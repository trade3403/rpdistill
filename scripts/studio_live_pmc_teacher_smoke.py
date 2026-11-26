"""Actual PMC acquisition and pretrained Qwen translation using the production pipeline.

Fresh temporary database, fixed search bounds, verified model snapshot, real network
and local generation. Report contains provenance and counts, not article prose or
training data. No synthetic paper/teacher injection and no relaxed dataset gate.
"""
import argparse
from contextlib import closing
import hashlib
import json
import os
from pathlib import Path
import re
import tempfile
import time
from collections import Counter

from studio_live_teacher_smoke import MODEL, REV, LICENSE, WEIGHT_SHA, BUDGET
from rpdistill.downloads import DownloadQueue
from rpdistill.teachers import TeacherRegistry
from rpdistill.inference import TranslationOptions
from rpdistill.corpus import CorpusStore, stable_split
from rpdistill.datasets import DatasetStore, DatasetGate
from rpdistill.fulltext import FulltextLibrary, inspect_record
from rpdistill.papers import PaperCatalog, PaperQuery
from rpdistill.pipeline import CorpusPipeline

PAPER_LIMIT=40
PAPER_BYTES=64*1024*1024
SEGMENT_LIMIT=120
QUERY=PaperQuery(("malaria",),"2024-01-01","2024-12-31",limit=PAPER_LIMIT)
OPTIONS=TranslationOptions(max_input_tokens=2048,max_new_tokens=384,batch_size=2,device="cpu",dtype="float32")

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--report",required=True,type=Path)
    args=p.parse_args()
    if args.report.exists():
        raise ValueError("new report path required")
    with tempfile.TemporaryDirectory(prefix="rpdistill-live-pmc-teacher-") as tmp:
        root=Path(tmp).resolve()
        db=root/"db.sqlite3"
        report={"model":MODEL,"revision":REV,"license":LICENSE,"weight_sha256":WEIGHT_SHA,
                "paper_provider":"ncbi-pmc","real_published_papers":True,
                "paper_limit":PAPER_LIMIT,"paper_payload_budget":PAPER_BYTES,
                "segment_limit":SEGMENT_LIMIT,"human_quality_certified":False,"release_ready":False}
        try:
            queue=DownloadQueue(db)
            job=queue.enqueue(MODEL,REV,reviewed_license=LICENSE,max_bytes=BUDGET,cache_dir=root/"cache")
            result=queue.run_next()
            assert result["id"]==job["id"] and result["state"]=="succeeded",result.get("error")
            assert 0<result["done_bytes"]==result["total_bytes"]<=BUDGET
            record=TeacherRegistry(db).get(MODEL,REV)
            assert record["license"]==LICENSE and not record["gated"] and not record["private"]
            weight=next(x for x in record["manifest"] if x["name"]=="model.safetensors")
            assert weight["sha256"]==WEIGHT_SHA and weight["upstream_sha256_verified"] is True
            report["model_verified_bytes"]=result["done_bytes"]
            os.environ["HF_HUB_OFFLINE"]="1"
            os.environ["TRANSFORMERS_OFFLINE"]="1"
            import torch
            torch.set_num_threads(min(4,os.cpu_count() or 1))
            pipe=CorpusPipeline(db)
            run=pipe.create(QUERY,MODEL,REV,OPTIONS,root=root/"xml",max_bytes=PAPER_BYTES,
                            paper_limit=PAPER_LIMIT,segment_limit=SEGMENT_LIMIT,gate=DatasetGate())
            start=time.monotonic()
            done=pipe.run(run["id"])
            report["pipeline_seconds"]=time.monotonic()-start
            report["run_id"]=run["id"]
            report["state"]=done["state"]
            report["stage"]=done["stage"]
            report["error"]=done["error"]
            report["stages"]=done["results"]
            assert done["stage"]>=3,done
            results=done["results"]
            assert results["search"]["provider"]=="ncbi-pmc" and 0<results["search"]["inserted"]<=PAPER_LIMIT
            assert 0<results["download"]["saved"]<=PAPER_LIMIT and results["download"]["bytes"]<=PAPER_BYTES
            assert results["parse"]["segments"]>0
            catalog={r["pmcid"]:r for r in PaperCatalog(db).list(500)}
            lib=FulltextLibrary(db,root/"xml")
            papers={}
            for f in lib.list():
                if f["status"]!="downloaded_pending_content_review":
                    continue
                raw=Path(f["path"]).read_bytes()
                assert len(raw)==f["size"] and hashlib.sha256(raw).hexdigest()==f["sha256"]
                rights=inspect_record(raw,f["pmcid"],full=True,expected_doi=catalog[f["pmcid"]]["doi"])
                assert rights["license"] in ("cc-by","cc0") and rights["license_uri"]==f["license_uri"]
                papers[f["pmcid"]]={k:f[k] for k in ("pmcid","doi","license","license_uri","sha256","datestamp","size")}
            report["papers"]=list(papers.values())
            corpus=CorpusStore(db)
            with closing(corpus.connect()) as conn:
                pairs=[json.loads(r[0]) for r in conn.execute("SELECT record FROM corpus_pairs ORDER BY id")]
            flags=Counter()
            screened_splits=Counter()
            for pair in pairs:
                pmcid=pair["pmcid"]
                assert pmcid in papers and pair["attribution"]["xml_sha256"]==papers[pmcid]["sha256"]
                assert pair["teacher"]=={"source":"huggingface","model_id":MODEL,"revision":REV}
                assert pair["split"]==stable_split(pmcid)
                assert hashlib.sha256(pair["source_text"].encode()).hexdigest()==pair["source_sha256"]
                flags.update(pair["quality_flags"])
                if pair["status"]=="screened_candidate" and re.search(r"[\u3400-\u9fff]",pair["translation"]):
                    screened_splits[pair["split"]]+=1
            report["quality_flags"]=dict(flags)
            report["screened_chinese_by_split"]=dict(screened_splits)
            report["translated_papers"]=len({r["pmcid"] for r in pairs})
            assert done["state"]=="candidate_complete",done
            assert done["stage"]==5
            translated=results["translate"]
            assert 0<translated["generated"]==len(pairs)<=SEGMENT_LIMIT and translated["failed"]==0
            manifest=results["snapshot"]
            assert manifest["status"]=="candidate_snapshot" and manifest["training_ready"] is False
            assert manifest["counts"]["train"]>=10 and manifest["counts"]["validation"]>=1 and manifest["counts"]["test"]>=1
            assert all(screened_splits[s]>0 for s in ("train","validation","test"))
            store=DatasetStore(db)
            dest=root/"candidate.jsonl"
            exported=store.export(manifest["version"],dest)
            assert exported["training_ready"] is False
            assert hashlib.sha256(dest.read_bytes()).hexdigest()==manifest["payload_sha256"]
            assert store.create(MODEL,REV,OPTIONS,gate=DatasetGate())["version"]==manifest["version"]
            report["snapshot_payload_verified"]=True
            report["snapshot_reuse_verified"]=True
            report["live_acceptance_passed"]=True
        finally:
            args.report.parent.mkdir(parents=True,exist_ok=True)
            with args.report.open("x",encoding="utf-8") as f:
                json.dump(report,f,ensure_ascii=True,allow_nan=False,indent=2)
            print(json.dumps(report,ensure_ascii=True,allow_nan=False))

if __name__=="__main__":
    main()
