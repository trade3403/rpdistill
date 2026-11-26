"""Local candidate operations bound to a completed registered evaluation."""
from contextlib import closing
from pathlib import Path
import json
import re
from uuid import uuid4
from .studio_evaluation import connect
from .training_queue import TrainingQueue, now
from .evaluation import read_json, write_new, hash_json, validate_benchmark, QualityGate
from .compression import create_candidate, plan, OVERHEAD
from .compression_review import compare_candidates
from .model_export import export_candidate, verify_package, REQUIRED_BYTES
from .student_evaluation import GenerationConfig

def initialize(db):
    db.execute("""CREATE TABLE IF NOT EXISTS studio_artifacts (
        id TEXT PRIMARY KEY,evaluation_id TEXT NOT NULL,mode TEXT NOT NULL,
        state TEXT NOT NULL,summary TEXT,error TEXT,created TEXT NOT NULL,updated TEXT NOT NULL)""")

def source(db_path,eval_id,eval_root):
    if not isinstance(eval_id,str) or not re.fullmatch(r"[a-f0-9]{32}",eval_id):
        raise ValueError("invalid evaluation ID")
    with closing(connect(db_path)) as db:
        row=db.execute("SELECT * FROM studio_evaluations WHERE id=?",(eval_id,)).fetchone()
    if row is None or row["state"]!="complete":
        raise ValueError("completed evaluation required")
    summary=json.loads(row["summary"])
    folder=Path(eval_root)/eval_id
    if folder.is_symlink():
        raise ValueError("symlink evaluation directory")
    report=read_json(folder/"report.json")
    benchmark=validate_benchmark(db_path,read_json(folder/"benchmark.json"))
    if (report.get("report_id")!=summary.get("report_id") or
        report.get("report_id")!=hash_json({k:v for k,v in report.items() if k!="report_id"}) or
        report.get("checkpoint_id")!=row["checkpoint_id"] or
        report.get("benchmark_id")!=benchmark["benchmark_id"] or
        report.get("training_dataset")!=row["version"] or
        report.get("automatic_gate_passed") is not True or
        report.get("release_ready") is not False or
        report.get("model_output_generated_locally") is not True or
        report.get("generation_failures")!=[]):
        raise ValueError("verified local automatic evaluation pass required")
    from dataclasses import asdict
    if report.get("gate")!=asdict(QualityGate()):
        raise ValueError("default quality gate required")
    job=TrainingQueue(db_path).get(row["training_id"])
    if job["state"]!="complete" or job["checkpoint_id"]!=row["checkpoint_id"] or job["spec"]["version"]!=row["version"]:
        raise ValueError("registered checkpoint no longer matches evaluation")
    checkpoint=Path(job["checkpoint"])
    if checkpoint.is_symlink() or checkpoint.parent!=Path(job["spec"]["root"])/job["id"]:
        raise ValueError("invalid registered checkpoint path")
    manifest=read_json(checkpoint/"manifest.json")
    if manifest.get("checkpoint_id")!=row["checkpoint_id"] or hash_json({k:v for k,v in manifest.items() if k!="checkpoint_id"})!=row["checkpoint_id"]:
        raise ValueError("checkpoint identity mismatch")
    return job,checkpoint,benchmark,report

def run_artifact(db_path,eval_id,mode,eval_root,root,*,max_bytes,max_seconds=3600,
                 license_label="",rights_note="",approved=False):
    if approved is not True or mode not in ("fp32","fp16","int8","export"):
        raise ValueError("explicit local candidate approval required")
    minimum=REQUIRED_BYTES if mode=="export" else plan(mode)["payload_bytes"]+OVERHEAD
    if type(max_bytes) is not int or not minimum<=max_bytes<=2**40:
        raise ValueError("candidate byte budget too small")
    if type(max_seconds) is not int or not 1<=max_seconds<=86400:
        raise ValueError("invalid comparison time budget")
    if mode=="export":
        if not license_label.strip() or not rights_note.strip():
            raise ValueError("explicit operator rights note required")
    job,checkpoint,benchmark,report=source(db_path,eval_id,eval_root)
    root=Path(root)
    if root.is_symlink():
        raise ValueError("symlink artifact root")
    id=uuid4().hex
    with closing(connect(db_path)) as db,db:
        db.execute("BEGIN IMMEDIATE")
        initialize(db)
        for table in ("studio_artifacts","studio_evaluations","training_jobs","model_download_jobs","corpus_runs"):
            if db.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name=?",(table,)).fetchone():
                if db.execute("SELECT 1 FROM "+table+" WHERE state IN ('running','pause_requested','cancel_requested') LIMIT 1").fetchone():
                    raise ValueError("another persistent worker active or needs recovery")
        stamp=now()
        db.execute("INSERT INTO studio_artifacts VALUES (?,?,?,'running',NULL,NULL,?,?)",(id,eval_id,mode,stamp,stamp))
    try:
        folder=root/id
        folder.mkdir(parents=True,exist_ok=False)
        if mode=="export":
            result=export_candidate(checkpoint,job["spec"]["assets"],folder/"candidate",dataset_version=job["spec"]["version"],
                license_label=license_label,rights_note=rights_note,max_bytes=max_bytes,acknowledge_candidate_only=True)
            verified=verify_package(folder/"candidate",expected_package_id=result["package_id"])
            if verified["origin"]["checkpoint_id"]!=job["checkpoint_id"]:
                raise ValueError("export source identity mismatch")
            summary={"artifact_id":verified["package_id"],"bytes":sum(v["bytes"] for v in verified["files"].values())+(folder/"candidate"/"manifest.json").stat().st_size,
                     "verified":True,"regression_passed":None,"release_ready":False}
        else:
            result=create_candidate(checkpoint,folder/"candidate",dataset_version=job["spec"]["version"],mode=mode,max_bytes=max_bytes)
            comparison=compare_candidates(db_path,benchmark,checkpoint,job["spec"]["assets"],[folder/"candidate"],
                config=GenerationConfig(**report["generation_config"]),max_cases=200,max_seconds=max_seconds)
            if comparison["source_checkpoint_id"]!=job["checkpoint_id"] or comparison["benchmark_id"]!=benchmark["benchmark_id"] or comparison["release_ready"] is not False:
                raise ValueError("comparison identity mismatch")
            row=comparison["candidates"][0]
            if row["candidate_id"]!=result["candidate_id"] or row["mode"]!=mode or not row["source_conversion_verified"]:
                raise ValueError("candidate conversion identity mismatch")
            write_new(folder/"comparison.json",comparison)
            selected=comparison["selected"]
            summary={"artifact_id":row["candidate_id"],"bytes":row["artifact_bytes"],"verified":True,
                "regression_passed":bool(selected and selected["candidate_id"]==row["candidate_id"]),
                "metric_delta":row["regression"]["metric_delta"],"failures":row["regression"]["failures"],
                "review_id":comparison["review_id"],"release_ready":False}
        with closing(connect(db_path)) as db,db:
            if db.execute("UPDATE studio_artifacts SET state='complete',summary=?,updated=? WHERE id=? AND state='running'",
                          (json.dumps(summary,allow_nan=False),now(),id)).rowcount!=1:
                raise ValueError("artifact worker ownership lost")
        return {"id":id,"state":"complete","release_ready":False}
    except (Exception,KeyboardInterrupt) as exc:
        with closing(connect(db_path)) as db,db:
            db.execute("UPDATE studio_artifacts SET state='failed',error=?,updated=? WHERE id=? AND state='running'",(type(exc).__name__,now(),id))
        raise

def recover_artifact(db_path,id,*,worker_stopped=False):
    if worker_stopped is not True or not re.fullmatch(r"[a-f0-9]{32}",id):
        raise ValueError("confirm original worker exited")
    with closing(connect(db_path)) as db,db:
        db.execute("BEGIN IMMEDIATE")
        initialize(db)
        if db.execute("UPDATE studio_artifacts SET state='interrupted',updated=? WHERE id=? AND state='running'",(now(),id)).rowcount!=1:
            raise ValueError("no active artifact task")
    return {"id":id,"state":"interrupted","release_ready":False}
