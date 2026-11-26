"""Bounded local Studio evaluation records. Never grants release approval."""
from contextlib import closing
from pathlib import Path
import json
import re
import sqlite3
from uuid import uuid4
from .training_queue import TrainingQueue, now
from .evaluation import freeze_benchmark, read_jsonl, read_json, write_new, hash_json
from .student_evaluation import evaluate_checkpoint, GenerationConfig

def connect(db_path):
    db=sqlite3.connect(db_path,timeout=10)
    db.row_factory=sqlite3.Row
    return db

def initialize(db):
    db.execute("""CREATE TABLE IF NOT EXISTS studio_evaluations (
        id TEXT PRIMARY KEY,training_id TEXT NOT NULL,version TEXT NOT NULL,
        checkpoint_id TEXT NOT NULL,state TEXT NOT NULL,summary TEXT,error TEXT,
        created TEXT NOT NULL,updated TEXT NOT NULL)""")

def evaluate_job(db_path,training_id,input_path,root,review_note,*,approved=False,
                 evaluate_fn=evaluate_checkpoint):
    if approved is not True or not re.fullmatch(r"[a-f0-9]{32}",training_id):
        raise ValueError("explicit evaluation approval required")
    job=TrainingQueue(db_path).get(training_id)
    if job["state"]!="complete" or not job["checkpoint"] or not job["checkpoint_id"]:
        raise ValueError("completed registered checkpoint required")
    spec=job["spec"]
    checkpoint=Path(job["checkpoint"])
    if checkpoint.parent!=Path(spec["root"])/training_id:
        raise ValueError("checkpoint outside registered job root")
    m=read_json(checkpoint/"manifest.json")
    if (m.get("checkpoint_id")!=job["checkpoint_id"] or
        hash_json({k:v for k,v in m.items() if k!="checkpoint_id"})!=job["checkpoint_id"]):
        raise ValueError("registered checkpoint identity mismatch")
    rows=read_jsonl(input_path)
    if not 1<=len(rows)<=200:
        raise ValueError("Studio supports 1–200 reviewed reference cases")
    benchmark=freeze_benchmark(db_path,spec["version"],rows,review_note=review_note)
    id=uuid4().hex
    root=Path(root)
    if root.is_symlink():
        raise ValueError("symlink evaluation root")
    with closing(connect(db_path)) as db,db:
        db.execute("BEGIN IMMEDIATE")
        initialize(db)
        if db.execute("SELECT 1 FROM studio_evaluations WHERE state='running'").fetchone():
            raise ValueError("another evaluation is active or needs recovery")
        for table in ("training_jobs","model_download_jobs","corpus_runs","studio_artifacts"):
            if db.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name=?",(table,)).fetchone():
                if db.execute("SELECT 1 FROM "+table+" WHERE state IN ('running','pause_requested','cancel_requested') LIMIT 1").fetchone():
                    raise ValueError("another persistent worker is active")
        stamp=now()
        db.execute("INSERT INTO studio_evaluations VALUES (?,?,?,?,'running',NULL,NULL,?,?)",
                   (id,training_id,spec["version"],job["checkpoint_id"],stamp,stamp))
    try:
        dest=root/id
        dest.mkdir(parents=True,exist_ok=False)
        write_new(dest/"benchmark.json",benchmark)
        report=evaluate_fn(db_path,benchmark,checkpoint,spec["assets"],config=GenerationConfig(max_new_tokens=128))
        if (report.get("checkpoint_id")!=job["checkpoint_id"] or
            report.get("benchmark_id")!=benchmark["benchmark_id"] or report.get("release_ready") is not False or
            report.get("report_id")!=hash_json({k:v for k,v in report.items() if k!="report_id"})):
            raise ValueError("evaluation report identity mismatch")
        write_new(dest/"report.json",report)
        summary={k:report[k] for k in ("report_id","benchmark_id","metrics","coverage","automatic_gate_passed","failures","performance")}
        with closing(connect(db_path)) as db,db:
            changed=db.execute("UPDATE studio_evaluations SET state='complete',summary=?,updated=? WHERE id=? AND state='running'",
                (json.dumps(summary,allow_nan=False),now(),id)).rowcount
            if changed!=1:
                raise ValueError("evaluation ownership lost")
        return {"id":id,"state":"complete","report_id":report["report_id"],"release_ready":False}
    except (Exception,KeyboardInterrupt) as exc:
        with closing(connect(db_path)) as db,db:
            db.execute("UPDATE studio_evaluations SET state='failed',error=?,updated=? WHERE id=? AND state='running'",
                       (type(exc).__name__,now(),id))
        raise

def recover_evaluation(db_path,id,*,worker_stopped=False):
    if worker_stopped is not True or not re.fullmatch(r"[a-f0-9]{32}",id):
        raise ValueError("confirm original worker exited")
    with closing(connect(db_path)) as db,db:
        db.execute("BEGIN IMMEDIATE")
        initialize(db)
        if db.execute("UPDATE studio_evaluations SET state='interrupted',updated=? WHERE id=? AND state='running'",
                      (now(),id)).rowcount!=1:
            raise ValueError("no active evaluation record")
    return {"id":id,"state":"interrupted","release_ready":False}
