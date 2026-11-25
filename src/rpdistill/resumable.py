"""E6a deterministic CPU training segments and safe full-state checkpoints.

Exact continuation is tested on the same CPU/software environment, only at
optimizer-step boundaries. No pickle. No CUDA/mixed precision or deployment.
"""
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
import hashlib
import json
import math
from pathlib import Path
import platform
import random
import shutil
import tempfile
import time

from .datasets import encoded
from .distill import DistillConfig, prepare_reviewed_snapshot
from .student import FIXED, StudentProfile, ALIASES, build_student, canonical_state, expected_shapes, contract
from .training_data import batches, tensor_batch
from .transfer import digest_file

SCHEMA="rpdistill-training-state-v1"
HEADER_BUDGET=16*1024*1024
MANIFEST_LIMIT=8*1024*1024


@dataclass(frozen=True)
class ResumeConfig:
    training: DistillConfig=DistillConfig()
    accumulation: int=1

    def __post_init__(self):
        if not isinstance(self.training,DistillConfig):
            raise ValueError("invalid training configuration")
        if type(self.accumulation) is not int or not 1<=self.accumulation<=64:
            raise ValueError("accumulation must be 1–64")


def hash_json(value):
    return hashlib.sha256(encoded(value).encode()).hexdigest()


def environment():
    import torch
    import transformers
    return {"python":platform.python_version(),"platform":platform.system(),
            "machine":platform.machine(),"torch":str(torch.__version__),
            "transformers":str(transformers.__version__),
            "threads":torch.get_num_threads(),"interop_threads":torch.get_num_interop_threads(),
            "matmul_precision":torch.get_float32_matmul_precision(),
            "mkldnn":torch.backends.mkldnn.enabled,
            "device":"cpu","dtype":"float32","deterministic_algorithms":True}


def epoch_groups(examples,profile,config,epoch):
    if type(epoch) is not int or epoch<0:
        raise ValueError("invalid epoch")
    order=list(range(len(examples)))
    random.Random(config.training.seed+epoch).shuffle(order)
    cfg=config.training
    micro=list(batches([examples[i] for i in order],profile,batch_size=cfg.batch_size,
                      max_padded_tokens=cfg.max_padded_tokens,max_logits=cfg.max_logits))
    return [micro[i:i+config.accumulation] for i in range(0,len(micro),config.accumulation)]


def optimizer_for(model,config):
    import torch
    params={name:p for name,p in model.named_parameters() if p.requires_grad}
    opt=torch.optim.AdamW(list(params.values()),lr=config.training.learning_rate,
                          weight_decay=config.training.weight_decay,foreach=False,fused=False)
    return params,opt


def required_bytes(profile):
    # Conservative cap for one checkpoint: weights + 2 FP32 moments + header/RNG/manifest.
    return 3*contract(profile)["fp32_payload_bytes"]+HEADER_BUDGET+MANIFEST_LIMIT


def preflight(destination,profile,max_checkpoint_bytes):
    destination=Path(destination)
    if destination.exists() or destination.is_symlink():
        raise ValueError("checkpoint destination already exists")
    if type(max_checkpoint_bytes) is not int or not required_bytes(profile)<=max_checkpoint_bytes<=2**40:
        raise ValueError("checkpoint budget below conservative required size")
    destination.parent.mkdir(parents=True,exist_ok=True)
    if shutil.disk_usage(destination.parent).free<required_bytes(profile):
        raise ValueError("insufficient checkpoint disk space")
    return destination.resolve()


def optimizer_tensors(params,opt,step):
    import torch
    tensors={}
    names=[]
    for name,p in params.items():
        state=opt.state.get(p)
        if not state:
            continue
        if set(state)!={"step","exp_avg","exp_avg_sq"}:
            raise ValueError("unexpected optimizer state")
        for key in ("step","exp_avg","exp_avg_sq"):
            v=state[key]
            if (v.dtype!=torch.float32 or not bool(torch.isfinite(v).all())
                or (key=="step" and (v.ndim!=0 or not 1<=float(v)<=step or float(v)!=int(v)))
                or (key!="step" and v.shape!=p.shape)
                or (key=="exp_avg_sq" and bool((v<0).any()))):
                raise ValueError("invalid optimizer tensor")
            tensors["optim."+name+"."+key]=v.detach().cpu().contiguous()
        names.append(name)
    if step and not names:
        raise ValueError("optimizer state missing")
    return tensors,names


def publish(destination,model,params,opt,profile,config,history,epoch,cursor,rng,
            data_hash,provenance,max_checkpoint_bytes,stop_reason):
    from safetensors.torch import save_file
    destination=preflight(destination,profile,max_checkpoint_bytes)
    state=canonical_state(model,profile)
    optimizer,names=optimizer_tensors(params,opt,len(history))
    tensors={"model."+k:v.detach().cpu().contiguous() for k,v in state.items()}
    tensors.update(optimizer)
    tensors["rng.cpu"]=rng.contiguous()
    manifest={"schema":SCHEMA,"created_at":datetime.now(timezone.utc).isoformat(),
              "profile":asdict(profile),"config":asdict(config),"environment":environment(),
              "data_sha256":data_hash,"provenance":provenance,
              "step":len(history),"epoch":epoch,"cursor":cursor,"history":history,
              "optimizer_names":names,"aliases":ALIASES,"optimizer_saved":True,
              "resume_boundary":"optimizer_step","rust_deployable":False,
              "status":"complete" if len(history)==config.training.steps else "paused",
              "stop_reason":stop_reason}
    stage=Path(tempfile.mkdtemp(prefix=".rpdistill-training-",dir=destination.parent))
    try:
        path=stage/"training.safetensors"
        save_file(tensors,str(path),metadata={"rpdistill_schema":SCHEMA})
        manifest["tensors"]={"bytes":path.stat().st_size,"sha256":digest_file(path)}
        manifest["checkpoint_id"]=hash_json(manifest)
        raw=encoded(manifest).encode()
        if len(raw)>MANIFEST_LIMIT or len(raw)+path.stat().st_size>max_checkpoint_bytes:
            raise ValueError("checkpoint exceeds approved budget")
        (stage/"manifest.json").write_bytes(raw)
        if destination.exists() or destination.is_symlink():
            raise ValueError("checkpoint destination already exists")
        stage.rename(destination)
    finally:
        if stage.exists():
            shutil.rmtree(stage)
    return manifest | {"path":str(destination)}


def restore(root,profile,config,examples,provenance):
    import torch
    from safetensors.torch import load_file
    root=Path(root)
    meta=root/"manifest.json"
    path=root/"training.safetensors"
    if any(p.is_symlink() or not p.is_file() for p in (meta,path)) or root.is_symlink():
        raise ValueError("invalid checkpoint files")
    if meta.stat().st_size>MANIFEST_LIMIT:
        raise ValueError("manifest exceeds limit")
    m=json.loads(meta.read_text(encoding="utf-8"))
    if (m.get("schema")!=SCHEMA or m.get("checkpoint_id")!=hash_json({k:v for k,v in m.items() if k!="checkpoint_id"})
        or m.get("profile")!=asdict(profile) or m.get("config")!=asdict(config)
        or m.get("environment")!=environment() or m.get("data_sha256")!=hash_json(examples)
        or m.get("provenance")!=provenance or m.get("aliases")!=ALIASES
        or m.get("optimizer_saved") is not True or m.get("resume_boundary")!="optimizer_step"):
        raise ValueError("training checkpoint identity or environment mismatch")
    step,epoch,cursor=m["step"],m["epoch"],m["cursor"]
    if (type(step) is not int or not 1<=step<config.training.steps
        or type(epoch) is not int or not 0<=epoch<=step
        or type(cursor) is not int or cursor<0 or m.get("status")!="paused"
        or len(m["history"])!=step):
        raise ValueError("invalid or completed checkpoint progress")
    for i,h in enumerate(m["history"],1):
        if h.get("step")!=i or not math.isfinite(h["loss"]) or not math.isfinite(h["gradient_norm"]):
            raise ValueError("invalid history")
    # Replay only deterministic group counts; no optimizer work or network.
    if cursor>=len(epoch_groups(examples,profile,config,epoch)):
        raise ValueError("invalid batch cursor")
    expected_steps=sum(len(epoch_groups(examples,profile,config,i)) for i in range(epoch))+cursor
    if expected_steps!=step:
        raise ValueError("checkpoint cursor and step disagree")
    if (path.stat().st_size!=m["tensors"]["bytes"] or path.stat().st_size>required_bytes(profile)
        or digest_file(path)!=m["tensors"]["sha256"]):
        raise ValueError("checkpoint tensor integrity mismatch")
    state=load_file(str(path),device="cpu")
    model=build_student(profile,seed=config.training.seed)
    params,opt=optimizer_for(model,config)
    shapes=expected_shapes(profile)
    names=m["optimizer_names"]
    if not isinstance(names,list) or not names or len(names)!=len(set(names)) or not set(names)<=set(params):
        raise ValueError("invalid optimizer names")
    keys={"model."+k for k in shapes}|{"rng.cpu"}|{"optim."+n+"."+k for n in names for k in ("step","exp_avg","exp_avg_sq")}
    if set(state)!=keys:
        raise ValueError("unexpected checkpoint tensors")
    canonical={}
    for k,shape in shapes.items():
        v=state["model."+k]
        if tuple(v.shape)!=shape or v.dtype!=torch.float32 or not bool(torch.isfinite(v).all()):
            raise ValueError("invalid model tensor")
        canonical[k]=v
    model.load_state_dict(canonical|{a:canonical[k] for a,k in ALIASES.items()},strict=True)
    for name in names:
        opt.state[params[name]]={k:state["optim."+name+"."+k].clone() for k in ("step","exp_avg","exp_avg_sq")}
    optimizer_tensors(params,opt,step)
    rng=state["rng.cpu"]
    if rng.dtype!=torch.uint8 or rng.shape!=torch.random.get_rng_state().shape:
        raise ValueError("invalid CPU RNG state")
    return model,params,opt,list(m["history"]),epoch,cursor,rng


def run_segment(examples,destination,*,config=ResumeConfig(),profile=FIXED,provenance,
                resume=None,run_steps=100,max_seconds=3600,max_checkpoint_bytes=2**30):
    """Train a bounded segment, atomically publish a complete state at a step boundary."""
    import torch
    if not isinstance(config,ResumeConfig) or not isinstance(profile,StudentProfile):
        raise ValueError("invalid config/profile")
    if not isinstance(examples,(list,tuple)) or not 1<=len(examples)<=10000:
        raise ValueError("invalid example count")
    if type(run_steps) is not int or not 1<=run_steps<=10000:
        raise ValueError("invalid segment steps")
    if type(max_seconds) not in (int,float) or not math.isfinite(max_seconds) or not 0<max_seconds<=86400:
        raise ValueError("invalid time budget")
    preflight(destination,profile,max_checkpoint_bytes)
    data_hash=hash_json(examples)
    encoded(provenance)
    groups=epoch_groups(examples,profile,config,0)
    if not groups:
        raise ValueError("no training batches")
    cfg=config.training
    previous=torch.are_deterministic_algorithms_enabled()
    warn=torch.is_deterministic_algorithms_warn_only_enabled()
    start=time.monotonic()
    torch.use_deterministic_algorithms(True)
    try:
        with torch.random.fork_rng(devices=[]):
            if resume:
                model,params,opt,history,epoch,cursor,rng=restore(resume,profile,config,examples,provenance)
                torch.random.set_rng_state(rng)
            else:
                model=build_student(profile,seed=cfg.seed)
                params,opt=optimizer_for(model,config)
                history,epoch,cursor=[],0,0
                torch.manual_seed(cfg.seed)
            model.train()
            end=min(cfg.steps,len(history)+run_steps)
            reason="segment_steps"
            groups=epoch_groups(examples,profile,config,epoch)
            while len(history)<end:
                group=groups[cursor]
                total_tokens=sum(sum(i!=-100 for row in b["labels"] for i in row) for b in group)
                opt.zero_grad(set_to_none=True)
                weighted=0.0
                for arrays in group:
                    batch=tensor_batch(arrays)
                    n=int((batch["labels"]!=-100).sum())
                    loss=model(**batch,use_cache=False).loss
                    if loss is None or not bool(torch.isfinite(loss)):
                        raise ValueError("nonfinite loss")
                    (loss*(n/total_tokens)).backward()
                    weighted+=float(loss.detach())*n
                grad=torch.nn.utils.clip_grad_norm_(list(params.values()),cfg.max_grad_norm,error_if_nonfinite=True)
                opt.step()
                history.append({"step":len(history)+1,"epoch":epoch+1,"loss":weighted/total_tokens,
                    "gradient_norm":float(grad),"supervised_tokens":total_tokens,"microbatches":len(group)})
                cursor+=1
                if cursor==len(groups):
                    epoch+=1
                    cursor=0
                    if len(history)<end:
                        groups=epoch_groups(examples,profile,config,epoch)
                if time.monotonic()-start>=max_seconds:
                    reason="time_budget_boundary"
                    break
            if len(history)==cfg.steps:
                reason="target_steps"
            opt.zero_grad(set_to_none=True)
            model.eval()
            return publish(destination,model,params,opt,profile,config,history,epoch,cursor,
                torch.random.get_rng_state(),data_hash,provenance,max_checkpoint_bytes,reason)
    finally:
        torch.use_deterministic_algorithms(previous,warn_only=warn)


def train_reviewed_segment(db_path,version,assets,destination,*,reviewed_dataset,
                           reviewed_teacher_license,config=ResumeConfig(),limit=1000,**kwargs):
    examples,provenance=prepare_reviewed_snapshot(db_path,version,assets,
        reviewed_dataset=reviewed_dataset,reviewed_teacher_license=reviewed_teacher_license,limit=limit)
    return run_segment(examples,destination,config=config,profile=FIXED,provenance=provenance,**kwargs)
