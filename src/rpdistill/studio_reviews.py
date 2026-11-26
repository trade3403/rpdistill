"""Local Studio Rust diagnostics and blinded review; never deployment approval."""
from contextlib import closing
from pathlib import Path
import json
import re
from uuid import uuid4
from .studio_evaluation import connect
from .studio_artifacts import source
from .training_queue import now
from .evaluation import read_json, read_jsonl, write_new, evaluate, hash_json
from .export_review import review_integration, check_integration_receipt
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
               executable=None,timeout_seconds=180,approved=False,artifact_id=None,reviewed_dataset=None,
               reviewed_teacher_license=None,reviewed_model_license=None,rights_note=None,reviewer=None,
               max_seconds=3600,training_limit=1000):
    if approved is not True or kind not in ("rust","blind","collect","integration","receipt-check"):
        raise ValueError("explicit diagnostic or review approval required")
    if type(timeout_seconds) is not int or not 1<=timeout_seconds<=900:
        raise ValueError("invalid timeout")
    if kind=="integration":
        collected=record(db_path,"studio_reviews",source_id)
        if collected["kind"]!="collect" or json.loads(collected["summary"]).get("candidate_gate_passed") is not True:
            raise ValueError("passed registered human review required")
        prior=record(db_path,"studio_reviews",collected["source_id"])
        artifact=record(db_path,"studio_artifacts",artifact_id)
        if prior["kind"]!="blind" or artifact["mode"]!="export" or artifact["evaluation_id"]!=prior["source_id"]:
            raise ValueError("artifact and human review must share exact evaluation")
        job,checkpoint,benchmark,student=source(db_path,prior["source_id"],eval_root)
        folder=Path(root)/prior["id"]
        baseline=read_json(folder/"baseline.json")
        packet=read_json(folder/"packet.json")
        key=read_json(folder/"private"/"key.json")
        pinned=json.loads(prior["summary"])
        if any(v!=pinned[k] for k,v in (("baseline_report",baseline.get("report_id")),("packet_id",packet.get("packet_id")),("key_id",key.get("key_id")))):
            raise ValueError("registered blind evidence mismatch")
        collected_root=Path(root)/source_id
        reviews=read_json(collected_root/"reviews.json")
        human=read_json(collected_root/"review.json")
        if (human.get("review_id")!=json.loads(collected["summary"]).get("review_id") or
            human.get("review_id")!=hash_json({k:v for k,v in human.items() if k!="review_id"}) or
            human.get("reviews_sha256")!=hash_json(reviews)):
            raise ValueError("registered human evidence mismatch")
        package_id=json.loads(artifact["summary"])["artifact_id"]
        package=Path(artifact_root)/artifact_id/"candidate"
        if not executable:
            raise ValueError("trusted local Rust bridge required")
        exe=Path(executable).resolve(strict=True)
        if not exe.is_file():
            raise ValueError("invalid Rust bridge")
        if reviewed_dataset!=job["spec"]["version"]:
            raise ValueError("exact dataset confirmation required")
        if not all(isinstance(v,str) and v.strip() for v in (reviewed_teacher_license,reviewed_model_license,rights_note,reviewer)):
            raise ValueError("explicit rights review required")
        if type(max_seconds) is not int or not 1<=max_seconds<=86400 or type(training_limit) is not int or not 1<=training_limit<=10000:
            raise ValueError("invalid review budget")
    elif kind=="receipt-check":
        prior=record(db_path,"studio_reviews",source_id)
        if prior["kind"]!="integration":
            raise ValueError("registered integration receipt required")
        pinned=json.loads(prior["summary"])
        artifact=record(db_path,"studio_artifacts",pinned["artifact_id"])
        package_id=pinned["package_id"]
        if artifact["mode"]!="export" or json.loads(artifact["summary"])["artifact_id"]!=package_id:
            raise ValueError("registered package pin mismatch")
        package=Path(artifact_root)/artifact["id"]/"candidate"
        receipt=read_json(Path(root)/source_id/"receipt.json")
    elif kind=="rust":
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
        if kind=="integration":
            exe_hash=digest_file(exe)
            receipt=review_integration(db_path,package,checkpoint,benchmark,student,baseline,packet,key,reviews,
                expected_package_id=package_id,reviewed_dataset=reviewed_dataset,
                reviewed_teacher_license=reviewed_teacher_license,reviewed_model_license=reviewed_model_license,
                rights_note=rights_note,reviewer=reviewer,executable=exe,
                acknowledge_local_candidate_only=True,training_limit=training_limit,max_cases=200,
                max_seconds=max_seconds,parity_timeout=timeout_seconds)
            if digest_file(exe)!=exe_hash or receipt.get("quality_review",{}).get("review_id")!=human["review_id"]:
                raise ValueError("integration evidence changed")
            check_integration_receipt(package,receipt,expected_package_id=package_id,expected_receipt_id=receipt["receipt_id"])
            write_new(out/"receipt.json",receipt)
            summary={"artifact_id":artifact_id,"package_id":package_id,"receipt_id":receipt["receipt_id"],
                "integration_passed":True,"executable_sha256":exe_hash}
        elif kind=="receipt-check":
            checked=check_integration_receipt(package,receipt,expected_package_id=package_id,
                expected_receipt_id=pinned["receipt_id"])
            write_new(out/"integrity.json",checked)
            summary={"package_id":package_id,"receipt_id":pinned["receipt_id"],
                "integrity_verified":True,"current_rights_revalidated":False}
        elif kind=="rust":
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
