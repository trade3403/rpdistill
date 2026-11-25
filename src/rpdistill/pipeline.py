"""Single-cycle, checkpointed acquisition-to-candidate-dataset orchestration."""
from contextlib import closing
from dataclasses import asdict
from datetime import datetime, timezone
import json
from pathlib import Path
import sqlite3
from uuid import uuid4

from .papers import PaperQuery, PaperCatalog
from .ncbi_papers import discover_with_source
from .fulltext import FulltextLibrary
from .corpus import CorpusStore
from .datasets import DatasetStore, DatasetGate
from .inference import TranslationOptions, load_teacher
from .teachers import TeacherRegistry, validate_id, validate_revision

STAGES=("search","download","parse","translate","snapshot")


def stamp():
    return datetime.now(timezone.utc).isoformat()


class CorpusPipeline:
    def __init__(self,db_path):
        self.path=Path(db_path)
        self.path.parent.mkdir(parents=True,exist_ok=True)
        with closing(self.connect()) as db,db:
            db.execute("""CREATE TABLE IF NOT EXISTS corpus_runs (
                id TEXT PRIMARY KEY, spec TEXT NOT NULL, state TEXT NOT NULL,
                stage INTEGER NOT NULL, results TEXT NOT NULL, error TEXT, updated TEXT NOT NULL)""")

    def connect(self):
        db=sqlite3.connect(self.path,timeout=10)
        db.row_factory=sqlite3.Row
        return db

    def get(self,run_id):
        with closing(self.connect()) as db:
            row=db.execute("SELECT * FROM corpus_runs WHERE id=?",(run_id,)).fetchone()
            if not row:
                raise KeyError("unknown corpus run")
            result=dict(row)
            for key in ("spec","results"):
                result[key]=json.loads(result[key])
            return result

    def create(self,query,model_id,revision,options,*,root,max_bytes,
               paper_limit=20,segment_limit=1000,gate=DatasetGate(),source="huggingface"):
        if not isinstance(query,PaperQuery) or not query.open_access_only:
            raise ValueError("pipeline requires open-access paper query")
        if not isinstance(options,TranslationOptions) or options.source_language!="English" or options.target_language!="Chinese":
            raise ValueError("current pipeline requires English to Chinese")
        if not isinstance(gate,DatasetGate):
            raise ValueError("invalid gate")
        validate_id(model_id)
        validate_revision(revision)
        TeacherRegistry(self.path,source=source).get(model_id,revision)
        for value,upper in ((max_bytes,2**40),(paper_limit,50),(segment_limit,1024)):
            if type(value) is not int or not 1<=value<=upper:
                raise ValueError("invalid pipeline budget")
        spec=dict(query=asdict(query),model_id=model_id,revision=revision,
                  options=asdict(options),root=str(Path(root).resolve()),
                  max_bytes=max_bytes,paper_limit=paper_limit,segment_limit=segment_limit,
                  gate=asdict(gate),source=source)
        run_id=uuid4().hex
        with closing(self.connect()) as db,db:
            db.execute("INSERT INTO corpus_runs VALUES (?,?,'queued',0,'{}',NULL,?)",
                       (run_id,json.dumps(spec),stamp()))
        return self.get(run_id)

    def run(self,run_id,*,search=discover_with_source,teacher_loader=load_teacher):
        with closing(self.connect()) as db,db:
            db.execute("BEGIN IMMEDIATE")
            if db.execute("SELECT 1 FROM corpus_runs WHERE state='running' LIMIT 1").fetchone():
                raise ValueError("a corpus worker is already active")
            updated=db.execute("UPDATE corpus_runs SET state='running',error=NULL,updated=? WHERE id=? AND state='queued'",
                               (stamp(),run_id))
            if updated.rowcount!=1:
                raise ValueError("run is not queued")
        run=self.get(run_id)
        spec,results=run["spec"],run["results"]
        stage=run["stage"]
        try:
            catalog=PaperCatalog(self.path)
            library=FulltextLibrary(self.path,spec["root"])
            corpus=CorpusStore(self.path)
            options=TranslationOptions(**spec["options"])
            while stage<len(STAGES):
                name=STAGES[stage]
                if name=="search":
                    value=search(PaperQuery(**spec["query"]),catalog,source="ncbi-pmc")
                    if value["inserted"]+value["duplicate"]==0:
                        raise ValueError("no usable search records")
                elif name=="download":
                    # Work against shared project catalog; prioritize unseen papers.
                    with closing(catalog.connect()) as db:
                        candidates=[json.loads(r[0]) for r in db.execute("""SELECT p.record FROM papers p
                            LEFT JOIN paper_fulltexts f ON p.pmcid=f.pmcid
                            WHERE json_extract(p.record,'$.eligibility')='pending_fulltext_license'
                            ORDER BY CASE WHEN f.pmcid IS NULL THEN 0 ELSE 1 END,p.paper_id LIMIT ?""",
                            (spec["paper_limit"],))]
                    value=library.download(candidates,max_bytes=spec["max_bytes"],limit=spec["paper_limit"])
                    if not value["saved"] and not value["cached"]:
                        raise ValueError("no downloaded papers")
                elif name=="parse":
                    value=corpus.parse(spec["root"],limit=spec["paper_limit"])
                    if not value["segments"]:
                        raise ValueError("no candidate source segments")
                elif name=="translate":
                    translator=teacher_loader(self.path,spec["model_id"],spec["revision"],options,source=spec["source"])
                    value=corpus.translate(translator,limit=spec["segment_limit"])
                    if value["failed"]:
                        raise RuntimeError("one or more translation batches failed")
                else:
                    value=DatasetStore(self.path).create(spec["model_id"],spec["revision"],options,
                        source=spec["source"],gate=DatasetGate(**spec["gate"]))
                results[name]=value
                stage+=1
                with closing(self.connect()) as db,db:
                    db.execute("UPDATE corpus_runs SET stage=?,results=?,updated=? WHERE id=?",
                               (stage,json.dumps(results),stamp(),run_id))
            state=("candidate_complete" if results["snapshot"]["status"]=="candidate_snapshot"
                   else "insufficient_candidates")
            error=None
        except (Exception,KeyboardInterrupt) as exc:
            state="failed" if not isinstance(exc,KeyboardInterrupt) else "interrupted"
            error=type(exc).__name__
        with closing(self.connect()) as db,db:
            db.execute("UPDATE corpus_runs SET state=?,error=?,updated=? WHERE id=?",
                       (state,error,stamp(),run_id))
        return self.get(run_id)

    def resume(self,run_id,*,worker_stopped=False):
        # Acquisition can consume unrecorded network bytes if interrupted.
        # Do not replay acquisition automatically; create a new authorized cycle.
        with closing(self.connect()) as db,db:
            db.execute("BEGIN IMMEDIATE")
            row=db.execute("SELECT stage,state FROM corpus_runs WHERE id=?",(run_id,)).fetchone()
            if not row:
                raise KeyError("unknown corpus run")
            if row["state"]=="running" and worker_stopped is not True:
                raise ValueError("confirm previous worker has stopped")
            if row["state"] not in ("failed","interrupted","running") or row["stage"]<2:
                raise ValueError("cannot resume acquisition; create a new budgeted cycle")
            db.execute("UPDATE corpus_runs SET state='queued',error=NULL,updated=? WHERE id=?",(stamp(),run_id))
        return self.get(run_id)
