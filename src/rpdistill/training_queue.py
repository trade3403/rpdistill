"""Persistent segmented training queue. One active worker per database.

The worker reserves each attempt's time and checkpoint allocation BEFORE execution.
Reservations are never refunded (including failures/crashes). Soft time/VRAM bounds
are not a process-level resource sandbox. Existing checkpoints are never deleted.
"""
from contextlib import closing,contextmanager
from dataclasses import asdict
from datetime import datetime,timezone
import json
import math
from pathlib import Path
import re
import sqlite3
from uuid import uuid4

from .distill import DistillConfig,prepare_reviewed_snapshot
from .resumable import ResumeConfig,required_bytes,run_segment,hash_json,SCHEMA,MANIFEST_LIMIT
from .student import FIXED,StudentProfile
from .transfer import digest_file

ACTIVE=("running","pause_requested","cancel_requested")


def now():
    return datetime.now(timezone.utc).isoformat()


def bounded(value,low,high,name):
    if type(value) is not int or not low<=value<=high:
        raise ValueError("invalid "+name)
    return value


def read_config(spec):
    raw=dict(spec["config"])
    raw["training"]=DistillConfig(**raw["training"])
    return ResumeConfig(**raw)


def verified_checkpoint(path,profile,previous_step,target_steps):
    """Validate local publication identity before advancing the durable cursor."""
    root=Path(path)
    meta=root/"manifest.json"
    weights=root/"training.safetensors"
    if root.is_symlink() or any(p.is_symlink() or not p.is_file() for p in (meta,weights)):
        raise ValueError("invalid checkpoint files")
    if meta.stat().st_size>MANIFEST_LIMIT:
        raise ValueError("manifest too large")
    m=json.loads(meta.read_text(encoding="utf-8"))
    if (m.get("schema")!=SCHEMA or m.get("checkpoint_id")!=hash_json({k:v for k,v in m.items() if k!="checkpoint_id"})
        or m.get("profile")!=asdict(profile) or m.get("optimizer_saved") is not True
        or m.get("resume_boundary")!="optimizer_step"):
        raise ValueError("invalid checkpoint manifest")
    step=m.get("step")
    if type(step) is not int or not previous_step<step<=target_steps:
        raise ValueError("invalid checkpoint progress")
    if m.get("status")!=("complete" if step==target_steps else "paused"):
        raise ValueError("invalid checkpoint status")
    size=weights.stat().st_size
    if size!=m["tensors"]["bytes"] or size>required_bytes(profile) or digest_file(weights)!=m["tensors"]["sha256"]:
        raise ValueError("checkpoint hash mismatch")
    return m,size+meta.stat().st_size


class TrainingQueue:
    def __init__(self,db_path):
        self.path=Path(db_path).resolve()
        self.path.parent.mkdir(parents=True,exist_ok=True)
        with self.write() as db:
            db.execute("""CREATE TABLE IF NOT EXISTS training_jobs (
                id TEXT PRIMARY KEY,spec TEXT NOT NULL,state TEXT NOT NULL,
                step INTEGER NOT NULL DEFAULT 0,attempt INTEGER NOT NULL DEFAULT 0,
                reserved_seconds INTEGER NOT NULL DEFAULT 0,reserved_bytes INTEGER NOT NULL DEFAULT 0,
                checkpoint TEXT,checkpoint_id TEXT,error TEXT,created TEXT NOT NULL,updated TEXT NOT NULL)""")
            db.execute("""CREATE TABLE IF NOT EXISTS training_step_metrics (
                job_id TEXT NOT NULL,attempt INTEGER NOT NULL,step INTEGER NOT NULL,
                loss REAL NOT NULL,seconds REAL NOT NULL,tokens INTEGER NOT NULL,
                committed INTEGER NOT NULL DEFAULT 0,created TEXT NOT NULL,
                PRIMARY KEY(job_id,attempt,step))""")
            db.execute("""CREATE TABLE IF NOT EXISTS training_events (
                seq INTEGER PRIMARY KEY AUTOINCREMENT,job_id TEXT NOT NULL,
                state TEXT NOT NULL,detail TEXT NOT NULL,created TEXT NOT NULL)""")

    def connect(self):
        db=sqlite3.connect(self.path,timeout=10)
        db.row_factory=sqlite3.Row
        return db

    @contextmanager
    def write(self):
        with closing(self.connect()) as db,db:
            db.execute("BEGIN IMMEDIATE")
            yield db

    def _get(self,db,id):
        row=db.execute("SELECT * FROM training_jobs WHERE id=?",(id,)).fetchone()
        if row is None:
            raise KeyError("unknown training job")
        result=dict(row)
        result["spec"]=json.loads(result["spec"])
        return result

    def get(self,id):
        with closing(self.connect()) as db:
            return self._get(db,id)

    def list(self,limit=100):
        bounded(limit,1,1000,"list limit")
        with closing(self.connect()) as db:
            return [self._get(db,r[0]) for r in db.execute("SELECT id FROM training_jobs ORDER BY created,id LIMIT ?",(limit,))]

    def events(self,id,limit=100):
        bounded(limit,1,1000,"event limit")
        with closing(self.connect()) as db:
            self._get(db,id)
            rows=db.execute("SELECT * FROM training_events WHERE job_id=? ORDER BY seq DESC LIMIT ?",(id,limit))
            return [dict(r)|{"detail":json.loads(r["detail"])} for r in rows]

    def event(self,db,id,state,**detail):
        db.execute("INSERT INTO training_events(job_id,state,detail,created) VALUES (?,?,?,?)",
                   (id,state,json.dumps(detail,allow_nan=False),now()))

    def state(self,db,id,state,error=None,**detail):
        db.execute("UPDATE training_jobs SET state=?,error=?,updated=? WHERE id=?",(state,error,now(),id))
        self.event(db,id,state,error=error,**detail)

    def enqueue(self,version,assets,root,*,reviewed_dataset,reviewed_teacher_license,
                config=ResumeConfig(),limit=1000,segment_steps=20,segment_seconds=300,
                total_seconds,max_checkpoint_bytes=2**30,total_checkpoint_bytes):
        if not isinstance(config,ResumeConfig):
            raise ValueError("invalid config")
        if not isinstance(version,str) or not re.fullmatch(r"[a-f0-9]{64}",version) or reviewed_dataset!=version:
            raise ValueError("explicit exact version review required")
        if not isinstance(reviewed_teacher_license,str) or not reviewed_teacher_license.strip():
            raise ValueError("teacher license review required")
        bounded(limit,1,10000,"example limit")
        bounded(segment_steps,1,10000,"segment steps")
        bounded(segment_seconds,1,86400,"segment seconds")
        bounded(total_seconds,segment_seconds,31_536_000,"total seconds")
        bounded(max_checkpoint_bytes,required_bytes(FIXED),2**40,"checkpoint size")
        bounded(total_checkpoint_bytes,max_checkpoint_bytes,2**44,"total checkpoint size")
        # Authorization is rechecked on every segment, not just when enqueued.
        spec=dict(version=version,assets=str(Path(assets).resolve()),root=str(Path(root).resolve()),
                  reviewed_dataset=reviewed_dataset,reviewed_teacher_license=reviewed_teacher_license,
                  config=asdict(config),limit=limit,segment_steps=segment_steps,segment_seconds=segment_seconds,
                  total_seconds=total_seconds,max_checkpoint_bytes=max_checkpoint_bytes,
                  total_checkpoint_bytes=total_checkpoint_bytes)
        raw=json.dumps(spec,sort_keys=True,allow_nan=False)
        with self.write() as db:
            existing=db.execute("""SELECT id FROM training_jobs WHERE spec=? AND
                state IN ('queued','running','pause_requested','cancel_requested','paused','failed','interrupted')""",(raw,)).fetchone()
            if existing:
                return self._get(db,existing[0])
            id=uuid4().hex
            stamp=now()
            db.execute("INSERT INTO training_jobs(id,spec,state,created,updated) VALUES (?,?,'queued',?,?)",(id,raw,stamp,stamp))
            self.event(db,id,"queued")
            return self._get(db,id)

    def control(self,id,action):
        changes={"pause":{"queued":"paused","running":"pause_requested"},
                 "cancel":{"queued":"cancelled","running":"cancel_requested","pause_requested":"cancel_requested",
                           "paused":"cancelled","failed":"cancelled","interrupted":"cancelled","budget_exhausted":"cancelled"},
                 "resume":{"paused":"queued","failed":"queued","interrupted":"queued"}}
        with self.write() as db:
            row=self._get(db,id)
            target=changes.get(action,{}).get(row["state"])
            if target is None:
                raise ValueError("invalid training job transition")
            self.state(db,id,target)
            return self._get(db,id)

    def recover(self,id,*,worker_stopped=False):
        if worker_stopped is not True:
            raise ValueError("confirm previous worker stopped")
        with self.write() as db:
            row=self._get(db,id)
            if row["state"] not in ACTIVE:
                raise ValueError("job not active")
            target={"running":"interrupted","pause_requested":"paused","cancel_requested":"cancelled"}[row["state"]]
            self.state(db,id,target,orphan_attempt=row["attempt"],
                       note="unregistered files retained; previous committed checkpoint remains authoritative")
            return self._get(db,id)

    def record_step(self,id,attempt,metric,seconds):
        step,loss,tokens=metric["step"],metric["loss"],metric["supervised_tokens"]
        if (type(step) is not int or type(tokens) is not int or tokens<=0
            or type(loss) not in (int,float) or not math.isfinite(loss) or loss<0
            or type(seconds) not in (int,float) or not math.isfinite(seconds) or seconds<=0):
            raise ValueError("invalid step telemetry")
        with self.write() as db:
            row=self._get(db,id)
            if row["attempt"]!=attempt or row["state"] not in ACTIVE:
                raise ValueError("worker ownership lost")
            if not row["step"]<step<=min(row["spec"]["config"]["training"]["steps"],
                                         row["step"]+row["spec"]["segment_steps"]):
                raise ValueError("invalid telemetry step")
            last=db.execute("SELECT max(step) FROM training_step_metrics WHERE job_id=? AND attempt=?",(id,attempt)).fetchone()[0]
            if step!=(last if last is not None else row["step"])+1:
                raise ValueError("nonsequential telemetry")
            db.execute("INSERT INTO training_step_metrics VALUES (?,?,?,?,?,?,0,?)",
                       (id,attempt,step,loss,seconds,tokens,now()))

    def run_next(self,*,prepare=prepare_reviewed_snapshot,execute=run_segment,profile=FIXED,max_segments=1000):
        bounded(max_segments,1,1000,"worker segment limit")
        with self.write() as db:
            if db.execute("SELECT 1 FROM training_jobs WHERE state IN ('running','pause_requested','cancel_requested') LIMIT 1").fetchone():
                raise ValueError("another training worker owns the queue")
            row=db.execute("SELECT id FROM training_jobs WHERE state='queued' ORDER BY created,id LIMIT 1").fetchone()
            if row is None:
                return None
            id=row[0]
            self.state(db,id,"running")
        for _ in range(max_segments):
            with self.write() as db:
                row=self._get(db,id)
                spec=row["spec"]
                if row["state"] in ("pause_requested","cancel_requested"):
                    self.state(db,id,"paused" if row["state"]=="pause_requested" else "cancelled")
                    return self._get(db,id)
                if row["state"]!="running":
                    raise ValueError("worker ownership lost")
                remaining=spec["total_seconds"]-row["reserved_seconds"]
                seconds=min(spec["segment_seconds"],remaining)
                size=spec["max_checkpoint_bytes"]
                if seconds<=0 or row["reserved_bytes"]+size>spec["total_checkpoint_bytes"]:
                    self.state(db,id,"budget_exhausted")
                    return self._get(db,id)
                # Uncommitted observations from earlier attempts are not resumable progress.
                db.execute("DELETE FROM training_step_metrics WHERE job_id=? AND committed=0",(id,))
                attempt=row["attempt"]+1
                db.execute("""UPDATE training_jobs SET attempt=?,reserved_seconds=reserved_seconds+?,
                    reserved_bytes=reserved_bytes+?,updated=? WHERE id=?""",(attempt,seconds,size,now(),id))
                self.event(db,id,"running",attempt=attempt,reserved_seconds=seconds,reserved_bytes=size)
            try:
                config=read_config(spec)
                root=Path(spec["root"])/id
                if root.is_symlink():
                    raise ValueError("symlink job root")
                root.mkdir(parents=True,exist_ok=True)
                destination=root/("attempt-%08d"%attempt)
                if row["checkpoint"]:
                    prior=Path(row["checkpoint"])
                    if prior.parent!=root:
                        raise ValueError("invalid prior checkpoint path")
                    previous,_=verified_checkpoint(prior,profile,row["step"]-1,config.training.steps)
                    if previous["checkpoint_id"]!=row["checkpoint_id"] or previous["step"]!=row["step"]:
                        raise ValueError("prior checkpoint identity mismatch")
                examples,provenance=prepare(self.path,spec["version"],spec["assets"],
                    reviewed_dataset=spec["reviewed_dataset"],
                    reviewed_teacher_license=spec["reviewed_teacher_license"],limit=spec["limit"])
                result=execute(examples,destination,config=config,profile=profile,provenance=provenance,
                    resume=row["checkpoint"],run_steps=spec["segment_steps"],max_seconds=seconds,
                    max_checkpoint_bytes=size,should_stop=lambda:self.get(id)["state"]!="running",
                    on_step=lambda metric,seconds:self.record_step(id,attempt,metric,seconds))
                m,actual=verified_checkpoint(destination,profile,row["step"],config.training.steps)
                if (m["checkpoint_id"]!=result.get("checkpoint_id") or actual>size
                    or m["step"]>row["step"]+spec["segment_steps"]):
                    raise ValueError("unexpected segment result")
                with self.write() as db:
                    latest=self._get(db,id)
                    if latest["attempt"]!=attempt or latest["state"] not in ACTIVE:
                        raise ValueError("worker ownership lost")
                    db.execute("UPDATE training_jobs SET step=?,checkpoint=?,checkpoint_id=?,updated=? WHERE id=?",
                               (m["step"],str(destination),m["checkpoint_id"],now(),id))
                    db.execute("UPDATE training_step_metrics SET committed=1 WHERE job_id=? AND attempt=? AND step<=?",
                               (id,attempt,m["step"]))
                    target=("complete" if m["status"]=="complete" else
                        "cancelled" if latest["state"]=="cancel_requested" else
                        "paused" if latest["state"]=="pause_requested" or m["stop_reason"]=="cuda_allocation_budget_boundary" else
                        "running")
                    # Only publish measured loss from the newly verified, committed checkpoint.
                    # Older or synthetic checkpoints without a valid history have no telemetry.
                    history=m.get("history")
                    last=history[-1] if isinstance(history,list) and history else None
                    metric={}
                    if isinstance(last,dict) and last.get("step")==m["step"]:
                        loss=last.get("loss")
                        if type(loss) in (int,float) and math.isfinite(loss) and loss>=0:
                            metric["loss"]=loss
                    self.state(db,id,target,step=m["step"],actual_bytes=actual,stop_reason=m["stop_reason"],**metric)
                    if target!="running":
                        return self._get(db,id)
            except (Exception,KeyboardInterrupt) as exc:
                with self.write() as db:
                    latest=self._get(db,id)
                    if latest["attempt"]==attempt and latest["state"] in ACTIVE:
                        target=("cancelled" if latest["state"]=="cancel_requested" else
                            "paused" if latest["state"]=="pause_requested" else
                            "interrupted" if isinstance(exc,KeyboardInterrupt) else "failed")
                        self.state(db,id,target,error=type(exc).__name__,attempt=attempt)
                    return self._get(db,id)
        with self.write() as db:
            row=self._get(db,id)
            if row["state"] in ACTIVE:
                target={"running":"queued","pause_requested":"paused","cancel_requested":"cancelled"}[row["state"]]
                self.state(db,id,target,reason="worker segment limit")
            return self._get(db,id)
