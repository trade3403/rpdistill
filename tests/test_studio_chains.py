import tempfile
from pathlib import Path
from contextlib import closing
import json
import unittest
from unittest.mock import patch
from rpdistill.training_queue import TrainingQueue,now
from rpdistill.studio_evaluation import connect,initialize as init_eval,recover_evaluation
from rpdistill.studio_artifacts import initialize as init_art
from rpdistill.studio_chains import run_chain,recover
from rpdistill.studio_chain_state import claim,initialize
from rpdistill.studio import snapshot

class StudioChainTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name)
        self.db=self.root/"db"
        q=TrainingQueue(self.db)
        j=q.enqueue("a"*64,self.root/"assets",self.root/"checkpoints",reviewed_dataset="a"*64,
                    reviewed_teacher_license="mit",total_seconds=300,total_checkpoint_bytes=2**30)
        self.job=j["id"]
        self.version=j["spec"]["version"]
        self.checkpoint="b"*64
        self.source="c"*32
        spec=j["spec"]|{"corpus_run":self.source,"review_note":"review asserted"}
        with q.write() as db:
            db.execute("UPDATE training_jobs SET spec=?,state='complete',checkpoint=?,checkpoint_id=? WHERE id=?",
                       (json.dumps(spec),str(self.root/"checkpoint"),self.checkpoint,self.job))
            db.execute("INSERT INTO studio_training_links VALUES (?,?,?,?,?,?)",
                       (self.version,self.source,self.job,"mit","review asserted",now()))
        # This suite tests orchestration. The actual source validator is covered by test_datasets.
        p=patch("rpdistill.studio_chains.linked_candidate",return_value={})
        p.start();self.addCleanup(p.stop)
        self.calls=[]
    def run_chain(self,approved=True):
        return run_chain(self.db,self.job,self.root/"refs.jsonl",self.root/"eval",self.root/"art",
            review_note="reference reviewed",mode="int8",compression_bytes=2**30,export_bytes=2**30,
            max_seconds=60,license_label="mit",rights_note="local only",approved=approved)
    def evaluation(self,path,training_id,*args,chain_id,passed=True,**kw):
        self.calls.append("evaluation")
        self.assertEqual(training_id,self.job)
        id="d"*32
        with closing(connect(path)) as db,db:
            init_eval(db)
            claim(db,chain_id,"evaluation",id,training_id,now())
            db.execute("INSERT INTO studio_evaluations VALUES (?,?,?,?,'complete',?,NULL,?,?)",
                (id,training_id,self.version,self.checkpoint,json.dumps({"automatic_gate_passed":passed}),now(),now()))
        return {"id":id,"release_ready":False}
    def artifact(self,path,eid,mode,*args,chain_id,passed=True,**kw):
        self.calls.append(mode)
        self.assertEqual(eid,"d"*32)
        id="e"*32 if mode!="export" else "f"*32
        with closing(connect(path)) as db,db:
            init_art(db)
            claim(db,chain_id,"export" if mode=="export" else "compression",id,eid,now(),mode=mode)
            db.execute("INSERT INTO studio_artifacts VALUES (?,?,?,'complete',?,NULL,?,?)",
                       (id,eid,mode,json.dumps({"verified":True,"regression_passed":passed,"release_ready":False}),now(),now()))
        return {"id":id,"release_ready":False}
    def test_gate_stop(self):
        with patch("rpdistill.studio_chains.evaluate_job",side_effect=lambda *a,**k:self.evaluation(*a,**k,passed=False)),patch("rpdistill.studio_chains.run_artifact") as artifact:
            with self.assertRaises(ValueError):
                self.run_chain(False)
            r=self.run_chain()
            self.assertEqual((r["state"],r["stage"]),("stopped","evaluation"))
            artifact.assert_not_called()
            self.assertFalse(r["release_ready"])
        self.assertEqual(self.calls,["evaluation"])
    def test_regression_stop(self):
        with patch("rpdistill.studio_chains.evaluate_job",side_effect=self.evaluation),patch("rpdistill.studio_chains.run_artifact",side_effect=lambda *a,**k:self.artifact(*a,**k,passed=False)):
            r=self.run_chain()
        self.assertEqual((r["state"],r["stage"]),("stopped","compression"))
        self.assertEqual(self.calls,["evaluation","int8"])
        self.assertIsNone(r["export_id"])
    def test_full_chain_and_duplicate(self):
        with patch("rpdistill.studio_chains.evaluate_job",side_effect=self.evaluation),patch("rpdistill.studio_chains.run_artifact",side_effect=self.artifact):
            r=self.run_chain()
            self.assertEqual((r["state"],r["stage"]),("complete","done"))
            self.assertFalse(r["release_ready"])
            with self.assertRaises(ValueError):
                self.run_chain()
        self.assertEqual(self.calls,["evaluation","int8","export"])
        self.assertEqual(snapshot(self.db)["rows"]["chains"][0]["export_id"],"f"*32)
    def test_interrupted_owner_recovery(self):
        def crash(path,training_id,*args,chain_id,**kw):
            with closing(connect(path)) as db,db:
                init_eval(db)
                with self.assertRaises(ValueError):
                    claim(db,None,"evaluation","e"*32,training_id,now())
                claim(db,chain_id,"evaluation","d"*32,training_id,now())
                db.execute("INSERT INTO studio_evaluations VALUES (?,?,?,?,'running',NULL,NULL,?,?)",
                    ("d"*32,training_id,self.version,self.checkpoint,now(),now()))
            raise RuntimeError("fixture crash")
        with patch("rpdistill.studio_chains.evaluate_job",side_effect=crash):
            with self.assertRaises(RuntimeError):
                self.run_chain()
        s=snapshot(self.db)
        id=s["rows"]["chains"][0]["id"]
        self.assertEqual(s["counts"]["chain_active"],1)
        with self.assertRaises(ValueError):
            recover_evaluation(self.db,"d"*32,worker_stopped=True)
        with self.assertRaises(ValueError):
            recover(self.db,id)
        self.assertEqual(recover(self.db,id,worker_stopped=True)["state"],"interrupted")
        self.assertEqual(snapshot(self.db)["rows"]["evaluations"][0]["state"],"interrupted")
