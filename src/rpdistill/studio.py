"""Versioned bounded read-only desktop snapshot, independent of ML dependencies."""
from contextlib import closing
from datetime import datetime,timezone
from pathlib import Path
import sqlite3

from .devices import device_report
from . import __version__

SCHEMA="rpdistill-studio-snapshot-v1"
TABLES={"teachers":"teachers","modelscope_teachers":"modelscope_teachers",
        "downloads":"model_download_jobs","papers":"papers","fulltexts":"paper_fulltexts",
        "segments":"corpus_segments","pairs":"corpus_pairs","datasets":"dataset_versions",
        "pipelines":"corpus_runs","training":"training_jobs","tasks":"tasks"}
QUERIES={
    "downloads":"""SELECT id,substr(json_extract(spec,'$.model_id'),1,200) AS model_id,
        coalesce(json_extract(spec,'$.source'),'huggingface') AS source,
        state,done_bytes,total_bytes,rate,eta,{network_bytes} AS network_bytes,
        {network_rate} AS network_rate,substr(error,1,200) AS error,updated
        FROM model_download_jobs ORDER BY updated DESC,id LIMIT 50""",
    "training":"""SELECT id,state,step,attempt,reserved_seconds,reserved_bytes,
        substr(error,1,200) AS error,updated FROM training_jobs ORDER BY updated DESC,id LIMIT 50""",
    "pipelines":"""SELECT id,state,stage,substr(error,1,200) AS error,updated,
        substr(json_extract(spec,'$.model_id'),1,200) AS model_id,
        substr(json_extract(spec,'$.query.keywords[0]'),1,200) AS keyword,
        json_extract(spec,'$.max_bytes') AS max_bytes,
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


def snapshot(db_path):
    path=Path(db_path).expanduser().resolve()
    counts={key:0 for key in TABLES}
    counts.update(download_queued=0,download_active=0,pipeline_active=0)
    rows={key:[] for key in (*QUERIES,"teachers","modelscope_teachers")}
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
            "database_exists":exists,"counts":counts,"rows":rows,"devices":device_report(disk),
            "read_only":True,"training_metrics_available":False,"release_ready":False}
