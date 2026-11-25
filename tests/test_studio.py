import tempfile
from pathlib import Path
import sqlite3
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
            self.assertEqual(len(r["rows"]["downloads"]),50)
            self.assertEqual(r["rows"]["downloads"][0]["state"],"queued")
            self.assertNotIn("spec",r["rows"]["downloads"][0])
            self.assertEqual(p.read_bytes(),before)
            self.assertFalse(r["training_metrics_available"])
