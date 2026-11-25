from pathlib import Path
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from threading import Event
from unittest.mock import Mock, patch

from rpdistill.downloads import DownloadQueue
from rpdistill.teachers import download_teacher
from test_teachers import info, MODEL, REV, PAYLOAD


class DownloadTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        self.q = DownloadQueue(self.root / "db.sqlite")

    def enqueue(self):
        return self.q.enqueue(MODEL, REV, reviewed_license="apache-2.0",
                              max_bytes=1024, cache_dir=self.root / "cache")

    def test_persistent_dedup(self):
        first = self.enqueue()
        self.assertEqual(self.enqueue()["id"], first["id"])
        self.assertEqual(DownloadQueue(self.q.path).list(), [first])

    def test_verified_progress_success(self):
        job = self.enqueue()
        def execute(**kwargs):
            kwargs["progress"](0, 10)
            kwargs["progress"](5, 10)
            row = self.q.get(job["id"])
            self.assertEqual(row["done_bytes"], 5)
            self.assertGreater(row["rate"], 0)
            kwargs["progress"](10, 10)
        result = self.q.run_next(execute=execute)
        self.assertEqual(result["state"], "succeeded")
        self.assertEqual(result["done_bytes"], 10)
        self.assertIsNone(self.q.run_next(execute=execute))

    def test_pause_and_resume(self):
        job = self.enqueue()
        def execute(**kwargs):
            kwargs["progress"](0, 10)
            self.q.control(job["id"], "pause")
            kwargs["checkpoint"]()
        self.assertEqual(self.q.run_next(execute=execute)["state"], "paused")
        self.assertEqual(self.q.control(job["id"], "resume")["state"], "queued")
        self.assertEqual(self.q.control(job["id"], "cancel")["state"], "cancelled")

    def test_running_cancel(self):
        job = self.enqueue()
        def execute(**kwargs):
            self.q.control(job["id"], "cancel")
            kwargs["checkpoint"]()
        self.assertEqual(self.q.run_next(execute=execute)["state"], "cancelled")

    def test_failure_redacted_and_retry(self):
        job = self.enqueue()
        def execute(**kwargs):
            raise RuntimeError("secret url")
        result = self.q.run_next(execute=execute)
        self.assertEqual(result["state"], "failed")
        self.assertEqual(result["error"], "RuntimeError")
        self.assertEqual(self.q.control(job["id"], "resume")["state"], "queued")

    def test_interrupt_and_incomplete(self):
        job = self.enqueue()
        def execute(**kwargs):
            raise KeyboardInterrupt()
        self.assertEqual(self.q.run_next(execute=execute)["state"], "interrupted")
        self.q.control(job["id"], "resume")
        self.assertEqual(self.q.run_next(execute=lambda **kw: None)["error"], "IncompleteProgress")

    def test_atomic_single_worker(self):
        self.enqueue()
        entered, release = Event(), Event()
        def execute(**kwargs):
            entered.set()
            if not release.wait(5):
                raise RuntimeError("test worker timeout")
            kwargs["progress"](1, 1)
        with ThreadPoolExecutor(max_workers=1) as pool:
            future = pool.submit(self.q.run_next, execute=execute)
            try:
                self.assertTrue(entered.wait(5))
                with self.assertRaisesRegex(ValueError, "active worker"):
                    self.q.run_next(execute=execute)
            finally:
                release.set()
            self.assertEqual(future.result(timeout=5)["state"], "succeeded")

    def test_recovery_requires_confirmation(self):
        job = self.enqueue()
        with self.q._write() as db:
            db.execute("UPDATE model_download_jobs SET state='running' WHERE id=?", (job["id"],))
        with self.assertRaises(ValueError):
            self.q.recover(job["id"])
        self.assertEqual(self.q.recover(job["id"], worker_stopped=True)["state"], "interrupted")

    @patch("rpdistill.teachers.time.sleep")
    def test_per_file_download_retry_and_register(self, sleep):
        self.enqueue()
        api = Mock()
        api.model_info.return_value = info()
        attempts = []
        def downloader(**kwargs):
            name = kwargs["allow_patterns"][0]
            attempts.append(name)
            if len(attempts) == 1:
                raise TimeoutError("temporary")
            dest = kwargs["cache_dir"] / "snapshot"
            dest.mkdir(exist_ok=True)
            (dest / name).write_bytes(PAYLOAD[name])
            return dest
        result = self.q.run_next(execute=lambda **kwargs: download_teacher(
            **kwargs, api=api, downloader=downloader))
        self.assertEqual(result["state"], "succeeded")
        self.assertEqual(result["done_bytes"], sum(map(len, PAYLOAD.values())))
        self.assertEqual(len(attempts), 4)
        sleep.assert_called_once()
