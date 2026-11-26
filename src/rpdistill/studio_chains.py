"""Explicit post-training evaluation, regression and FP32 candidate export."""
from contextlib import closing
import json
import re
from uuid import uuid4
from .studio_evaluation import connect,evaluate_job
from .studio_artifacts import run_artifact
from .studio_chain_state import initialize
from .training_queue import TrainingQueue,linked_candidate,now
from .compression import plan,OVERHEAD
from .model_export import REQUIRED_BYTES

def get(path,id):
    with closing(connect(path)) as db:
        row=db.execute("SELECT * FROM studio_chains WHERE id=?",(id,)).fetchone()
        if row is None:
            raise ValueError("unknown chain")
        result=dict(row)
        result.pop("spec")
        return result|{"release_ready":False}

def advance(path,id,stage,child_result,*,mode=None):
    """Use the committed child record, not just its return code."""
    column={"evaluation":"evaluation_id","compression":"compression_id","export":"export_id"}[stage]
    table="studio_evaluations" if stage=="evaluation" else "studio_artifacts"
    with closing(connect(path)) as db,db:
        db.execute("BEGIN IMMEDIATE")
        r=db.execute("SELECT * FROM studio_chains WHERE id=? AND state='running' AND stage=?",(id,stage)).fetchone()
        if not r or child_result.get("id")!=r[column] or child_result.get("release_ready") is not False:
            raise ValueError("chain result identity mismatch")
        c=db.execute("SELECT * FROM "+table+" WHERE id=?",(r[column],)).fetchone()
        if not c or c["state"]!="complete":
            raise ValueError("chain child not complete")
        summary=json.loads(c["summary"])
        if stage=="evaluation":
            if (c["training_id"],c["version"],c["checkpoint_id"])!=(r["training_id"],r["version"],r["checkpoint_id"]):
                raise ValueError("evaluation source mismatch")
            passed=summary.get("automatic_gate_passed") is True
        else:
            if c["evaluation_id"]!=r["evaluation_id"] or c["mode"]!=mode or summary.get("release_ready") is not False:
                raise ValueError("candidate source mismatch")
            passed=summary.get("verified") is True and (stage=="export" or summary.get("regression_passed") is True)
        target="stopped" if not passed else "complete" if stage=="export" else "running"
        next_stage={"evaluation":"compression","compression":"export","export":"done"}[stage] if passed else stage
        db.execute("UPDATE studio_chains SET state=?,stage=?,error=?,updated=? WHERE id=?",
            (target,next_stage,None if passed else stage+"_gate_not_passed",now(),id))
    return passed

def run_chain(path,training_id,input_path,eval_root,artifact_root,*,review_note,mode,
              compression_bytes,export_bytes,max_seconds,license_label,rights_note,approved=False):
    if approved is not True or not isinstance(training_id,str) or not re.fullmatch(r"[a-f0-9]{32}",training_id):
        raise ValueError("explicit chain approval required")
    if mode not in ("fp16","int8"):
        raise ValueError("invalid compression mode")
    for v,lo,hi in ((compression_bytes,plan(mode)["payload_bytes"]+OVERHEAD,2**40),
                    (export_bytes,REQUIRED_BYTES,2**40),(max_seconds,1,86400)):
        if type(v) is not int or not lo<=v<=hi:
            raise ValueError("invalid chain budget")
    for v,maxlen in ((review_note,2000),(license_label,128),(rights_note,2000)):
        if not isinstance(v,str) or not v.strip() or len(v)>maxlen or any(ord(c)<32 or ord(c)==127 for c in v):
            raise ValueError("explicit reference and candidate rights review required")
    q=TrainingQueue(path)
    id=uuid4().hex
    with q.write() as db:
        initialize(db)
        job=q._get(db,training_id)
        spec=job["spec"]
        if job["state"]!="complete" or not job["checkpoint"] or not job["checkpoint_id"] or not spec.get("corpus_run"):
            raise ValueError("completed linked training required")
        link=db.execute("SELECT * FROM studio_training_links WHERE job_id=?",(training_id,)).fetchone()
        if not link or link["version"]!=spec["version"] or link["run_id"]!=spec["corpus_run"] or link["license"]!=spec["reviewed_teacher_license"] or link["review_note"]!=spec["review_note"]:
            raise ValueError("registered training link mismatch")
        linked_candidate(db,spec["corpus_run"],spec["version"],spec["reviewed_teacher_license"])
        for table in ("studio_chains","studio_plans","corpus_runs","training_jobs","model_download_jobs","studio_evaluations","studio_artifacts","studio_reviews"):
            if db.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name=?",(table,)).fetchone() and db.execute("SELECT 1 FROM "+table+" WHERE state IN ('running','pause_requested','cancel_requested') LIMIT 1").fetchone():
                raise ValueError("another persistent worker active or needs recovery")
        if db.execute("SELECT 1 FROM studio_chains WHERE checkpoint_id=? AND state='complete'",(job["checkpoint_id"],)).fetchone():
            raise ValueError("checkpoint already has a completed chain")
        stamp=now()
        settings=dict(mode=mode,compression_bytes=compression_bytes,export_bytes=export_bytes,max_seconds=max_seconds,
                      review_note=review_note,license_label=license_label,rights_note=rights_note)
        db.execute("INSERT INTO studio_chains VALUES (?,?,?,?,?,'running','evaluation',NULL,NULL,NULL,NULL,?,?)",
            (id,training_id,spec["version"],job["checkpoint_id"],json.dumps(settings,allow_nan=False),stamp,stamp))
    try:
        result=evaluate_job(path,training_id,input_path,eval_root,review_note,approved=True,chain_id=id)
        if not advance(path,id,"evaluation",result):
            return get(path,id)
        eid=result["id"]
        result=run_artifact(path,eid,mode,eval_root,artifact_root,max_bytes=compression_bytes,max_seconds=max_seconds,approved=True,chain_id=id)
        if not advance(path,id,"compression",result,mode=mode):
            return get(path,id)
        result=run_artifact(path,eid,"export",eval_root,artifact_root,max_bytes=export_bytes,license_label=license_label,
                            rights_note=rights_note,approved=True,chain_id=id)
        advance(path,id,"export",result,mode="export")
        return get(path,id)
    except (Exception,KeyboardInterrupt) as exc:
        with closing(connect(path)) as db,db:
            # If a child is still running, retain ownership for explicit recovery.
            r=db.execute("SELECT * FROM studio_chains WHERE id=?",(id,)).fetchone()
            column,table={"evaluation":("evaluation_id","studio_evaluations"),"compression":("compression_id","studio_artifacts"),"export":("export_id","studio_artifacts")}.get(r["stage"],("export_id","studio_artifacts"))
            active=r[column] and db.execute("SELECT 1 FROM "+table+" WHERE id=? AND state='running'",(r[column],)).fetchone()
            if not active:
                db.execute("UPDATE studio_chains SET state='failed',error=?,updated=? WHERE id=? AND state='running'",(type(exc).__name__,now(),id))
        raise

def recover(path,id,*,worker_stopped=False):
    if worker_stopped is not True or not isinstance(id,str) or not re.fullmatch(r"[a-f0-9]{32}",id):
        raise ValueError("confirm original chain and child stopped")
    with closing(connect(path)) as db,db:
        db.execute("BEGIN IMMEDIATE")
        initialize(db)
        r=db.execute("SELECT * FROM studio_chains WHERE id=? AND state='running'",(id,)).fetchone()
        if not r:
            raise ValueError("no interrupted chain")
        for col,table in (("evaluation_id","studio_evaluations"),("compression_id","studio_artifacts"),("export_id","studio_artifacts")):
            if r[col]:
                db.execute("UPDATE "+table+" SET state='interrupted',error='ChainWorkerInterrupted',updated=? WHERE id=? AND state='running'",(now(),r[col]))
        db.execute("UPDATE studio_chains SET state='interrupted',error='ChainWorkerInterrupted',updated=? WHERE id=?",(now(),id))
    return get(path,id)
