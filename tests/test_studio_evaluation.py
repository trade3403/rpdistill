import tempfile
from pathlib import Path
import json
import unittest
from contextlib import closing
from rpdistill.training_queue import TrainingQueue
from rpdistill.studio_evaluation import evaluate_job, recover_evaluation, connect, initialize
from rpdistill.evaluation import hash_json
from rpdistill.studio import snapshot
from unittest.mock import patch

class StudioEvaluationTests(unittest.TestCase):
    def test_reject_unapproved_and_incomplete(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp); db=root/"db"
            q=TrainingQueue(db)
            j=q.enqueue("a"*64,root/"assets",root/"checkpoints",reviewed_dataset="a"*64,
                reviewed_teacher_license="mit",total_seconds=300,total_checkpoint_bytes=2**30)
            for approved in (False,True):
                with self.assertRaises(ValueError):
                    evaluate_job(db,j["id"],root/"input.jsonl",root/"eval","test",approved=approved)
            self.assertFalse((root/"eval").exists())
    def test_persist_report_and_recovery(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp); db=root/"db"; q=TrainingQueue(db)
            j=q.enqueue("a"*64,root/"assets",root/"checkpoints",reviewed_dataset="a"*64,
                reviewed_teacher_license="mit",total_seconds=300,total_checkpoint_bytes=2**30)
            # Match the real queue: its spec stores a canonical absolute root.
            # Temporary paths may use aliases (macOS /var, Windows junctions/short names).
            checkpoint=Path(j["spec"]["root"])/j["id"]/"attempt-00000001"
            checkpoint.mkdir(parents=True)
            m={"fixture":True}; m["checkpoint_id"]=hash_json(m)
            (checkpoint/"manifest.json").write_text(json.dumps(m),encoding="utf-8")
            with q.write() as c:
                c.execute("UPDATE training_jobs SET state='complete',checkpoint=?,checkpoint_id=? WHERE id=?",
                          (str(checkpoint),m["checkpoint_id"],j["id"]))
            inp=root/"input.jsonl"; inp.write_text("{}\n",encoding="utf-8")
            benchmark={"benchmark_id":"b"*64}
            report={"checkpoint_id":m["checkpoint_id"],"benchmark_id":"b"*64,"release_ready":False,
                    "metrics":{"bleu":20.0,"chrf":42.0},"coverage":{"cases":1,"papers":1},
                    "automatic_gate_passed":False,"failures":["coverage:cases"],"performance":{}}
            report["report_id"]=hash_json(report)
            # The containment check must still reject a checkpoint outside the registered root.
            with q.write() as c:
                c.execute("UPDATE training_jobs SET checkpoint=? WHERE id=?",
                          (str(root/"outside"/"attempt-00000001"),j["id"]))
            with self.assertRaisesRegex(ValueError,"checkpoint outside registered job root"):
                evaluate_job(db,j["id"],inp,root/"eval","fixture",approved=True)
            self.assertFalse((root/"eval").exists())
            with q.write() as c:
                c.execute("UPDATE training_jobs SET checkpoint=? WHERE id=?",(str(checkpoint),j["id"]))
            with patch("rpdistill.studio_evaluation.freeze_benchmark",return_value=benchmark):
                result=evaluate_job(db,j["id"],inp,root/"eval","fixture",approved=True,evaluate_fn=lambda *a,**kw:report)
            self.assertFalse(result["release_ready"])
            self.assertEqual(snapshot(db)["rows"]["evaluations"][0]["chrf"],42.0)
            self.assertTrue((root/"eval"/result["id"]/"report.json").is_file())
            with closing(connect(db)) as c,c:
                c.execute("UPDATE studio_evaluations SET state='running' WHERE id=?",(result["id"],))
            with self.assertRaises(ValueError):
                recover_evaluation(db,result["id"])
            self.assertEqual(recover_evaluation(db,result["id"],worker_stopped=True)["state"],"interrupted")
