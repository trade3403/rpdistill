"""Sequence-level distillation from approved teacher translations.

CPU FP32 first; checkpoint is weights-only, NOT an exact optimizer/RNG resume.
No pickle and no production package claims.
"""
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
import hashlib
import json
import math
from pathlib import Path
import random
import shutil
import tempfile

from .student import FIXED, StudentProfile, ALIASES, build_student, canonical_state, expected_shapes, contract, StudentCodec
from .training_data import batches, tensor_batch, snapshot_examples
from .datasets import DatasetStore, encoded
from .teachers import TeacherRegistry
from .transfer import digest_file


@dataclass(frozen=True)
class DistillConfig:
    steps: int = 20
    batch_size: int = 1
    learning_rate: float = 1e-4
    weight_decay: float = 0.01
    max_grad_norm: float = 1.0
    seed: int = 42
    max_padded_tokens: int = 4096
    max_logits: int = 16777216

    def __post_init__(self):
        for name,upper in (("steps",10000),("batch_size",64),("max_padded_tokens",65536),
                           ("max_logits",134217728)):
            v=getattr(self,name)
            if type(v) is not int or not 1<=v<=upper:
                raise ValueError("invalid "+name)
        if type(self.seed) is not int or not 0<=self.seed<2**32:
            raise ValueError("invalid seed")
        for name,lo,hi in (("learning_rate",1e-8,0.1),("weight_decay",0,1),
                           ("max_grad_norm",1e-6,100)):
            v=getattr(self,name)
            if type(v) not in (int,float) or not math.isfinite(v) or not lo<=v<=hi:
                raise ValueError("invalid "+name)


def train_sequence(model,examples,config=DistillConfig(),profile=FIXED):
    """Train on already authorized, tokenized targets. Returns actual measured metrics."""
    import torch
    if not isinstance(config,DistillConfig) or not isinstance(profile,StudentProfile):
        raise ValueError("invalid training configuration")
    if not isinstance(examples,(list,tuple)) or not 1<=len(examples)<=10000:
        raise ValueError("expected 1–10000 training examples")
    canonical_state(model,profile)
    if any(p.device.type!="cpu" for p in model.parameters()):
        raise ValueError("E5 currently supports CPU FP32 only")
    # Validate every example/budget before mutating parameters.
    for _ in batches(examples,profile,batch_size=config.batch_size,
                     max_padded_tokens=config.max_padded_tokens,max_logits=config.max_logits):
        pass
    model.train()
    params=[p for p in model.parameters() if p.requires_grad]
    optim=torch.optim.AdamW(params,lr=config.learning_rate,weight_decay=config.weight_decay)
    rng=random.Random(config.seed)
    history=[]
    epoch=0
    with torch.random.fork_rng(devices=[]):
        torch.manual_seed(config.seed)
        while len(history)<config.steps:
            epoch+=1
            order=list(range(len(examples)))
            rng.shuffle(order)
            shuffled=[examples[i] for i in order]
            for arrays in batches(shuffled,profile,batch_size=config.batch_size,
                                  max_padded_tokens=config.max_padded_tokens,max_logits=config.max_logits):
                batch=tensor_batch(arrays)
                tokens=int((batch["labels"]!=-100).sum().item())
                optim.zero_grad(set_to_none=True)
                out=model(**batch,use_cache=False)
                loss=out.loss
                if loss is None or loss.ndim!=0 or not bool(torch.isfinite(loss)):
                    raise ValueError("nonfinite training loss")
                loss.backward()
                grad=torch.nn.utils.clip_grad_norm_(params,config.max_grad_norm,error_if_nonfinite=True)
                optim.step()
                history.append({"step":len(history)+1,"epoch":epoch,"loss":float(loss.detach()),
                                "gradient_norm":float(grad),"supervised_tokens":tokens})
                if len(history)>=config.steps:
                    break
    canonical_state(model,profile)
    optim.zero_grad(set_to_none=True)
    model.eval()
    return history


def eval_loss(model,examples,profile=FIXED,*,batch_size=1,max_logits=16777216,max_padded_tokens=4096):
    """Token-weighted evaluation loss; no parameter changes."""
    import torch
    previous=model.training
    model.eval()
    total=tokens=0
    try:
        with torch.no_grad():
            for arrays in batches(examples,profile,batch_size=batch_size,max_logits=max_logits,
                                  max_padded_tokens=max_padded_tokens):
                batch=tensor_batch(arrays)
                n=int((batch["labels"]!=-100).sum().item())
                loss=model(**batch,use_cache=False).loss
                if not bool(torch.isfinite(loss)):
                    raise ValueError("nonfinite evaluation loss")
                total+=float(loss)*n
                tokens+=n
    finally:
        model.train(previous)
    if not tokens:
        raise ValueError("empty evaluation")
    return {"loss":total/tokens,"supervised_tokens":tokens}


def save_checkpoint(model,profile,config,history,destination,*,provenance):
    """Publish an immutable, verified local SafeTensors weights-only checkpoint."""
    from safetensors.torch import save_file
    destination=Path(destination)
    if destination.exists() or destination.is_symlink():
        raise ValueError("checkpoint destination already exists")
    destination=destination.resolve()
    destination.parent.mkdir(parents=True,exist_ok=True)
    state=canonical_state(model,profile)
    expected=contract(profile)["fp32_payload_bytes"]
    if shutil.disk_usage(destination.parent).free<expected+16*1024*1024:
        raise ValueError("insufficient checkpoint disk space")
    if not isinstance(history,list) or len(history)!=config.steps:
        raise ValueError("incomplete training history")
    for i,item in enumerate(history,1):
        if item.get("step")!=i or not math.isfinite(item["loss"]) or not math.isfinite(item["gradient_norm"]):
            raise ValueError("invalid training history")
    # JSON serialization rejects nonfinite data before writing.
    manifest={"schema":"rpdistill-weights-v1","created_at":datetime.now(timezone.utc).isoformat(),
              "profile":asdict(profile),"config":asdict(config),"provenance":provenance,
              "history":history,"aliases":ALIASES,"optimizer_saved":False,
              "exact_resume":False,"rust_deployable":False,"payload_bytes":expected}
    encoded(manifest)
    stage=Path(tempfile.mkdtemp(prefix=".rpdistill-checkpoint-",dir=destination.parent))
    try:
        path=stage/"student.safetensors"
        save_file({k:v.detach().cpu().contiguous() for k,v in state.items()},str(path),
                  metadata={"format":"pt","rpdistill_schema":"weights-v1"})
        manifest["weights"]={"bytes":path.stat().st_size,"sha256":digest_file(path)}
        manifest["checkpoint_id"]=hashlib.sha256(encoded(manifest).encode()).hexdigest()
        raw=encoded(manifest).encode()
        if len(raw)>8*1024*1024:
            raise ValueError("checkpoint manifest too large")
        (stage/"manifest.json").write_bytes(raw)
        if destination.exists() or destination.is_symlink():
            raise ValueError("checkpoint destination already exists")
        stage.rename(destination)
    finally:
        if stage.exists():
            shutil.rmtree(stage)
    return manifest | {"path":str(destination)}


def load_checkpoint(root):
    """Reconstruct the exact student weights on CPU, not optimizer state."""
    import torch
    from safetensors.torch import load_file
    root=Path(root)
    path=root/"student.safetensors"
    meta=root/"manifest.json"
    if root.is_symlink() or path.is_symlink() or meta.is_symlink():
        raise ValueError("symlink checkpoint rejected")
    if meta.stat().st_size>8*1024*1024:
        raise ValueError("manifest exceeds limit")
    manifest=json.loads(meta.read_text(encoding="utf-8"))
    identity=manifest.get("checkpoint_id")
    if (manifest.get("schema")!="rpdistill-weights-v1"
        or hashlib.sha256(encoded({k:v for k,v in manifest.items() if k!="checkpoint_id"}).encode()).hexdigest()!=identity
        or manifest.get("aliases")!=ALIASES or manifest.get("exact_resume") is not False
        or manifest.get("optimizer_saved") is not False):
        raise ValueError("checkpoint manifest integrity mismatch")
    profile=StudentProfile(**manifest["profile"])
    config=DistillConfig(**manifest["config"])
    payload=contract(profile)["fp32_payload_bytes"]
    if (manifest["payload_bytes"]!=payload or path.stat().st_size!=manifest["weights"]["bytes"]
        or not payload<=path.stat().st_size<=payload+8*1024*1024
        or digest_file(path)!=manifest["weights"]["sha256"]):
        raise ValueError("checkpoint weight integrity mismatch")
    state=load_file(str(path),device="cpu")
    shapes=expected_shapes(profile)
    if set(state)!=set(shapes):
        raise ValueError("checkpoint tensor names mismatch")
    for k,v in state.items():
        if tuple(v.shape)!=shapes[k] or v.dtype!=torch.float32 or not bool(torch.isfinite(v).all()):
            raise ValueError("invalid checkpoint tensor: "+k)
    model=build_student(profile,seed=config.seed)
    model.load_state_dict(state | {a:state[k] for a,k in ALIASES.items()},strict=True)
    canonical_state(model,profile)
    model.eval()
    return model,manifest


def prepare_reviewed_snapshot(db_path,version,assets,*,reviewed_dataset,
                              reviewed_teacher_license,limit=1000):
    """Explicit operator authorization required; review is asserted, not certified by software."""
    if reviewed_dataset!=version:
        raise ValueError("explicit review of exact dataset version required")
    manifest=next((m for m in DatasetStore(db_path).list() if m["version"]==version),None)
    if manifest is None:
        raise KeyError("unknown dataset version")
    teacher=manifest["teacher"]
    registered=TeacherRegistry(db_path,source=teacher["source"]).get(teacher["model_id"],teacher["revision"])
    if not reviewed_teacher_license or registered.get("license")!=reviewed_teacher_license:
        raise ValueError("teacher license review must match registered license")
    if (manifest.get("options",{}).get("source_language")!="English"
        or manifest.get("options",{}).get("target_language")!="Chinese"):
        raise ValueError("student requires English–Chinese data")
    codec=StudentCodec.from_assets(assets)
    examples,stats=snapshot_examples(db_path,version,codec,split="train",limit=limit)
    if not examples or stats["excluded"]:
        raise ValueError("selected training examples failed current integrity or tokenization")
    if stats["accepted"]<manifest["gate"]["min_train"]:
        raise ValueError("insufficient accepted training examples")
    # No validation or test examples enter the optimizer.
    provenance={"dataset_version":version,"teacher":teacher,"reviewed_teacher_license":reviewed_teacher_license,
                "operator_review_asserted":True,"split":"train","selected":stats,
                "training_pair_ids_sha256":hashlib.sha256(encoded([e["pair_id"] for e in examples]).encode()).hexdigest(),
                "initialization":"random","method":"sequence-level teacher-target cross-entropy",
                "quality_certified":False}
    return examples,provenance


def train_reviewed_snapshot(db_path,version,assets,destination,*,reviewed_dataset,
                            reviewed_teacher_license,config=DistillConfig(),limit=1000):
    if Path(destination).exists() or Path(destination).is_symlink():
        raise ValueError("checkpoint destination already exists")
    examples,provenance=prepare_reviewed_snapshot(db_path,version,assets,
        reviewed_dataset=reviewed_dataset,reviewed_teacher_license=reviewed_teacher_license,limit=limit)
    model=build_student(FIXED,seed=config.seed)
    history=train_sequence(model,examples,config,FIXED)
    return save_checkpoint(model,FIXED,config,history,destination,provenance=provenance)
