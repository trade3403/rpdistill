import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor

from rpdistill.config import TrainingConfig
from rpdistill.tasks import TaskStore


class TaskTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.path = Path(self.tmp.name) / "tasks.sqlite3"
        self.store = TaskStore(self.path)

    def create(self):
        return self.store.create(TrainingConfig("teacher", "student", seed=7))

    def test_persist_config_and_events(self):
        task = self.create()
        other = TaskStore(self.path)
        self.assertEqual(other.get(task["id"]), task)
        self.assertEqual(task["state"], "queued")
        self.assertEqual(task["config"]["seed"], 7)
        self.assertEqual(other.list(), [task])
        self.assertEqual(other.events(task["id"])[0]["state"], "queued")

    def test_lifecycle_and_retry(self):
        task_id = self.create()["id"]
        for old, new in [
            ("queued", "running"), ("running", "interrupted"),
            ("interrupted", "queued"), ("queued", "running"),
            ("running", "paused"), ("paused", "queued"),
            ("queued", "running"), ("running", "succeeded"),
        ]:
            self.assertEqual(self.store.transition(task_id, old, new)["state"], new)
        self.assertEqual(len(self.store.events(task_id)), 9)

    def test_invalid_transition_and_conflict_no_event(self):
        task_id = self.create()["id"]
        with self.assertRaises(ValueError):
            self.store.transition(task_id, "queued", "succeeded")
        with self.assertRaises(ValueError):
            self.store.transition(task_id, "running", "failed")
        self.assertEqual(len(self.store.events(task_id)), 1)

    def test_unknown_task(self):
        with self.assertRaises(KeyError):
            self.store.get("not-a-task")

    def test_atomic_concurrent_claim(self):
        task_id = self.create()["id"]

        def claim():
            try:
                self.store.transition(task_id, "queued", "running")
                return True
            except ValueError:
                return False

        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(lambda _: claim(), range(2)))
        self.assertEqual(sum(results), 1)
        self.assertEqual(len(self.store.events(task_id)), 2)

    def test_cli_persistence(self):
        prefix = [sys.executable, "-m", "rpdistill", "--db", str(self.path)]
        def call(*args):
            return json.loads(subprocess.check_output(prefix + list(args), text=True))
        task = call("create", "--teacher", "t", "--student", "s")
        self.assertEqual(call("show", task["id"]), task)
        self.assertEqual(call("list"), [task])
        self.assertEqual(call("events", task["id"])[0]["state"], "queued")
