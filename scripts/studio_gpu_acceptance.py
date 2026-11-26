"""Explicit real CUDA acceptance for the fixed student and durable queue.

Uses original test translation targets and verified tokenizer assets. It is
a hardware/checkpoint acceptance, not training on the live PMC candidate or a
translation quality certification. No CPU fallback and no implicit download.
"""
import argparse
import json
import math
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import time

os.environ.setdefault("CUBLAS_WORKSPACE_CONFIG",":4096:8")

from rpdistill.student import FIXED,StudentCodec,contract
from rpdistill.training_data import acquire_assets,ASSET_BYTES
from rpdistill.distill import DistillConfig
from rpdistill.resumable import ResumeConfig,execution_device,required_bytes,run_segment
from rpdistill.training_queue import TrainingQueue,verified_checkpoint
from rpdistill.studio import snapshot
from rpdistill.evaluation import hash_json

CASES=[
    ("Academic paper translation.","学术论文翻译。"),
    ("The model has high accuracy.","模型具有较高的准确率。"),
    ("The experimental results are statistically significant.","实验结果具有统计学意义。"),
    ("The temperature was 25 degrees Celsius.","温度为25摄氏度。"),
]
STEPS=3
SEGMENT_SECONDS=300

def config(args):
    if not re.fullmatch(r"cuda:[0-9]{1,3}",args.device):
        raise ValueError("explicit CUDA device required")
    return ResumeConfig(DistillConfig(steps=STEPS,batch_size=1,learning_rate=1e-4,seed=37),
                        accumulation=1,device=args.device,precision=args.precision,
                        cuda_budget_bytes=args.cuda_budget_bytes)

def inputs(root):
    codec=StudentCodec.from_assets(root/"assets")
    examples=[{"source_ids":codec.encode(a),"target_ids":codec.encode(b,target=True)} for a,b in CASES]
    provenance={"fixture":"original synthetic translation pairs; not teacher output",
                "method":"sequence-level teacher-target cross-entropy mechanics",
                "tokenized_examples_sha256":hash_json(examples),"quality_certified":False}
    return examples,provenance

def runtime(args):
    import torch
    torch.set_num_threads(1)
    cfg=config(args)
    device=execution_device(cfg,FIXED)
    if device.type!="cuda":
        raise ValueError("CUDA required; CPU fallback forbidden")
    with torch.cuda.device(device):
        t=torch.tensor([2.0],device=device)
        if not t.is_cuda or (t*3).item()!=6.0:
            raise ValueError("real CUDA tensor calculation failed")
        del t
        torch.cuda.synchronize(device)
    return cfg,device

def worker(args):
    cfg,device=runtime(args)
    root=Path(args.worker_root).resolve(strict=True)
    queue=TrainingQueue(root/"db")
    job=queue.get(args.job_id)
    if job["spec"]["config"]["device"]!=args.device:
        raise ValueError("worker device mismatch")
    examples,prov=inputs(root)
    def prepare(*a,**kw):
        return examples,prov
    if args.worker=="pause":
        def execute(*a,**kw):
            stop=kw["should_stop"]
            def pause():
                queue.control(job["id"],"pause")
                return stop()
            kw["should_stop"]=pause
            return run_segment(*a,**kw)
        result=queue.run_next(prepare=prepare,execute=execute,profile=FIXED)
        assert result["id"]==job["id"] and result["state"]=="paused" and result["step"]==1,result
    elif args.worker=="resume":
        assert job["state"]=="paused" and job["step"]==1
        queue.control(job["id"],"resume")
        result=queue.run_next(prepare=prepare,profile=FIXED)
        assert result["id"]==job["id"] and result["state"]=="complete" and result["step"]==STEPS,result
    else:
        raise ValueError("invalid worker mode")
    print(json.dumps({"worker":args.worker,"pid":os.getpid(),"job":job["id"],"state":result["state"],"step":result["step"]}))

def accept(args,report):
    import torch
    from safetensors import safe_open
    cfg,device=runtime(args)
    props=torch.cuda.get_device_properties(device)
    report.update(gpu=props.name,device=str(device),capability=[props.major,props.minor],
                  total_vram_bytes=props.total_memory,torch=str(torch.__version__),cuda=torch.version.cuda,
                  precision=args.precision,allocated_budget_bytes=args.cuda_budget_bytes,
                  profile=contract(FIXED)["profile"],real_cuda_tensor=True)
    checkpoint_bytes=required_bytes(FIXED)
    # Pause + final queue checkpoint + uninterrupted reference; reserve extra disk.
    with tempfile.TemporaryDirectory(prefix="rpdistill-gpu-accept-") as tmp:
        root=Path(tmp).resolve()
        if shutil.disk_usage(root).free<4*checkpoint_bytes+ASSET_BYTES:
            raise ValueError("insufficient disk for checkpoint comparison")
        report["tokenizer"]=acquire_assets(root/"assets",max_bytes=ASSET_BYTES+1048576)
        report["tokenizer"].pop("path",None)
        examples,prov=inputs(root)
        report["examples_sha256"]=hash_json(examples)
        queue=TrainingQueue(root/"db")
        version=hash_json(prov)
        job=queue.enqueue(version,root/"assets",root/"states",reviewed_dataset=version,
            reviewed_teacher_license="original-test-fixture",config=cfg,segment_steps=STEPS,
            segment_seconds=SEGMENT_SECONDS,total_seconds=2*SEGMENT_SECONDS,
            max_checkpoint_bytes=checkpoint_bytes,total_checkpoint_bytes=2*checkpoint_bytes)
        report["training_job"]=job["id"]
        workers=[]
        for mode in ("pause","resume"):
            command=[sys.executable,str(Path(__file__).resolve()),"--approved","--device",args.device,
                "--precision",args.precision,"--cuda-budget-bytes",str(args.cuda_budget_bytes),
                "--worker",mode,"--worker-root",str(root),"--job-id",job["id"]]
            proc=subprocess.run(command,check=True,timeout=900,capture_output=True,encoding="utf-8",
                                errors="replace",env={**os.environ,"HF_HUB_OFFLINE":"1","TRANSFORMERS_OFFLINE":"1"})
            result=json.loads(proc.stdout.strip().splitlines()[-1])
            assert result["worker"]==mode and result["job"]==job["id"]
            workers.append(result)
        report["workers"]=workers
        # The first subprocess has exited before the second is launched.
        done=TrainingQueue(root/"db").get(job["id"])
        assert done["state"]=="complete" and done["step"]==STEPS and done["attempt"]==2,done
        assert done["reserved_seconds"]==2*SEGMENT_SECONDS and done["reserved_bytes"]==2*checkpoint_bytes
        folders=sorted((root/"states"/job["id"]).glob("attempt-*"))
        assert len(folders)==2 and folders[-1]==Path(done["checkpoint"])
        first,_=verified_checkpoint(folders[0],FIXED,0,STEPS)
        final,_=verified_checkpoint(folders[1],FIXED,1,STEPS)
        assert first["step"]==1 and final["checkpoint_id"]==done["checkpoint_id"]
        start=time.monotonic()
        full=run_segment(examples,root/"reference",config=cfg,profile=FIXED,provenance=prov,
            run_steps=STEPS,max_seconds=SEGMENT_SECONDS,max_checkpoint_bytes=checkpoint_bytes)
        reference_seconds=time.monotonic()-start
        assert full["status"]=="complete" and full["step"]==STEPS
        assert full["history"]==final["history"] and full["scaler_state"]==final["scaler_state"]
        assert bool(full["scaler_state"])==(args.precision=="float16")
        peaks=[m["peak_cuda_allocated_bytes"] for m in (first,final,full)]
        assert all(type(x) is int and 0<x<=args.cuda_budget_bytes for x in peaks),peaks
        assert all(m["environment"]["device"]==args.device and m["environment"]["gpu"]==props.name for m in (first,final,full))
        with safe_open(str(folders[1]/"training.safetensors"),framework="pt",device="cpu") as a, safe_open(
                str(root/"reference"/"training.safetensors"),framework="pt",device="cpu") as b:
            keys=list(a.keys())
            assert keys==list(b.keys()) and "rng.cuda" in keys and "rng.cpu" in keys
            assert any(k.startswith("optim.") for k in keys)
            for key in keys:
                assert torch.equal(a.get_tensor(key),b.get_tensor(key)),key
        metrics=snapshot(queue.path)["rows"]["training_loss"]
        assert [r["step"] for r in metrics]==list(range(1,STEPS+1))
        assert all(r["committed"]==1 and r["seconds"]>0 and r["tokens"]>0 and math.isfinite(r["loss"]) for r in metrics)
        assert [r["loss"] for r in metrics]==[r["loss"] for r in full["history"]]
        report.update(steps=STEPS,checkpoint_count=len(folders),checkpoint_id=done["checkpoint_id"],
            equal_state_tensors=len(keys),peak_cuda_allocated_bytes=max(peaks),history_equal=True,
            scaler_equal=True,process_restart_resume=True,budget_reservations=True,
            committed_metrics=metrics,reference_seconds=reference_seconds,local_gpu_smoke_pass=True)

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--device",default="cuda:0")
    p.add_argument("--precision",choices=["float32","float16","bfloat16"],required=True)
    p.add_argument("--cuda-budget-bytes",type=int,required=True)
    p.add_argument("--approved",action="store_true")
    p.add_argument("--report",type=Path)
    p.add_argument("--worker",choices=["pause","resume"])
    p.add_argument("--worker-root")
    p.add_argument("--job-id")
    args=p.parse_args()
    if not args.approved:
        p.error("explicit local GPU/asset download and disk approval required")
    if args.worker:
        if not args.worker_root or not args.job_id or args.report:
            p.error("invalid internal worker arguments")
        worker(args)
        return
    if not args.report or args.report.exists() or args.worker_root or args.job_id:
        p.error("new report path required")
    report={"schema":"rpdistill-gpu-acceptance-v1","local_gpu_smoke_pass":False,
            "real_cuda_tensor":False,"quality_test":False,"release_ready":False,
            "fixture":"original synthetic translation pairs, full fixed student"}
    try:
        accept(args,report)
    except (Exception,KeyboardInterrupt) as exc:
        report["error"]=type(exc).__name__
        raise
    finally:
        args.report.parent.mkdir(parents=True,exist_ok=True)
        with args.report.open("x",encoding="utf-8") as f:
            json.dump(report,f,ensure_ascii=True,allow_nan=False,indent=2)
        print(json.dumps(report,ensure_ascii=True,allow_nan=False))

if __name__=="__main__":
    main()
