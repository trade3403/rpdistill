"""Real pinned teacher quantitative diagnostic, distinct from release evaluation."""
import argparse
from dataclasses import asdict
import json
import math
import os
from pathlib import Path
import statistics
import tempfile
import time

from studio_live_teacher_smoke import MODEL,REV,LICENSE,WEIGHT_SHA,BUDGET
from teacher_diagnostic_cases import cases,fixture_id
from rpdistill.downloads import DownloadQueue
from rpdistill.teachers import TeacherRegistry
from rpdistill.inference import TranslationOptions,load_teacher,PROMPT_VERSION
from rpdistill.evaluation import QualityGate,score_cases,hash_json,write_new
from rpdistill.student_evaluation import peak_process_rss

def timed_run(teacher,rows,batch):
    out=[]
    batch_seconds=[]
    count=0
    start=time.perf_counter()
    for pos in range(0,len(rows),batch):
        group=rows[pos:pos+batch]
        t=time.perf_counter()
        actual=teacher.translate([r["source"] for r in group])
        dt=time.perf_counter()-t
        assert len(actual)==len(group) and dt>0
        batch_seconds.append(dt)
        for row,result in zip(group,actual):
            assert result["source_text"]==row["source"]
            assert result["teacher"]=={"source":"huggingface","model_id":MODEL,"revision":REV}
            assert result["prompt_version"]==PROMPT_VERSION
            assert result["options"]==asdict(teacher.options)
            assert 0<=result["generated_tokens"]<=teacher.options.max_new_tokens
            assert result["finish_reason"] in ("eos","length")
            count+=result["generated_tokens"]
            out.append({"id":row["id"],"hypothesis":result["translation"],
                        "finish_reason":result["finish_reason"],"generated_tokens":result["generated_tokens"]})
    total=time.perf_counter()-start
    ordered=sorted(batch_seconds)
    score=score_cases(rows,[{"id":r["id"],"hypothesis":r["hypothesis"]} for r in out])
    # The authored suite lacks independent human and real-paper coverage.
    assert not score["automatic_gate_passed"] and "coverage:cases" in score["failures"]
    return {"batch_size":batch,"options":asdict(teacher.options),
            "performance":{"seconds":total,"segments_per_second":len(out)/total,
              "generated_tokens":count,"generated_tokens_per_second":count/total,
              "batch_latency_p50_seconds":statistics.median(ordered),
              "batch_latency_p95_seconds":ordered[math.ceil(.95*len(ordered))-1],
              "batch_count":len(ordered),"process_peak_rss_bytes":peak_process_rss()},
            "generation":out,"generation_incomplete":sum(r["finish_reason"]!="eos" for r in out),
            "diagnostic_metrics":score}

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--report",required=True,type=Path)
    args=p.parse_args()
    if args.report.exists():
        raise ValueError("new report required")
    rows=cases()
    report={"schema":"rpdistill-teacher-diagnostic-v1","fixture_id":fixture_id(),
            "reference_origin":"original authored diagnostic, not independent human review",
            "real_published_papers":False,"training_dataset_bound":False,
            "model":MODEL,"revision":REV,"license":LICENSE,"weight_sha256":WEIGHT_SHA,
            "prompt_version":PROMPT_VERSION,"quality_certified":False,"release_ready":False,
            "diagnostic_execution_passed":False,"cases":rows}
    try:
        perfect=score_cases(rows,[{"id":c["id"],"hypothesis":c["reference"]} for c in rows])
        corrupt=score_cases(rows,[{"id":c["id"],"hypothesis":""} for c in rows])
        assert perfect["metrics"]["bleu"]>99 and perfect["metrics"]["chrf"]>99
        assert perfect["metrics"]["numeric"]==1 and perfect["metrics"]["terminology"]==1
        assert perfect["metrics"]["citations"]==1 and perfect["metrics"]["protected"]==1
        assert not perfect["automatic_gate_passed"] and not corrupt["automatic_gate_passed"]
        assert corrupt["metrics"]["suspicious"]==1 and corrupt["metrics"]["protected"]==0
        report["metric_control_checks"]=True
        with tempfile.TemporaryDirectory(prefix="rpdistill-teacher-diagnostic-") as tmp:
            root=Path(tmp).resolve()
            db=root/"db"
            queue=DownloadQueue(db)
            job=queue.enqueue(MODEL,REV,reviewed_license=LICENSE,max_bytes=BUDGET,cache_dir=root/"cache")
            result=queue.run_next()
            assert result["state"]=="succeeded" and result["id"]==job["id"],result
            assert 0<result["done_bytes"]==result["total_bytes"]<=BUDGET
            record=TeacherRegistry(db).get(MODEL,REV)
            assert record["license"]==LICENSE and not record["private"] and not record["gated"]
            weight=next(r for r in record["manifest"] if r["name"]=="model.safetensors")
            assert weight["sha256"]==WEIGHT_SHA and weight["upstream_sha256_verified"] is True
            report["verified_bytes"]=result["done_bytes"]
            os.environ["HF_HUB_OFFLINE"]="1"
            os.environ["TRANSFORMERS_OFFLINE"]="1"
            import torch,transformers
            torch.set_num_threads(min(4,os.cpu_count() or 1))
            report.update(torch=str(torch.__version__),transformers=transformers.__version__,
                          threads=torch.get_num_threads(),device="cpu",dtype="float32",runs=[])
            for batch in (1,2):
                opts=TranslationOptions(max_input_tokens=512,max_new_tokens=128,batch_size=batch)
                start=time.perf_counter()
                teacher=load_teacher(db,MODEL,REV,opts)
                load_seconds=time.perf_counter()-start
                # Same untimed warmup workload, not a scored case.
                teacher.translate(["The laboratory records were checked before analysis."]*batch)
                run=timed_run(teacher,rows,batch)
                run["load_seconds"]=load_seconds
                report["runs"].append(run)
                del teacher
            a,b=report["runs"]
            report["batch_output_exact_match_fraction"]=sum(x["hypothesis"]==y["hypothesis"]
                for x,y in zip(a["generation"],b["generation"]))/len(rows)
            report["batch2_to_batch1_throughput_ratio"]=b["performance"]["segments_per_second"]/a["performance"]["segments_per_second"]
            report["diagnostic_execution_passed"]=True
    except (Exception,KeyboardInterrupt) as exc:
        report["error"]=type(exc).__name__
        raise
    finally:
        write_new(args.report,report|{"report_id":hash_json(report)})
        print(json.dumps({k:v for k,v in report.items() if k not in ("cases","runs")}|
            {"runs":[{k:v for k,v in r.items() if k not in ("generation","diagnostic_metrics")}|
                {"metrics":r["diagnostic_metrics"]["metrics"],"failures":r["diagnostic_metrics"]["failures"]}
                for r in report.get("runs",[])]},ensure_ascii=True,allow_nan=False))

if __name__=="__main__":
    main()
