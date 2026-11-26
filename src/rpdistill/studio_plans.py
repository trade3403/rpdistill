"""Finite, explicitly authorized periodic corpus plans; no implicit training or replay."""
from contextlib import closing
from datetime import datetime, timezone, timedelta
import json
from pathlib import Path
import re
import sqlite3
from uuid import uuid4
from .pipeline import CorpusPipeline, stamp

def connect(path):
    db=sqlite3.connect(path,timeout=10)
    db.row_factory=sqlite3.Row
    return db

def initialize(db):
    db.execute("""CREATE TABLE IF NOT EXISTS studio_plans (
        id TEXT PRIMARY KEY,template_id TEXT NOT NULL,spec TEXT NOT NULL,license TEXT NOT NULL,
        interval_minutes INTEGER NOT NULL,max_cycles INTEGER NOT NULL,claimed INTEGER NOT NULL,
        state TEXT NOT NULL,active_run TEXT,next_due TEXT,error TEXT,updated TEXT NOT NULL)""")
    db.execute("""CREATE TABLE IF NOT EXISTS studio_plan_cycles (
        plan_id TEXT NOT NULL,cycle INTEGER NOT NULL,run_id TEXT NOT NULL UNIQUE,
        PRIMARY KEY(plan_id,cycle))""")

def valid_id(id):
    if not isinstance(id,str) or not re.fullmatch(r"[a-f0-9]{32}",id):
        raise ValueError("invalid plan or template ID")

def get(path,id):
    with closing(connect(path)) as db:
        row=db.execute("SELECT id,template_id,interval_minutes,max_cycles,claimed,state,active_run,next_due,error,updated FROM studio_plans WHERE id=?",(id,)).fetchone()
        if row is None:
            raise ValueError("unknown plan")
        return dict(row)

def teacher_license(db,spec):
    source=spec.get("source")
    if source not in ("huggingface","modelscope"):
        raise ValueError("invalid teacher source")
    table="teachers" if source=="huggingface" else "modelscope_teachers"
    row=db.execute("SELECT record FROM "+table+" WHERE model_id=? AND revision=?",(spec["model_id"],spec["revision"])).fetchone()
    if row is None:
        raise ValueError("teacher unavailable")
    record=json.loads(row[0])
    if record.get("private") or record.get("gated"):
        raise ValueError("restricted teacher")
    return record.get("license")

def create(path,template_id,license,interval_minutes,max_cycles,total_bytes,*,approved=False):
    valid_id(template_id)
    if approved is not True or not isinstance(license,str) or not license.strip() or len(license)>100:
        raise ValueError("explicit plan rights and budget approval required")
    if type(interval_minutes) is not int or not 5<=interval_minutes<=10080 or type(max_cycles) is not int or not 1<=max_cycles<=10:
        raise ValueError("invalid schedule bounds")
    if type(total_bytes) is not int or not 1<=total_bytes<=2**40:
        raise ValueError("invalid total authorized payload")
    template=CorpusPipeline(path).get(template_id)
    spec=template["spec"]
    if template["state"] not in ("queued","candidate_complete","insufficient_candidates") or not spec["query"]["open_access_only"]:
        raise ValueError("eligible fixed corpus template required")
    if type(spec["max_bytes"]) is not int or not 1<=spec["max_bytes"]<=2**40 or spec["max_bytes"]*max_cycles!=total_bytes:
        raise ValueError("exact total payload authorization required")
    id=uuid4().hex
    with closing(connect(path)) as db,db:
        db.execute("BEGIN IMMEDIATE")
        initialize(db)
        if db.execute("SELECT 1 FROM studio_plan_cycles WHERE run_id=?",(template_id,)).fetchone():
            raise ValueError("scheduled child is not a reusable template")
        if teacher_license(db,spec)!=license:
            raise ValueError("teacher license changed")
        db.execute("INSERT INTO studio_plans VALUES (?,?,?,?,?,?,0,'ready',NULL,?,NULL,?)",
                   (id,template_id,json.dumps(spec,allow_nan=False),license,interval_minutes,max_cycles,stamp(),stamp()))
    return get(path,id)

def tick(path,id,*,approved=False,run=None,clock=None):
    valid_id(id)
    if approved is not True:
        raise ValueError("explicit scheduler authorization required")
    clock=clock or (lambda: datetime.now(timezone.utc))
    engine=CorpusPipeline(path)
    with closing(connect(path)) as db,db:
        db.execute("BEGIN IMMEDIATE")
        initialize(db)
        row=db.execute("SELECT * FROM studio_plans WHERE id=?",(id,)).fetchone()
        if row is None or row["state"]!="ready":
            raise ValueError("plan not ready")
        if datetime.fromisoformat(row["next_due"])>clock():
            return {"id":id,"state":"waiting","next_due":row["next_due"]}
        if row["claimed"]>=row["max_cycles"]:
            raise ValueError("cycle budget exhausted")
        for table in ("studio_plans","corpus_runs","training_jobs","model_download_jobs","studio_evaluations","studio_artifacts","studio_reviews"):
            if db.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name=?",(table,)).fetchone() and db.execute("SELECT 1 FROM "+table+" WHERE state IN ('running','pause_requested','cancel_requested') LIMIT 1").fetchone():
                raise ValueError("another persistent worker is active")
        spec=json.loads(row["spec"])
        if teacher_license(db,spec)!=row["license"]:
            raise ValueError("teacher license changed")
        child=uuid4().hex
        cycle=row["claimed"]+1
        # Reserve the entire cycle, even if killed before search or download.
        db.execute("INSERT INTO corpus_runs VALUES (?,?,'queued',0,'{}',NULL,?)",(child,row["spec"],stamp()))
        db.execute("INSERT INTO studio_plan_cycles VALUES (?,?,?)",(id,cycle,child))
        db.execute("UPDATE studio_plans SET state='running',claimed=?,active_run=?,updated=? WHERE id=?",(cycle,child,stamp(),id))
    try:
        result=(run or engine.run)(child,plan_id=id)
        # Read committed state, not a success assertion from subprocess/callback.
        actual=engine.get(child)
        if result["id"]!=child or result["state"]!=actual["state"] or actual["state"] not in ("candidate_complete","insufficient_candidates","failed","interrupted"):
            raise ValueError("cycle identity mismatch")
        state=("complete" if cycle==row["max_cycles"] else "ready") if actual["state"]=="candidate_complete" else "stopped"
        error=None if state in ("ready","complete") else str(actual["state"])
        due=(clock()+timedelta(minutes=row["interval_minutes"])).isoformat() if state=="ready" else None
        with closing(connect(path)) as db,db:
            if db.execute("UPDATE studio_plans SET state=?,active_run=NULL,next_due=?,error=?,updated=? WHERE id=? AND state='running' AND active_run=?",
                          (state,due,error,stamp(),id,child)).rowcount!=1:
                raise ValueError("plan ownership lost")
        return get(path,id)
    except (Exception,KeyboardInterrupt):
        # Keep running ownership for explicit recovery; no automatic replay.
        raise

def recover(path,id,*,worker_stopped=False):
    valid_id(id)
    if worker_stopped is not True:
        raise ValueError("confirm original worker exited")
    with closing(connect(path)) as db,db:
        db.execute("BEGIN IMMEDIATE")
        initialize(db)
        row=db.execute("SELECT active_run FROM studio_plans WHERE id=? AND state='running'",(id,)).fetchone()
        if row is None:
            raise ValueError("no interrupted plan")
        db.execute("UPDATE corpus_runs SET state='interrupted',error='PlanWorkerInterrupted',updated=? WHERE id=? AND state IN ('queued','running')",(stamp(),row[0]))
        db.execute("UPDATE studio_plans SET state='stopped',active_run=NULL,next_due=NULL,error='PlanWorkerInterrupted',updated=? WHERE id=?",(stamp(),id))
    return get(path,id)

def cancel(path,id,*,approved=False):
    valid_id(id)
    if approved is not True:
        raise ValueError("explicit plan cancellation required")
    with closing(connect(path)) as db,db:
        db.execute("BEGIN IMMEDIATE")
        initialize(db)
        if db.execute("UPDATE studio_plans SET state='cancelled',next_due=NULL,updated=? WHERE id=? AND state='ready'",(stamp(),id)).rowcount!=1:
            raise ValueError("only idle ready plan can be cancelled")
    return get(path,id)
