import hashlib
import json
from pathlib import Path
from contextlib import closing
import tempfile
import unittest
from unittest.mock import Mock, patch
import sqlite3

from rpdistill.corpus import CorpusStore,stable_split
from rpdistill.datasets import DatasetStore,DatasetGate
from rpdistill.fulltext import FulltextLibrary
from rpdistill.inference import TeacherTranslator,TranslationOptions
from rpdistill.papers import PaperCatalog,PaperQuery,paper_from_record
from rpdistill.pipeline import CorpusPipeline
from rpdistill.teachers import Teacher,TeacherRegistry
from test_fulltext import xml

REV="a"*40
MODEL="test/model"
GATE=DatasetGate(1,1,1,100)
OPTIONS=TranslationOptions(batch_size=2)


class DatasetTests(unittest.TestCase):
    def setUp(self):
        tmp=tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root=Path(tmp.name)
        self.db=self.root/"db"
        self.catalog=PaperCatalog(self.db)
        self.library=FulltextLibrary(self.db,self.root/"xml")
        self.corpus=CorpusStore(self.db)
        self.datasets=DatasetStore(self.db)
        self.ids={}
        for i in range(1000,2000):
            pmcid="PMC"+str(i)
            self.ids.setdefault(stable_split(pmcid),pmcid)
            if len(self.ids)==3:
                break
        self.assertEqual(len(self.ids),3)

    def add(self,pmcid,text):
        doi="10.1234/"+pmcid.lower()
        self.catalog.ingest(paper_from_record(dict(source="MED",id=pmcid[3:],title="Research",
             authorString="Example Author",doi=doi,pmcid=pmcid,isOpenAccess="Y",license="cc by")))
        raw=xml(pmcid=pmcid,doi=doi).replace(b"<p>Example</p>",("<p>"+text+"</p>").encode())
        path=self.library.path_for(pmcid)
        path.write_bytes(raw)
        with closing(sqlite3.connect(self.db)) as db,db:
            self.library.save(db,dict(pmcid=pmcid,doi=doi,status="downloaded_pending_content_review",
               path=str(path),size=len(raw),sha256=hashlib.sha256(raw).hexdigest(),
               license_uri="https://creativecommons.org/licenses/by/4.0/",datestamp="2025-01-01"))

    def populate(self):
        for split,pmcid in self.ids.items():
            self.add(pmcid,"A scientific observation was recorded for "+split+" under controlled conditions.")
        self.corpus.parse(self.library.root)

    def translator(self):
        backend=Mock()
        backend.generate.side_effect=lambda messages,options:[
            dict(translation="在受控实验条件下记录了这项科研观察结果。",finish_reason="eos",generated_tokens=12)
            for _ in messages]
        return TeacherTranslator(dict(model_id=MODEL,revision=REV),OPTIONS,backend=backend)

    def make(self):
        return self.datasets.create(MODEL,REV,OPTIONS,gate=GATE)

    def test_gate_validation_and_empty(self):
        with self.assertRaises(ValueError):
            DatasetGate(5,5,5,10)
        self.assertEqual(self.make()["status"],"insufficient_candidates")
        self.assertEqual(self.datasets.list(),[])

    def test_snapshot_idempotent_and_integrity(self):
        self.populate()
        self.corpus.translate(self.translator())
        manifest=self.make()
        self.assertEqual(manifest["counts"],dict(train=1,validation=1,test=1))
        self.assertFalse(manifest["training_ready"])
        self.assertTrue(self.make()["reused"])
        out=self.root/"dataset.jsonl"
        exported=self.datasets.export(manifest["version"],out)
        self.assertEqual(hashlib.sha256(out.read_bytes()).hexdigest(),exported["payload_sha256"])
        self.assertEqual(len(out.read_text().splitlines()),3)
        with self.assertRaises(ValueError):
            self.datasets.export(manifest["version"],out)
        with closing(sqlite3.connect(self.db)) as db,db:
            db.execute("UPDATE dataset_members SET record='{}' WHERE ordinal=0")
        with self.assertRaisesRegex(ValueError,"integrity"):
            self.datasets.export(manifest["version"],self.root/"corrupt.jsonl")

    def test_wrong_configuration_excluded(self):
        self.populate()
        self.corpus.translate(self.translator())
        self.assertEqual(self.datasets.create(MODEL,"b"*40,OPTIONS,gate=GATE)["status"],
                         "insufficient_candidates")

    def test_tampered_fulltext_blocks_snapshot(self):
        self.populate()
        self.corpus.translate(self.translator())
        self.library.path_for(self.ids["test"]).write_bytes(b"tampered")
        self.assertEqual(self.make()["missing"]["test"],1)

    def test_persistent_cross_version_duplicate_guard(self):
        self.populate()
        self.corpus.translate(self.translator())
        first=self.make()
        train_text="A scientific observation was recorded for train under controlled conditions."
        other=next("PMC"+str(i) for i in range(2000,3000)
                   if stable_split("PMC"+str(i))=="test")
        self.add(other,train_text)
        self.corpus.parse(self.library.root)
        self.corpus.translate(self.translator())
        second=self.make()
        self.assertEqual(first["version"],second["version"])
        self.assertEqual(second["count"],3)

    def test_pipeline_single_cycle_and_resume(self):
        self.populate()
        TeacherRegistry(self.db).put(Teacher(MODEL,REV,"mit",False,False,None),self.root,[])
        pipe=CorpusPipeline(self.db)
        query=PaperQuery(("test",),"2025-01-01","2025-12-31",limit=3)
        run=pipe.create(query,MODEL,REV,OPTIONS,root=self.library.root,max_bytes=100000,
                         gate=GATE,paper_limit=3)
        search=Mock(return_value={"inserted":0,"duplicate":3})
        loader=Mock(side_effect=[RuntimeError("test"),self.translator()])
        with patch("rpdistill.pipeline.FulltextLibrary.download",return_value={"saved":0,"cached":3}) as dl:
            failed=pipe.run(run["id"],search=search,teacher_loader=loader)
            self.assertEqual(failed["stage"],3)
            self.assertEqual(failed["state"],"failed")
            pipe.resume(run["id"])
            done=pipe.run(run["id"],search=search,teacher_loader=loader)
            self.assertEqual(done["state"],"candidate_complete")
            self.assertEqual(done["stage"],5)
            self.assertFalse(done["results"]["snapshot"]["training_ready"])
            search.assert_called_once()
            dl.assert_called_once()

    def test_acquisition_failure_requires_new_budget(self):
        TeacherRegistry(self.db).put(Teacher(MODEL,REV,"mit",False,False,None),self.root,[])
        pipe=CorpusPipeline(self.db)
        query=PaperQuery(("test",),"2025-01-01","2025-12-31")
        run=pipe.create(query,MODEL,REV,OPTIONS,root=self.library.root,max_bytes=100,
                         gate=GATE)
        result=pipe.run(run["id"],search=Mock(side_effect=TimeoutError()))
        self.assertEqual(result["state"],"failed")
        self.assertEqual(result["stage"],0)
        with self.assertRaises(ValueError):
            pipe.resume(run["id"])

    def test_tokenized_snapshot_split_and_current_integrity(self):
        from rpdistill.training_data import snapshot_examples
        self.populate()
        self.corpus.translate(self.translator())
        manifest=self.make()
        codec=Mock()
        codec.encode.side_effect=lambda text,target=False: [3,0] if target else [2,4,0]
        rows,stats=snapshot_examples(self.db,manifest["version"],codec,split="train")
        self.assertEqual(stats["accepted"],1)
        self.assertEqual(len(rows),1)
        self.assertEqual(rows[0]["target_ids"],[3,0])
        self.assertEqual(codec.encode.call_count,2)
        self.library.path_for(self.ids["train"]).write_bytes(b"tampered")
        rows,stats=snapshot_examples(self.db,manifest["version"],codec,split="train")
        self.assertEqual(rows,[])
        self.assertEqual(stats["excluded"],1)
        with closing(sqlite3.connect(self.db)) as db,db:
            db.execute("UPDATE dataset_members SET record=replace(record,'Research','Tampered') WHERE ordinal=0")
        with self.assertRaises(ValueError):
            snapshot_examples(self.db,manifest["version"],codec,split="train")
