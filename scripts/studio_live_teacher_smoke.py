"""Live pretrained Qwen teacher on original synthetic scientific prose.

Real network weight download and real local CPU generation; fictional JATS
records are isolated fixtures, never real papers or a certified dataset.
No mock teacher, remote model code, pickle, or user data.
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
from xml.sax.saxutils import escape

from rpdistill.downloads import DownloadQueue
from rpdistill.teachers import TeacherRegistry
from rpdistill.inference import TranslationOptions, load_teacher, PROMPT_VERSION
from rpdistill.corpus import CorpusStore, stable_split, quality
from rpdistill.datasets import DatasetStore, DatasetGate
from rpdistill.fulltext import FulltextLibrary
from rpdistill.papers import PaperCatalog, paper_from_record

MODEL="Qwen/Qwen2.5-0.5B-Instruct"
REV="c89bee90d9f811437d9735454613c35b4a3c4dc8"
LICENSE="apache-2.0"
WEIGHT_SHA="fdf756fa7fcbe7404d5c60e26bff1a0c8b8aa1f72ced49e7dd0210fe288fb7fe"
BUDGET=1200*1024*1024
CASES={
    "train": [
        "The experimental results indicate that increasing the temperature accelerates the reaction.",
        "The concentration of glucose in the sample was measured after 24 hours.",
    ],
    "validation": [
        "The new method improves the accuracy of measurements under controlled laboratory conditions.",
        "The mean particle diameter was 12 nm before the treatment.",
    ],
    "test": [
        "The analysis suggests that the observed difference is associated with environmental changes.",
        "The samples were stored at 4 degrees Celsius to reduce degradation.",
    ],
}
URI="https://creativecommons.org/licenses/by/4.0/"

def fixture_records():
    # High fictional IDs are used only inside the temporary test database.
    ids={}
    for i in range(990000000,990001000):
        pid="PMC"+str(i)
        ids.setdefault(stable_split(pid),pid)
        if len(ids)==3:
            break
    assert set(ids)==set(CASES)
    records={}
    for split,pid in ids.items():
        doi="10.1234/fixture-"+pid.lower()
        front=(f'<OAI-PMH xmlns="http://www.openarchives.org/OAI/2.0/"><GetRecord><record>'
            f'<header><identifier>oai:pubmedcentral.nih.gov:{pid[3:]}</identifier>'
            f'<datestamp>2025-01-01</datestamp></header><metadata><article xmlns="" xml:lang="en">'
            f'<front><article-meta><article-id pub-id-type="pmc">{pid[3:]}</article-id>'
            f'<article-id pub-id-type="doi">{doi}</article-id>'
            f'<permissions><license xmlns:xlink="http://www.w3.org/1999/xlink" xlink:href="{URI}">'
            f'<license-p>Original test fixture prose under CC BY 4.0.</license-p></license></permissions>'
            f'</article-meta></front>')
        end='</article></metadata></record></GetRecord></OAI-PMH>'
        body='<body>'+''.join('<p>'+escape(s)+'</p>' for s in CASES[split])+'</body>'
        records[pid]=(paper_from_record(dict(source="FIXTURE",id=pid[3:],title="Fictional translation test fixture",
            authorString="RPDistill test fixture",doi=doi,pmcid=pid,isOpenAccess="Y",license="cc by")),
            (front+end).encode(),(front+body+end).encode())
    return records

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--report",required=True,type=Path)
    args=p.parse_args()
    if args.report.exists():
        raise ValueError("new report path required")
    with tempfile.TemporaryDirectory(prefix="rpdistill-live-teacher-") as tmp:
        root=Path(tmp).resolve()
        db=root/"db.sqlite3"
        queue=DownloadQueue(db)
        start=time.monotonic()
        job=queue.enqueue(MODEL,REV,reviewed_license=LICENSE,max_bytes=BUDGET,cache_dir=root/"cache")
        downloaded=queue.run_next()
        assert downloaded["id"]==job["id"] and downloaded["state"]=="succeeded",downloaded.get("error")
        assert 0<downloaded["done_bytes"]==downloaded["total_bytes"]<=BUDGET
        assert 0<downloaded["network_bytes"]<=BUDGET
        record=TeacherRegistry(db).get(MODEL,REV)
        assert record["license"]==LICENSE and record["revision"]==REV and not record["gated"] and not record["private"]
        weight=next(x for x in record["manifest"] if x["name"]=="model.safetensors")
        assert weight["sha256"]==WEIGHT_SHA and weight["upstream_sha256_verified"] is True
        download_seconds=time.monotonic()-start
        # No online model loading: flags set before importing transformers/torch.
        os.environ["HF_HUB_OFFLINE"]="1"
        os.environ["TRANSFORMERS_OFFLINE"]="1"
        import torch
        torch.set_num_threads(min(4,os.cpu_count() or 1))
        options=TranslationOptions(max_input_tokens=512,max_new_tokens=128,batch_size=1,device="cpu",dtype="float32")
        start=time.monotonic()
        teacher=load_teacher(db,MODEL,REV,options)
        load_seconds=time.monotonic()-start
        records=fixture_records()
        catalog=PaperCatalog(db)
        for paper,_,_ in records.values():
            catalog.ingest(paper)
        lib=FulltextLibrary(db,root/"xml")
        def fetch(pid,prefix,budget):
            raw=records[pid][1 if prefix=="pmc_fm" else 2]
            budget.consume(len(raw))
            return raw
        acquisition=lib.download(catalog.list(),max_bytes=65536,limit=3,fetch=fetch,sleep=lambda _:None)
        assert acquisition["saved"]==3
        corpus=CorpusStore(db)
        parsed=corpus.parse(lib.root,limit=3)
        assert parsed["segments"]==6 and parsed["blocked"]==0
        start=time.monotonic()
        translated=corpus.translate(teacher,limit=6)
        seconds=time.monotonic()-start
        with closing(corpus.connect()) as conn:
            pairs=[json.loads(x[0]) for x in conn.execute("SELECT record FROM corpus_pairs ORDER BY id")]
        assert len(pairs)==6 and translated["generated"]==6 and translated["failed"]==0
        rows=[]
        for pair in pairs:
            assert pair["teacher"]=={"source":"huggingface","model_id":MODEL,"revision":REV}
            assert pair["prompt_version"]==PROMPT_VERSION
            assert pair["source_text"] in CASES[pair["split"]]
            assert pair["quality_flags"]==quality(pair["source_text"],pair|{"status":"candidate" if pair["finish_reason"]=="eos" and pair["translation"].strip() and "<think>" not in pair["translation"] and "</think>" not in pair["translation"] else "needs_review"})
            rows.append({k:pair[k] for k in ("source_text","translation","split","finish_reason","quality_flags","status")})
        cached=corpus.translate(teacher,limit=6)
        assert cached["cached"]==6 and cached["generated"]==0
        store=DatasetStore(db)
        manifest=store.create(MODEL,REV,options,gate=DatasetGate(1,1,1,6))
        report={"fixture":"original fictional JATS; not real published papers",
            "model":MODEL,"revision":REV,"license":LICENSE,"weight_sha256":WEIGHT_SHA,
            "verified_bytes":downloaded["done_bytes"],"network_bytes":downloaded["network_bytes"],
            "device":"cpu","dtype":"float32","torch":torch.__version__,"download_seconds":download_seconds,
            "load_seconds":load_seconds,"translation_seconds":seconds,"segments_per_second":6/max(seconds,0.001),
            "fixture_acquisition":acquisition,"parsed":parsed,"translated":translated,"cached":cached,
            "snapshot":manifest,"outputs":rows,"human_quality_certified":False,"release_ready":False}
        if manifest["status"]=="candidate_snapshot":
            dest=root/"fixture.jsonl"
            store.export(manifest["version"],dest)
            assert hashlib.sha256(dest.read_bytes()).hexdigest()==manifest["payload_sha256"]
            report["snapshot_payload_verified"]=True
        else:
            report["snapshot_payload_verified"]=False
        # Preserve diagnostic results even if the candidate gate fails.
        args.report.parent.mkdir(parents=True,exist_ok=True)
        with args.report.open("x",encoding="utf-8") as f:
            json.dump(report,f,ensure_ascii=True,allow_nan=False,indent=2)
        print(json.dumps(report,ensure_ascii=True,allow_nan=False))
        assert translated["screened"]>0,"no screened translations"
        assert manifest["status"]=="candidate_snapshot","fixture split gate not passed"
        assert manifest["training_ready"] is False
        for split in CASES:
            assert any(r["split"]==split and r["status"]=="screened_candidate" and re.search(r"[\u3400-\u9fff]",r["translation"]) for r in rows),split

if __name__=="__main__":
    main()
