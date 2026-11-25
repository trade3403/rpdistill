"""Persistent single-worker model download jobs, with cooperative file-boundary control."""
from __future__ import annotations

from contextlib import closing, contextmanager
from datetime import datetime, timezone
import json
from pathlib import Path
import sqlite3
import time
from uuid import uuid4

from .teachers import TeacherRegistry, download_teacher, validate_id, validate_revision


def now():
    return datetime.now(timezone.utc).isoformat()


class StopRequested(Exception):
    pass


class DownloadQueue:
    def __init__(self, db_path):
        self.path = Path(db_path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self._write() as db:
            db.execute("""CREATE TABLE IF NOT EXISTS model_download_jobs (
                id TEXT PRIMARY KEY, spec TEXT NOT NULL, state TEXT NOT NULL,
                done_bytes INTEGER NOT NULL DEFAULT 0, total_bytes INTEGER,
                rate REAL, eta REAL, error TEXT, updated TEXT NOT NULL,
                created TEXT NOT NULL)""")

    def _connect(self):
        db = sqlite3.connect(self.path, timeout=10)
        db.row_factory = sqlite3.Row
        return db

    @contextmanager
    def _write(self):
        with closing(self._connect()) as db, db:
            db.execute("BEGIN IMMEDIATE")
            yield db

    @staticmethod
    def _get(db, job_id):
        row = db.execute("SELECT * FROM model_download_jobs WHERE id=?", (job_id,)).fetchone()
        if row is None:
            raise KeyError("unknown download job")
        result = dict(row)
        result["spec"] = json.loads(result["spec"])
        return result

    def get(self, job_id):
        with closing(self._connect()) as db:
            return self._get(db, job_id)

    def list(self):
        with closing(self._connect()) as db:
            return [self._get(db, r[0]) for r in db.execute(
                "SELECT id FROM model_download_jobs ORDER BY created, id")]

    def enqueue(self, model_id, revision, *, reviewed_license, max_bytes, cache_dir,
                source="huggingface"):
        if source not in ("huggingface", "modelscope"):
            raise ValueError("unknown model source")
        if source == "modelscope" and "/" not in model_id:
            raise ValueError("ModelScope requires owner/name")
        validate_id(model_id)
        validate_revision(revision)
        if not isinstance(reviewed_license, str) or not reviewed_license.strip():
            raise ValueError("license review required")
        if type(max_bytes) is not int or not 0 < max_bytes < 2**63:
            raise ValueError("invalid byte budget")
        spec = dict(model_id=model_id, revision=revision, reviewed_license=reviewed_license,
                    max_bytes=max_bytes, cache_dir=str(Path(cache_dir).resolve()))
        if source != "huggingface":
            spec["source"] = source
        encoded = json.dumps(spec, sort_keys=True)
        with self._write() as db:
            existing = db.execute("""SELECT id FROM model_download_jobs
                WHERE spec=? AND state IN ('queued','running','pause_requested',
                'cancel_requested','paused')""", (encoded,)).fetchone()
            if existing:
                return self._get(db, existing[0])
            job_id = uuid4().hex
            stamp = now()
            db.execute("""INSERT INTO model_download_jobs(id,spec,state,updated,created)
                VALUES (?,?,'queued',?,?)""", (job_id, encoded, stamp, stamp))
            return self._get(db, job_id)

    def control(self, job_id, action):
        with self._write() as db:
            row = self._get(db, job_id)
            state = row["state"]
            changes = {
                "pause": {"queued": "paused", "running": "pause_requested"},
                "cancel": {"queued": "cancelled", "paused": "cancelled",
                           "failed": "cancelled", "interrupted": "cancelled",
                           "running": "cancel_requested", "pause_requested": "cancel_requested"},
                "resume": {"paused": "queued", "failed": "queued", "interrupted": "queued"},
            }
            target = changes.get(action, {}).get(state)
            if target is None:
                raise ValueError(f"cannot {action} job in state {state}")
            db.execute("UPDATE model_download_jobs SET state=?,updated=? WHERE id=?",
                       (target, now(), job_id))
            return self._get(db, job_id)

    def recover(self, job_id, *, worker_stopped=False):
        """Operator must verify the former worker process has exited."""
        if worker_stopped is not True:
            raise ValueError("confirm the previous worker has stopped")
        with self._write() as db:
            row = self._get(db, job_id)
            if row["state"] not in ("running", "pause_requested", "cancel_requested"):
                raise ValueError("job is not active")
            target = {"running": "interrupted", "pause_requested": "paused",
                      "cancel_requested": "cancelled"}[row["state"]]
            db.execute("UPDATE model_download_jobs SET state=?,rate=NULL,eta=NULL,updated=? WHERE id=?",
                       (target, now(), job_id))
            return self._get(db, job_id)

    def run_next(self, *, execute=None):
        with self._write() as db:
            # Enforce a single active worker per database, including pending stop requests.
            if db.execute("""SELECT 1 FROM model_download_jobs WHERE
                    state IN ('running','pause_requested','cancel_requested') LIMIT 1""").fetchone():
                raise ValueError("an active worker already owns the queue")
            row = db.execute("""SELECT id FROM model_download_jobs WHERE state='queued'
                ORDER BY created,id LIMIT 1""").fetchone()
            if row is None:
                return None
            job_id = row[0]
            db.execute("""UPDATE model_download_jobs SET state='running',done_bytes=0,
                       total_bytes=NULL,rate=NULL,eta=NULL,error=NULL,updated=? WHERE id=?""",
                       (now(), job_id))
            spec = self._get(db, job_id)["spec"]
        source = spec.pop("source", "huggingface")
        if execute is None:
            if source == "modelscope":
                from .modelscope_source import download_modelscope
                execute = download_modelscope
            else:
                execute = download_teacher
        start = time.monotonic()

        def checkpoint():
            state = self.get(job_id)["state"]
            if state != "running":
                raise StopRequested()

        def progress(done, total):
            if type(done) is not int or type(total) is not int or not 0 <= done <= total:
                raise ValueError("invalid verified progress")
            elapsed = max(time.monotonic() - start, 0.001)
            rate = done / elapsed if done else None
            eta = (total - done) / rate if rate else None
            with self._write() as db:
                row = self._get(db, job_id)
                if row["state"] != "running":
                    raise StopRequested()
                if done < row["done_bytes"] or (row["total_bytes"] is not None
                                               and row["total_bytes"] != total):
                    raise ValueError("nonmonotonic progress")
                db.execute("""UPDATE model_download_jobs SET done_bytes=?,total_bytes=?,
                    rate=?,eta=?,updated=? WHERE id=?""", (done, total, rate, eta, now(), job_id))

        target, error = "succeeded", None
        try:
            execute(**spec, registry=TeacherRegistry(self.path, source=source),
                    checkpoint=checkpoint, progress=progress)
        except StopRequested:
            target = "interrupted"
        except KeyboardInterrupt:
            target = "interrupted"
        except Exception as exc:
            # Avoid recording URLs or credentials in the error string.
            target, error = "failed", type(exc).__name__
        with self._write() as db:
            row = self._get(db, job_id)
            # Completion wins if a request arrives after the final checkpoint/registration.
            if target != "succeeded":
                target = {"pause_requested": "paused", "cancel_requested": "cancelled"}.get(
                    row["state"], target)
            if target == "succeeded" and (row["total_bytes"] is None
                                           or row["done_bytes"] != row["total_bytes"]):
                target, error = "failed", "IncompleteProgress"
            db.execute("""UPDATE model_download_jobs SET state=?,error=?,rate=NULL,eta=NULL,
                       updated=? WHERE id=?""", (target, error, now(), job_id))
            return self._get(db, job_id)
