"""Local Studio Rust diagnostics and blinded review; never deployment approval."""
from contextlib import closing
from pathlib import Path
import json
import re
from uuid import uuid4
from .studio_evaluation import connect
from .studio_artifacts import source
from .training_queue import now
from .evaluation import read_json, read_jsonl, write_new, evaluate
from .quality_review import create_blind_review, collect_review
from .rust_parity import rust_parity
from .rust_profile import rust_profile
from .model_export import verify_package
from .transfer import digest_file

def initialize(db):
    db.execute("""CREATE TABLE IF NOT EXISTS studio_reviews (
        id TEXT PRIMARY KEY,source_id TEXT NOT NULL,kind TEXT NOT NULL,
        state TEXT NOT NULL,summary TEXT,error TEXT,created TEXT NOT NULL,updated TEXT NOT NULL)""")

def record(db_path,table,id):
    if table not in ("studio_artifacts","studio_reviews"):
        raise ValueError("invalid record type")
    if not isinstance(id,str) or not re.fullmatch(r"[a-f0-9]{32}",id):
        raise ValueError("invalid registered ID")
    with closing(connect(db_path)) as db:
        row=db.execute("SELECT * FROM "+table+" WHERE id=?",(id,)).fetchone()
    if row is None or row["state"]!="complete":
        raise ValueError("completed registered record required")
    return dict(row)

def run_review(db_path,source_id,kind,eval_root,artifact_root,root,*,input_path=None,
               executable=None,timeout_seconds=180,approved=False):
    if approved is not True or kind not in ("rust","blind","collect"):
        raise ValueError("explicit diagnostic or review approval required")
    if type(timeout_seconds) is not int or not 1<=timeout_seconds<=900:
        raise ValueError("invalid timeout")
    if kind=="rust":
        artifact=record(db_path,"studio_artifacts",source_id)
        if artifact["mode"]!="export":
            raise ValueError("FP32 export required")
        package_id=json.loads(artifact["summary"])["artifact_id"]
        package=Path(artifact_root)/source_id/"candidate"
        job,_,_,_=source(db_path,artifact["evaluation_id"],eval_root)
        manifest=verify_package(package,expected_package_id=package_id)
        if manifest["origin"]["checkpoint_id"]!=job["checkpoint_id"]:
            raise ValueError("package source mismatch")
        if not executable:
            raise ValueError("trusted local Rust bridge required")
        exe=Path(executable).resolve(strict=True)
        if not exe.is_file():
            raise ValueError("invalid Rust bridge")
    elif kind=="blind":
        _,_,benchmark,student=source(db_path,source_id,eval_root)
        baseline=evaluate(db_path,benchmark,read_jsonl(input_path),label="external baseline")
    else:
        prior=record(db_path,"studio_reviews",source_id)
        if prior["kind"]!="blind":
            raise ValueError("registered blind packet required")
        _,_,benchmark,student=source(db_path,prior["source_id"],eval_root)
        folder=Path(root)/source_id
        baseline=read_json(folder/"baseline.json")
        packet=read_json(folder/"packet.json")
        key=read_json(folder/"private"/"key.json")
        pinned=json.loads(prior["summary"])
        if (packet.get("packet_id")!=pinned["packet_id"] or
            key.get("key_id")!=pinned["key_id"] or
            baseline.get("report_id")!=pinned["baseline_report"]):
            raise ValueError("registered blind packet identity mismatch")
        reviews=read_json(input_path)
    root=Path(root)
    if root.is_symlink():
        raise ValueError("symlink review root")
    id=uuid4().hex
    with closing(connect(db_path)) as db,db:
        db.execute("BEGIN IMMEDIATE")
        initialize(db)
        for table in ("studio_reviews","studio_artifacts","studio_evaluations","training_jobs","model_download_jobs","corpus_runs"):
            if db.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name=?",(table,)).fetchone():
                if db.execute("SELECT 1 FROM "+table+" WHERE state IN ('running','pause_requested','cancel_requested') LIMIT 1").fetchone():
                    raise ValueError("another persistent worker active or needs recovery")
        stamp=now()
        db.execute("INSERT INTO studio_reviews VALUES (?,?,?,'running',NULL,NULL,?,?)",(id,source_id,kind,stamp,stamp))
    try:
        out=root/id
        out.mkdir(parents=True,exist_ok=False)
        if kind=="rust":
            exe_hash=digest_file(exe)
            parity=rust_parity(package,expected_package_id=package_id,executable=exe,timeout_seconds=timeout_seconds)
            profile=rust_profile(package,expected_package_id=package_id,executable=exe,timeout_seconds=timeout_seconds)
            if (parity["diagnostic_passed"] is not True or parity["package_id"]!=package_id or
                profile["package_id"]!=package_id or profile["executable_sha256"]!=exe_hash or digest_file(exe)!=exe_hash or
                parity["weights_sha256"]!=manifest["files"]["weights.safetensors"]["sha256"] or
                profile["weights_sha256"]!=parity["weights_sha256"] or
                verify_package(package,expected_package_id=package_id)!=manifest):
                raise ValueError("diagnostic identity mismatch")
            write_new(out/"parity.json",parity)
            write_new(out/"profile.json",profile)
            summary={"package_id":package_id,"parity_passed":True,"parity_report":parity["report_id"],
                     "profile_report":profile["report_id"],"executable_sha256":exe_hash,
                     "cached_tokens_per_second":profile["cases"][0]["cached_tokens_per_second"],
                     "full_tokens_per_second":profile["cases"][0]["full_tokens_per_second"],
                     "rss_bytes":profile["rust_process_peak_rss_bytes"]}
        elif kind=="blind":
            packet,key=create_blind_review(db_path,benchmark,student,baseline)
            write_new(out/"private"/"key.json",key)
            write_new(out/"baseline.json",baseline)
            write_new(out/"packet.json",packet)
            summary={"packet_id":packet["packet_id"],"key_id":key["key_id"],
                     "baseline_report":baseline["report_id"],"cases":len(packet["cases"])}
        else:
            result=collect_review(db_path,benchmark,student,baseline,packet,key,reviews)
            write_new(out/"review.json",result)
            write_new(out/"reviews.json",reviews)
            summary={k:result[k] for k in ("review_id","reviewer_count","case_count","candidate_gate_passed","metrics","failures")}
        summary["release_ready"]=False
        with closing(connect(db_path)) as db,db:
            if db.execute("UPDATE studio_reviews SET state='complete',summary=?,updated=? WHERE id=? AND state='running'",
                          (json.dumps(summary,allow_nan=False),now(),id)).rowcount!=1:
                raise ValueError("review worker ownership lost")
        return {"id":id,"state":"complete","release_ready":False}
    except (Exception,KeyboardInterrupt) as exc:
        with closing(connect(db_path)) as db,db:
            db.execute("UPDATE studio_reviews SET state='failed',error=?,updated=? WHERE id=? AND state='running'",(type(exc).__name__,now(),id))
        raise

def recover_review(db_path,id,*,worker_stopped=False):
    if worker_stopped is not True or not re.fullmatch(r"[a-f0-9]{32}",id):
        raise ValueError("confirm original worker exited")
    with closing(connect(db_path)) as db,db:
        db.execute("BEGIN IMMEDIATE")
        initialize(db)
        if db.execute("UPDATE studio_reviews SET state='interrupted',updated=? WHERE id=? AND state='running'",(now(),id)).rowcount!=1:
            raise ValueError("no active review")
    return {"id":id,"state":"interrupted","release_ready":False}
