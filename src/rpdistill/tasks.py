"""Persistent experiment metadata and atomic lifecycle transitions.

This module records lifecycle state; it does not execute or suspend workers.
"""
from contextlib import closing, contextmanager
from dataclasses import asdict
from datetime import datetime, timezone
import json
from pathlib import Path
import sqlite3
from uuid import uuid4

from .config import TrainingConfig

TRANSITIONS = {
    "queued": {"running", "cancelled"},
    "running": {"paused", "succeeded", "failed", "cancelled", "interrupted"},
    "paused": {"queued", "cancelled"},
    "interrupted": {"queued", "cancelled"},
    "failed": {"queued", "cancelled"},
    "succeeded": set(),
    "cancelled": set(),
}


def timestamp() -> str:
    return datetime.now(timezone.utc).isoformat()


class TaskStore:
    def __init__(self, path: str | Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self._write() as db:
            db.execute("""CREATE TABLE IF NOT EXISTS tasks (
                id TEXT PRIMARY KEY, config TEXT NOT NULL, state TEXT NOT NULL,
                created_at TEXT NOT NULL, updated_at TEXT NOT NULL)""")
            db.execute("""CREATE TABLE IF NOT EXISTS events (
                seq INTEGER PRIMARY KEY AUTOINCREMENT, task_id TEXT NOT NULL
                REFERENCES tasks(id), at TEXT NOT NULL, state TEXT NOT NULL,
                message TEXT NOT NULL)""")

    def _connect(self):
        db = sqlite3.connect(self.path, timeout=10)
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA foreign_keys = ON")
        return db

    @contextmanager
    def _write(self):
        with closing(self._connect()) as db, db:
            db.execute("BEGIN IMMEDIATE")
            yield db

    @staticmethod
    def _row(row):
        if row is None:
            raise KeyError("unknown task")
        result = dict(row)
        result["config"] = json.loads(result["config"])
        return result

    @staticmethod
    def _event(db, task_id, state, message, at):
        db.execute("INSERT INTO events(task_id, at, state, message) VALUES (?, ?, ?, ?)",
                   (task_id, at, state, message))

    def create(self, config: TrainingConfig) -> dict:
        if not isinstance(config, TrainingConfig):
            raise TypeError("expected TrainingConfig")
        task_id, now = uuid4().hex, timestamp()
        with self._write() as db:
            db.execute("INSERT INTO tasks VALUES (?, ?, ?, ?, ?)",
                       (task_id, json.dumps(asdict(config), allow_nan=False),
                        "queued", now, now))
            self._event(db, task_id, "queued", "experiment created", now)
        return self.get(task_id)

    def get(self, task_id: str) -> dict:
        with closing(self._connect()) as db:
            return self._row(db.execute("SELECT * FROM tasks WHERE id = ?",
                                        (task_id,)).fetchone())

    def list(self) -> list[dict]:
        with closing(self._connect()) as db:
            return [self._row(row) for row in db.execute(
                "SELECT * FROM tasks ORDER BY created_at, id")]

    def events(self, task_id: str) -> list[dict]:
        self.get(task_id)
        with closing(self._connect()) as db:
            return [dict(row) for row in db.execute(
                "SELECT * FROM events WHERE task_id = ? ORDER BY seq", (task_id,))]

    def transition(self, task_id: str, expected: str, target: str,
                   message: str = "") -> dict:
        if target not in TRANSITIONS.get(expected, set()):
            raise ValueError(f"invalid transition: {expected} -> {target}")
        if not isinstance(message, str) or len(message) > 4096:
            raise ValueError("message must be text of at most 4096 characters")
        now = timestamp()
        with self._write() as db:
            row = self._row(db.execute("SELECT * FROM tasks WHERE id = ?",
                                       (task_id,)).fetchone())
            if row["state"] != expected:
                raise ValueError(f"state conflict: expected {expected}, found {row['state']}")
            db.execute("UPDATE tasks SET state = ?, updated_at = ? WHERE id = ?",
                       (target, now, task_id))
            self._event(db, task_id, target, message or f"{expected} -> {target}", now)
            result = self._row(db.execute("SELECT * FROM tasks WHERE id = ?",
                                          (task_id,)).fetchone())
        return result
