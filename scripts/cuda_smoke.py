"""Explicit local GPU acceptance. No skip/pass when CUDA unavailable."""
import argparse
import json
import os
from pathlib import Path
import tempfile

# Set before initializing CUDA. Does not alter the user's other processes.
os.environ.setdefault("CUBLAS_WORKSPACE_CONFIG",":4096:8")
import torch
from safetensors.torch import load_file
from rpdistill.student import StudentProfile
from rpdistill.distill import DistillConfig
from rpdistill.resumable import ResumeConfig,run_segment

parser=argparse.ArgumentParser()
parser.add_argument("--device",default="cuda:0")
parser.add_argument("--precision",choices=["float32","float16","bfloat16"],required=True)
parser.add_argument("--cuda-budget-bytes",type=int,required=True)
args=parser.parse_args()
if not args.device.startswith("cuda:"):
    raise SystemExit("GPU acceptance requires explicit CUDA device")
p=StudentProfile(vocab=32,hidden=16,encoder_layers=1,decoder_layers=1,heads=2,ffn=32,positions=32,pad=31)
cfg=ResumeConfig(DistillConfig(steps=7,batch_size=1,learning_rate=0.003,seed=37),
                 accumulation=2,device=args.device,precision=args.precision,
                 cuda_budget_bytes=args.cuda_budget_bytes)
examples=[{"source_ids":[2,i,0],"target_ids":[i+5,0] if i%2 else [i+5,i+6,0]} for i in range(3,8)]
prov={"fixture":"synthetic local GPU targets"}
with tempfile.TemporaryDirectory() as tmp:
    root=Path(tmp)
    def run(name,**kwargs):
        return run_segment(examples,root/name,config=cfg,profile=p,provenance=prov,**kwargs)
    full=run("full")
    partial=run("partial",run_steps=2)
    resumed=run("resumed",resume=root/"partial")
    assert full["status"]==resumed["status"]=="complete" and partial["step"]==2
    a,b=[load_file(str(root/name/"training.safetensors")) for name in ("full","resumed")]
    assert a.keys()==b.keys() and all(torch.equal(a[k],b[k]) for k in a)
    assert "rng.cuda" in a and full["history"]==resumed["history"]
    assert full["scaler_state"]==resumed["scaler_state"]
    assert bool(full["scaler_state"])==(args.precision=="float16")
    print(json.dumps({"device":args.device,"precision":args.precision,"steps":full["step"],
          "equal_state_tensors":len(a),"peak_cuda_allocated_bytes":full["peak_cuda_allocated_bytes"],
          "history_equal":True,"scaler_equal":True,"local_gpu_smoke_pass":True,
          "quality_test":False}))
