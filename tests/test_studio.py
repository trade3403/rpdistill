import tempfile
from pathlib import Path
import sqlite3
from contextlib import closing
import unittest
from unittest.mock import patch
from rpdistill.studio import snapshot,SCHEMA

class StudioTests(unittest.TestCase):
    @patch("rpdistill.studio.device_report",return_value={})
    def test_missing_db_does_not_create(self,_):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)/"absent"/"db.sqlite3"
            r=snapshot(p)
            self.assertFalse(p.parent.exists())
            self.assertFalse(r["database_exists"])
            self.assertEqual(r["schema"],SCHEMA)
            self.assertEqual(sum(r["counts"].values()),0)
    @patch("rpdistill.studio.device_report",return_value={})
    def test_actual_read_only_counts_and_bounded_rows(self,_):
        from rpdistill.downloads import DownloadQueue
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)/"db.sqlite3"
            q=DownloadQueue(p)
            for i in range(51):
                q.enqueue("org/model"+str(i),"a"*40,reviewed_license="apache-2.0",max_bytes=1000,cache_dir=tmp)
            before=p.read_bytes()
            r=snapshot(p)
            self.assertEqual(r["counts"]["downloads"],51)
            self.assertEqual(r["counts"]["download_queued"],51)
            self.assertEqual(r["counts"]["download_active"],0)
            self.assertEqual(r["rows"]["downloads"][0]["source"],"huggingface")
            self.assertIsNone(r["rows"]["downloads"][0]["network_rate"])
            self.assertEqual(len(r["rows"]["downloads"]),50)
            self.assertEqual(r["rows"]["downloads"][0]["state"],"queued")
            self.assertNotIn("spec",r["rows"]["downloads"][0])
            self.assertEqual(p.read_bytes(),before)
            self.assertFalse(r["training_metrics_available"])

    @patch("rpdistill.studio.device_report",return_value={})
    def test_network_metrics_and_legacy_read_only(self,_):
        from rpdistill.downloads import DownloadQueue
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)/"db.sqlite3"
            q=DownloadQueue(p)
            job=q.enqueue("org/model","a"*40,reviewed_license="apache-2.0",max_bytes=1000,cache_dir=tmp)
            with closing(sqlite3.connect(p)) as db, db:
                db.execute("UPDATE model_download_jobs SET state='running',network_bytes=123,network_rate=45.5 WHERE id=?",(job["id"],))
            before=p.read_bytes()
            r=snapshot(p)
            self.assertEqual(r["counts"]["download_active"],1)
            self.assertEqual(r["counts"]["download_queued"],0)
            self.assertEqual(r["rows"]["downloads"][0]["network_bytes"],123)
            self.assertEqual(r["rows"]["downloads"][0]["network_rate"],45.5)
            self.assertEqual(p.read_bytes(),before)
            with closing(sqlite3.connect(p)) as db, db:
                db.execute("ALTER TABLE model_download_jobs DROP COLUMN network_bytes")
                db.execute("ALTER TABLE model_download_jobs DROP COLUMN network_rate")
            before=p.read_bytes()
            r=snapshot(p)
            self.assertIsNone(r["rows"]["downloads"][0]["network_bytes"])
            self.assertIsNone(r["rows"]["downloads"][0]["network_rate"])
            self.assertEqual(p.read_bytes(),before)

    @patch("rpdistill.studio.device_report",return_value={})
    def test_corpus_snapshot_bounded_and_read_only(self,_):
        import json
        from rpdistill.pipeline import CorpusPipeline
        from rpdistill.papers import PaperCatalog
        from rpdistill.datasets import DatasetStore
        from contextlib import closing
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)/"db.sqlite3"
            CorpusPipeline(p)
            PaperCatalog(p)
            DatasetStore(p)
            with closing(sqlite3.connect(p)) as db, db:
                db.execute("INSERT INTO corpus_runs VALUES (?,?,'running',2,?,NULL,?)",
                    ("a"*32,json.dumps({"model_id":"fixture/model","query":{"keywords":["biology"]},"max_bytes":1024,"paper_limit":2}),"{}","2026-01-01"))
                db.execute("INSERT INTO papers(doi,pmcid,record) VALUES (?,?,?)",
                    ("10.1234/test","PMC123",json.dumps({"title":"fixture title","eligibility":"pending_fulltext_license"})))
                db.execute("INSERT INTO dataset_versions VALUES (?,?)",("b"*64,json.dumps({"counts":{"train":10,"validation":1,"test":1},"status":"candidate_snapshot","teacher":{"model_id":"fixture/model"}})))
            before=p.read_bytes()
            r=snapshot(p)
            self.assertEqual(r["counts"]["pipeline_active"],1)
            self.assertEqual(r["rows"]["pipelines"][0]["keyword"],"biology")
            self.assertEqual(r["rows"]["papers"][0]["title"],"fixture title")
            self.assertEqual(r["rows"]["datasets"][0]["train"],10)
            self.assertNotIn("spec",r["rows"]["pipelines"][0])
            self.assertNotIn("manifest",r["rows"]["datasets"][0])
            self.assertEqual(p.read_bytes(),before)

    @patch("rpdistill.studio.device_report",return_value={})
    def test_training_snapshot_loss_single_job_and_read_only(self,_):
        from rpdistill.training_queue import TrainingQueue
        from rpdistill.resumable import required_bytes
        from rpdistill.student import FIXED
        from contextlib import closing
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)/"db"
            q=TrainingQueue(p)
            j=q.enqueue("c"*64,Path(tmp)/"assets",Path(tmp)/"states",reviewed_dataset="c"*64,
                reviewed_teacher_license="mit",total_seconds=300,total_checkpoint_bytes=2**30)
            with q.write() as db:
                db.execute("UPDATE training_jobs SET step=2,state='running' WHERE id=?",(j["id"],))
                q.event(db,j["id"],"running",step=1,loss=2.5)
                q.event(db,j["id"],"running",step=2,loss=1.75)
                q.event(db,"d"*32,"running",step=2,loss=99)
            before=p.read_bytes()
            r=snapshot(p)
            self.assertEqual(r["counts"]["training_active"],1)
            self.assertEqual(r["counts"]["checkpoint_min_bytes"],required_bytes(FIXED))
            self.assertEqual([v["loss"] for v in r["rows"]["training_loss"]],[2.5,1.75])
            self.assertTrue(r["training_metrics_available"])
            self.assertNotIn("spec",r["rows"]["training"][0])
            self.assertEqual(p.read_bytes(),before)
