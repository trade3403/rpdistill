"""Versioned bounded read-only desktop snapshot, independent of ML dependencies."""
from contextlib import closing
from datetime import datetime,timezone
from pathlib import Path
import sqlite3
import os
import shutil
from importlib.util import find_spec
from .resumable import required_bytes
from .student import FIXED, ASSETS, BASE_SOURCE, BASE_REVISION, checked_assets

from .devices import device_report
from . import __version__

SCHEMA="rpdistill-studio-snapshot-v1"
TABLES={"teachers":"teachers","modelscope_teachers":"modelscope_teachers",
        "downloads":"model_download_jobs","papers":"papers","fulltexts":"paper_fulltexts",
        "segments":"corpus_segments","pairs":"corpus_pairs","datasets":"dataset_versions",
        "pipelines":"corpus_runs","training":"training_jobs","tasks":"tasks","evaluations":"studio_evaluations","artifacts":"studio_artifacts","reviews":"studio_reviews","plans":"studio_plans","plan_cycles":"studio_plan_cycles","training_links":"studio_training_links","chains":"studio_chains"}
QUERIES={
    "chains":"""SELECT id,training_id,version,checkpoint_id,state,stage,evaluation_id,compression_id,export_id,error,updated,
        json_extract(spec,'$.mode') AS mode,json_extract(spec,'$.compression_bytes') AS compression_bytes,
        json_extract(spec,'$.export_bytes') AS export_bytes FROM studio_chains ORDER BY updated DESC,id LIMIT 50""",
    "training_links":"""SELECT version,run_id,job_id,license,substr(review_note,1,2000) AS review_note,created
        FROM studio_training_links ORDER BY created DESC,job_id LIMIT 50""",
    "plans":"""SELECT id,template_id,interval_minutes,max_cycles,claimed,state,active_run,next_due,error,updated,license,
        json_extract(spec,'$.model_id') AS model_id,json_extract(spec,'$.revision') AS revision,
        json_extract(spec,'$.query.keywords[0]') AS keyword,json_extract(spec,'$.max_bytes') AS max_bytes
        FROM studio_plans ORDER BY updated DESC,id LIMIT 50""",
    "plan_cycles":"""SELECT c.plan_id,c.cycle,c.run_id,r.state,r.stage,r.updated,
        json_extract(r.results,'$.snapshot.version') AS dataset_version
        FROM studio_plan_cycles c JOIN corpus_runs r ON r.id=c.run_id ORDER BY r.updated DESC,c.run_id LIMIT 50""",
    "reviews":"""SELECT id,source_id,kind,state,error,updated,
        json_extract(summary,'$.package_id') AS package_id,json_extract(summary,'$.parity_passed') AS parity_passed,
        json_extract(summary,'$.receipt_id') AS receipt_id,json_extract(summary,'$.integration_passed') AS integration_passed,
        json_extract(summary,'$.integrity_verified') AS integrity_verified,json_extract(summary,'$.artifact_id') AS artifact_id,
        json_extract(summary,'$.cached_tokens_per_second') AS cached_tokens_per_second,
        json_extract(summary,'$.full_tokens_per_second') AS full_tokens_per_second,
        json_extract(summary,'$.rss_bytes') AS rss_bytes,json_extract(summary,'$.packet_id') AS packet_id,
        json_extract(summary,'$.reviewer_count') AS reviewer_count,json_extract(summary,'$.case_count') AS case_count,
        json_extract(summary,'$.candidate_gate_passed') AS candidate_gate_passed,
        json_extract(summary,'$.metrics.student_adequacy') AS adequacy,json_extract(summary,'$.metrics.student_fluency') AS fluency,
        substr(json_extract(summary,'$.failures'),1,1000) AS failures FROM studio_reviews ORDER BY updated DESC,id LIMIT 50""",
    "artifacts":"""SELECT id,evaluation_id,mode,state,error,updated,
        json_extract(summary,'$.artifact_id') AS artifact_id,json_extract(summary,'$.bytes') AS bytes,
        json_extract(summary,'$.verified') AS verified,json_extract(summary,'$.regression_passed') AS regression_passed,
        json_extract(summary,'$.metric_delta.bleu') AS bleu_delta,json_extract(summary,'$.metric_delta.chrf') AS chrf_delta,
        substr(json_extract(summary,'$.failures'),1,1000) AS failures FROM studio_artifacts ORDER BY updated DESC,id LIMIT 50""",
    "evaluations":"""SELECT id,training_id,version,checkpoint_id,state,updated,error,
        json_extract(summary,'$.report_id') AS report_id,json_extract(summary,'$.benchmark_id') AS benchmark_id,
        json_extract(summary,'$.metrics.bleu') AS bleu,json_extract(summary,'$.metrics.chrf') AS chrf,
        json_extract(summary,'$.metrics.numeric') AS numeric,json_extract(summary,'$.metrics.citations') AS citations,
        json_extract(summary,'$.metrics.terminology') AS terminology,json_extract(summary,'$.metrics.protected') AS protected,
        json_extract(summary,'$.coverage.cases') AS cases,json_extract(summary,'$.coverage.papers') AS papers,
        json_extract(summary,'$.automatic_gate_passed') AS automatic_gate_passed,
        substr(json_extract(summary,'$.failures'),1,1000) AS failures
        FROM studio_evaluations ORDER BY updated DESC,id LIMIT 50""",
    "downloads":"""SELECT id,substr(json_extract(spec,'$.model_id'),1,200) AS model_id,
        coalesce(json_extract(spec,'$.source'),'huggingface') AS source,
        state,done_bytes,total_bytes,rate,eta,{network_bytes} AS network_bytes,
        {network_rate} AS network_rate,substr(error,1,200) AS error,updated
        FROM model_download_jobs ORDER BY updated DESC,id LIMIT 50""",
    "training":"""SELECT id,state,step,attempt,reserved_seconds,reserved_bytes,
        json_extract(spec,'$.version') AS version,
        json_extract(spec,'$.config.training.steps') AS target_steps,
        json_extract(spec,'$.config.device') AS device,
        json_extract(spec,'$.total_seconds') AS total_seconds,
        json_extract(spec,'$.total_checkpoint_bytes') AS total_checkpoint_bytes,
        substr(error,1,200) AS error,updated FROM training_jobs ORDER BY updated DESC,id LIMIT 50""",
    "pipelines":"""SELECT id,state,stage,substr(error,1,200) AS error,updated,
        substr(json_extract(spec,'$.model_id'),1,200) AS model_id,
        substr(json_extract(spec,'$.query.keywords[0]'),1,200) AS keyword,
        json_extract(spec,'$.max_bytes') AS max_bytes,
        json_extract(spec,'$.revision') AS revision,coalesce(json_extract(spec,'$.source'),'huggingface') AS source,
        json_extract(spec,'$.query.start_date') AS start_date,json_extract(spec,'$.query.end_date') AS end_date,
        json_extract(spec,'$.query.limit') AS search_limit,json_extract(spec,'$.segment_limit') AS segment_limit,
        json_extract(spec,'$.options.device') AS device,json_extract(spec,'$.options.dtype') AS dtype,
        json_extract(spec,'$.paper_limit') AS paper_limit,
        json_extract(results,'$.snapshot.version') AS dataset_version
        FROM corpus_runs ORDER BY updated DESC,id LIMIT 50""",
    "papers":"""SELECT paper_id AS id,pmcid,substr(json_extract(record,'$.title'),1,300) AS title,
        substr(json_extract(record,'$.publication_date'),1,20) AS publication_date,
        substr(json_extract(record,'$.eligibility'),1,80) AS eligibility
        FROM papers ORDER BY paper_id DESC LIMIT 50""",
    "datasets":"""SELECT version,json_extract(manifest,'$.counts.train') AS train,
        json_extract(manifest,'$.counts.validation') AS validation,
        json_extract(manifest,'$.counts.test') AS test,
        substr(json_extract(manifest,'$.teacher.model_id'),1,200) AS model_id,
        substr(json_extract(manifest,'$.status'),1,80) AS status
        FROM dataset_versions ORDER BY version LIMIT 50""",
}
TEACHER_SQL="""SELECT substr(model_id,1,200) AS model_id,revision,
    substr(json_extract(record,'$.license'),1,100) AS license FROM {table}
    ORDER BY model_id,revision LIMIT 50"""


def student_resources(assets,checkpoint_root):
    assets=Path(assets).expanduser()
    state="missing"
    try:
        if assets.is_symlink():
            state="invalid"
        elif assets.exists():
            checked_assets(assets)
            state="verified"
    except (OSError,ValueError):
        state="invalid"
    def free_bytes(path):
        try:
            path=Path(path).expanduser().resolve()
            while not path.exists() and path!=path.parent:
                path=path.parent
            return shutil.disk_usage(path).free if path.is_dir() else None
        except (OSError,RuntimeError,ValueError):
            return None
    def present(name):
        try:
            return find_spec(name) is not None
        except (ImportError,ValueError):
            return False
    return {"state":state,"source":BASE_SOURCE,"revision":BASE_REVISION,
            "file_count":len(ASSETS),"asset_bytes":sum(v[0] for v in ASSETS.values()),
            "assets_free_bytes":free_bytes(assets),"checkpoint_free_bytes":free_bytes(checkpoint_root),
            "dependencies":{name:present(name) for name in ("torch","transformers","sentencepiece","safetensors","huggingface_hub","modelscope_hub","sacrebleu")},
            "runtime_verified":False}


def snapshot(db_path):
    path=Path(db_path).expanduser().resolve()
    counts={key:0 for key in TABLES}
    counts.update(download_queued=0,download_active=0,pipeline_active=0,training_queued=0,training_active=0,evaluation_active=0,artifact_active=0,review_active=0,plan_active=0,chain_active=0)
    rows={key:[] for key in (*QUERIES,"teachers","modelscope_teachers","training_loss","training_events")}
    exists=path.exists()
    if exists:
        if not path.is_file():
            raise ValueError("studio database is not a file")
        # No migrations or initialization from a dashboard query.
        with closing(sqlite3.connect(path.as_uri()+"?mode=ro",uri=True,timeout=3)) as db:
            db.row_factory=sqlite3.Row
            db.execute("PRAGMA query_only=ON")
            db.execute("PRAGMA trusted_schema=OFF")
            db.execute("BEGIN")
            available={row[0] for row in db.execute("SELECT name FROM sqlite_master WHERE type='table'")}
            for key,table in TABLES.items():
                if table in available:
                    counts[key]=db.execute("SELECT count(*) FROM "+table).fetchone()[0]
            if TABLES["downloads"] in available:
                counts["download_queued"]=db.execute("SELECT count(*) FROM model_download_jobs WHERE state='queued'").fetchone()[0]
                counts["download_active"]=db.execute("SELECT count(*) FROM model_download_jobs WHERE state IN ('running','pause_requested','cancel_requested')").fetchone()[0]
            if TABLES["pipelines"] in available:
                counts["pipeline_active"]=db.execute("SELECT count(*) FROM corpus_runs WHERE state='running'").fetchone()[0]
            if TABLES["training"] in available:
                counts["training_queued"]=db.execute("SELECT count(*) FROM training_jobs WHERE state='queued'").fetchone()[0]
                counts["training_active"]=db.execute("SELECT count(*) FROM training_jobs WHERE state IN ('running','pause_requested','cancel_requested')").fetchone()[0]
            if "training_events" in available and TABLES["training"] in available:
                rows["training_events"]=[dict(r) for r in db.execute("""SELECT seq,job_id,state,created,
                    json_extract(detail,'$.step') AS step,substr(json_extract(detail,'$.error'),1,100) AS error
                    FROM training_events ORDER BY seq DESC LIMIT 50""")]
                # One job, bounded recent checkpoint samples. Never blend distinct runs.
                chosen=db.execute("""SELECT id FROM training_jobs WHERE step>0
                    ORDER BY CASE WHEN state IN ('running','pause_requested','cancel_requested') THEN 0 ELSE 1 END,updated DESC,id LIMIT 1""").fetchone()
                if "training_step_metrics" in available:
                    # Prefer the active job even before its first checkpoint.
                    chosen=db.execute("""SELECT id FROM training_jobs
                        WHERE state IN ('running','pause_requested','cancel_requested')
                        OR step>0 ORDER BY CASE WHEN state IN ('running','pause_requested','cancel_requested')
                        THEN 0 ELSE 1 END,updated DESC,id LIMIT 1""").fetchone()
                if chosen:
                    rows["training_loss"]=[dict(r) for r in db.execute("""SELECT job_id,
                        json_extract(detail,'$.step') AS step,json_extract(detail,'$.loss') AS loss
                        FROM training_events WHERE job_id=? AND json_type(detail,'$.loss') IN ('integer','real')
                        ORDER BY seq DESC LIMIT 120""",(chosen[0],))][::-1]
                    if "training_step_metrics" in available:
                        samples=[dict(r) for r in db.execute("""SELECT m.job_id,m.step,m.loss,m.seconds,m.tokens,
                            m.committed,m.created,j.state,j.step AS durable_step,
                            json_extract(j.spec,'$.config.training.steps') AS target_steps
                            FROM training_step_metrics m JOIN training_jobs j ON j.id=m.job_id
                            WHERE m.job_id=? AND (m.committed=1 OR (m.attempt=j.attempt AND j.state IN
                            ('running','pause_requested','cancel_requested') AND m.step>j.step))
                            ORDER BY m.step DESC LIMIT 120""",(chosen[0],))][::-1]
                        if samples:
                            rows["training_loss"]=samples
            if TABLES["evaluations"] in available:
                counts["evaluation_active"]=db.execute("SELECT count(*) FROM studio_evaluations WHERE state='running'").fetchone()[0]
            if TABLES["artifacts"] in available:
                counts["artifact_active"]=db.execute("SELECT count(*) FROM studio_artifacts WHERE state='running'").fetchone()[0]
            if TABLES["reviews"] in available:
                counts["review_active"]=db.execute("SELECT count(*) FROM studio_reviews WHERE state='running'").fetchone()[0]
            if TABLES["plans"] in available:
                counts["plan_active"]=db.execute("SELECT count(*) FROM studio_plans WHERE state='running'").fetchone()[0]
            if TABLES["chains"] in available:
                counts["chain_active"]=db.execute("SELECT count(*) FROM studio_chains WHERE state='running'").fetchone()[0]
            for key,sql in QUERIES.items():
                if TABLES[key] in available:
                    if key=="downloads":
                        columns={row[1] for row in db.execute("PRAGMA table_info(model_download_jobs)")}
                        sql=sql.format(**{name:name if name in columns else "NULL" for name in ("network_bytes","network_rate")})
                    rows[key]=[dict(r) for r in db.execute(sql)]
            for key in ("teachers","modelscope_teachers"):
                if TABLES[key] in available:
                    rows[key]=[dict(r) for r in db.execute(TEACHER_SQL.format(table=TABLES[key]))]
    disk=path.parent
    while not disk.exists():
        disk=disk.parent
    return {"schema":SCHEMA,"version":__version__,"observed_at":datetime.now(timezone.utc).isoformat(),
            "database_exists":exists,"checkpoint_min_bytes":required_bytes(FIXED),
            "student_resources":student_resources(os.environ.get("RPDISTILL_STUDENT_ASSETS",Path.home()/".rpdistill"/"student-assets"),
                os.environ.get("RPDISTILL_CHECKPOINT_ROOT",Path.home()/".rpdistill"/"checkpoints")),"counts":counts,"rows":rows,"devices":device_report(disk),
            "read_only":True,"training_metrics_available":bool(rows["training_loss"]),"release_ready":False}
