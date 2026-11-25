from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock
from rpdistill.training_queue import TrainingQueue
from rpdistill.resumable import ResumeConfig
from rpdistill.distill import DistillConfig

V="a"*64

class TrainingQueueTests(unittest.TestCase):
    def setUp(self):
        tmp=tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root=Path(tmp.name)
        self.q=TrainingQueue(self.root/"db")
    def enqueue(self,**kw):
        spec=dict(reviewed_dataset=V,reviewed_teacher_license="mit",
                  config=ResumeConfig(DistillConfig(steps=5)),segment_steps=2,
                  segment_seconds=10,total_seconds=30,total_checkpoint_bytes=3*2**30)
        spec.update(kw)
        return self.q.enqueue(V,self.root/"assets",self.root/"states",**spec)
    def test_enqueue_and_control(self):
        j=self.enqueue()
        self.assertEqual(self.enqueue()["id"],j["id"])
        self.assertEqual(self.q.control(j["id"],"pause")["state"],"paused")
        self.assertEqual(self.q.control(j["id"],"resume")["state"],"queued")
        self.assertEqual(self.q.control(j["id"],"cancel")["state"],"cancelled")
        self.assertIsNone(self.q.run_next())
    def test_review_and_budget(self):
        for kw in (dict(reviewed_dataset="b"*64),dict(total_seconds=9),
                   dict(total_checkpoint_bytes=100),dict(segment_steps=0)):
            with self.assertRaises(ValueError):
                self.enqueue(**kw)
    def test_failed_attempt_budget_not_refunded(self):
        j=self.enqueue(total_seconds=10)
        prep=Mock(side_effect=ValueError("test"))
        r=self.q.run_next(prepare=prep)
        self.assertEqual(r["state"],"failed")
        self.assertEqual(r["reserved_seconds"],10)
        self.assertEqual(r["reserved_bytes"],2**30)
        self.q.control(j["id"],"resume")
        self.assertEqual(self.q.run_next(prepare=prep)["state"],"budget_exhausted")
        prep.assert_called_once()
    def test_single_worker_and_explicit_recovery(self):
        j=self.enqueue()
        with self.q.write() as db:
            self.q.state(db,j["id"],"running")
        with self.assertRaises(ValueError):
            self.q.run_next()
        with self.assertRaises(ValueError):
            self.q.recover(j["id"])
        self.assertEqual(self.q.recover(j["id"],worker_stopped=True)["state"],"interrupted")
        self.assertEqual(self.q.control(j["id"],"resume")["state"],"queued")
    def test_pause_during_prepare(self):
        j=self.enqueue()
        def prep(*args,**kwargs):
            self.q.control(j["id"],"pause")
            raise RuntimeError("test")
        r=self.q.run_next(prepare=prep)
        self.assertEqual(r["state"],"paused")
        self.assertEqual(r["attempt"],1)
        self.assertGreater(len(self.q.events(j["id"])),2)
