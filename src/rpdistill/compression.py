"""Storage-only compression of verified trained Marian checkpoints.

FP16 and rowwise symmetric INT8 are reconstructed to FP32 for reference
inference. No native low precision kernels, Rust compatibility or release claim.
"""
from dataclasses import asdict
import json
import math
from pathlib import Path
import re
import shutil
import tempfile

from .datasets import encoded
from .evaluation import hash_json
from .student import FIXED,StudentProfile,ALIASES,expected_shapes,canonical_state,build_student
from .student_evaluation import load_evaluation_model
from .transfer import digest_file

SCHEMA="rpdistill-compressed-candidate-v1"
D_AUDIT="5389f3fc33ab45b93f6cab7c7e5bfd17fe43e8e9"
MODES=("fp32","fp16","int8")
OVERHEAD=8*1024*1024


def layout(mode,profile=FIXED):
    if mode not in MODES or not isinstance(profile,StudentProfile):
        raise ValueError("invalid compression mode/profile")
    result={}
    for name,shape in sorted(expected_shapes(profile).items()):
        # Keep bias, layer norm and deterministic position tables in FP32.
        matrix=len(shape)==2 and name.endswith(".weight") and "embed_positions" not in name
        dtype=mode if matrix else "fp32"
        result[name]={"shape":list(shape),"dtype":dtype}
        if dtype=="int8":
            result[name+".row_scale"]={"shape":[shape[0]],"dtype":"fp32"}
    return result


def plan(mode,profile=FIXED):
    tensors=layout(mode,profile)
    sizes={"fp32":4,"fp16":2,"int8":1}
    size=sum(math.prod(v["shape"])*sizes[v["dtype"]] for v in tensors.values())
    original=4*sum(math.prod(s) for s in expected_shapes(profile).values())
    return {"mode":mode,"canonical_tensors":len(expected_shapes(profile)),"stored_tensors":len(tensors),
            "payload_bytes":size,"fp32_payload_bytes":original,"payload_ratio":size/original,
            "rust_deployable":False,"native_low_precision_inference":False,
            "reference_compute_dtype":"float32","d_audit_revision":D_AUDIT}


def pack_tensor(value,mode):
    import torch
    if value.dtype!=torch.float32 or value.device.type!="cpu" or not bool(torch.isfinite(value).all()):
        raise ValueError("invalid source tensor")
    value=value.detach().contiguous()
    if mode=="fp32":
        return value,None
    if mode=="fp16":
        result=value.to(torch.float16)
        if not bool(torch.isfinite(result).all()):
            raise ValueError("FP16 conversion overflow")
        return result,None
    if mode!="int8" or value.ndim!=2:
        raise ValueError("invalid rowwise conversion")
    maximum=value.abs().amax(dim=1)
    scales=torch.where(maximum==0,torch.ones_like(maximum),
                       (maximum/127).clamp_min(torch.finfo(torch.float32).tiny))
    quantized=(value/scales[:,None]).round().clamp(-127,127).to(torch.int8)
    return quantized.contiguous(),scales.contiguous()


def unpack_tensor(value,mode,scale=None):
    import torch
    expected={"fp32":torch.float32,"fp16":torch.float16,"int8":torch.int8}
    if mode not in expected or value.dtype!=expected[mode] or value.device.type!="cpu":
        raise ValueError("invalid compressed tensor dtype")
    if mode=="int8":
        if (value.ndim!=2 or scale is None or scale.dtype!=torch.float32
            or scale.device.type!="cpu" or tuple(scale.shape)!=(value.shape[0],)
            or not bool(torch.isfinite(scale).all()) or not bool((scale>0).all())
            or bool((value==-128).any())):
            raise ValueError("invalid INT8 row scales or values")
        result=value.float()*scale[:,None]
    else:
        if scale is not None:
            raise ValueError("unexpected row scale")
        result=value.float()
    if not bool(torch.isfinite(result).all()):
        raise ValueError("nonfinite reconstructed tensor")
    return result.contiguous()


def difference(original,reconstructed):
    import torch
    maximum=squared=0.0
    a,b=original.reshape(-1),reconstructed.reshape(-1)
    for offset in range(0,a.numel(),1048576):
        d=a[offset:offset+1048576].double()-b[offset:offset+1048576].double()
        maximum=max(maximum,float(d.abs().max()))
        squared+=float((d*d).sum())
    return maximum,squared,a.numel()


def create_candidate(checkpoint,destination,*,dataset_version,mode,max_bytes,profile=FIXED):
    from safetensors.torch import save_file
    spec=plan(mode,profile)
    if not isinstance(dataset_version,str) or not re.fullmatch(r"[a-f0-9]{64}",dataset_version):
        raise ValueError("invalid dataset version")
    if type(max_bytes) is not int or not spec["payload_bytes"]+OVERHEAD<=max_bytes<=2**40:
        raise ValueError("compression budget below conservative requirement")
    dest=Path(destination)
    if dest.exists() or dest.is_symlink():
        raise ValueError("candidate destination exists")
    dest=dest.resolve()
    dest.parent.mkdir(parents=True,exist_ok=True)
    if shutil.disk_usage(dest.parent).free<spec["payload_bytes"]+OVERHEAD:
        raise ValueError("insufficient compression disk space")
    model,source=load_evaluation_model(checkpoint,expected_dataset=dataset_version,profile=profile)
    state=canonical_state(model,profile)
    tensors={}
    errors={}
    schema=layout(mode,profile)
    total_sq=total_count=0
    max_error=0.0
    for name,value in state.items():
        dtype=schema[name]["dtype"]
        packed,scale=pack_tensor(value,dtype)
        tensors[name]=packed
        if scale is not None:
            tensors[name+".row_scale"]=scale
        restored=unpack_tensor(packed,dtype,scale)
        maximum,squared,count=difference(value,restored)
        errors[name]={"max_abs":maximum,"rmse":math.sqrt(squared/count)}
        total_sq+=squared
        total_count+=count
        max_error=max(max_error,maximum)
    manifest={"schema":SCHEMA,"profile":asdict(profile),"plan":spec,"layout":schema,
              "aliases":ALIASES,"source_checkpoint_id":source["checkpoint_id"],
              "training_dataset":dataset_version,"tensor_errors":errors,
              "max_abs_error":max_error,"rmse":math.sqrt(total_sq/total_count),
              "quality_tested":False,"release_ready":False}
    stage=Path(tempfile.mkdtemp(prefix=".rpdistill-compressed-",dir=dest.parent))
    try:
        weights=stage/"weights.safetensors"
        save_file(tensors,str(weights),metadata={"rpdistill_schema":SCHEMA,"storage_mode":mode})
        manifest["weights"]={"bytes":weights.stat().st_size,"sha256":digest_file(weights)}
        manifest["candidate_id"]=hash_json(manifest)
        raw=encoded(manifest).encode()
        if len(raw)>OVERHEAD or len(raw)+weights.stat().st_size>max_bytes:
            raise ValueError("candidate exceeds byte budget")
        (stage/"manifest.json").write_bytes(raw)
        if dest.exists() or dest.is_symlink():
            raise ValueError("candidate destination exists")
        stage.rename(dest)
    finally:
        if stage.exists():
            shutil.rmtree(stage)
    return manifest|{"path":str(dest)}


def load_candidate(root,*,dataset_version,source_checkpoint_id,profile=FIXED):
    """Verify local artifact, reconstruct FP32 model; identity is not a signature."""
    import torch
    from safetensors import safe_open
    root=Path(root)
    meta=root/"manifest.json"
    weights=root/"weights.safetensors"
    if root.is_symlink() or any(p.is_symlink() or not p.is_file() for p in (meta,weights)):
        raise ValueError("invalid compressed candidate files")
    if meta.stat().st_size>OVERHEAD:
        raise ValueError("candidate manifest exceeds budget")
    m=json.loads(meta.read_text(encoding="utf-8"))
    if (m.get("schema")!=SCHEMA or m.get("candidate_id")!=hash_json({k:v for k,v in m.items() if k!="candidate_id"})
        or m.get("profile")!=asdict(profile) or m.get("aliases")!=ALIASES
        or m.get("training_dataset")!=dataset_version or m.get("source_checkpoint_id")!=source_checkpoint_id
        or not re.fullmatch(r"[a-f0-9]{64}",source_checkpoint_id)
        or not re.fullmatch(r"[a-f0-9]{64}",dataset_version)
        or m.get("quality_tested") is not False or m.get("release_ready") is not False):
        raise ValueError("candidate identity mismatch")
    mode=m["plan"]["mode"]
    spec=plan(mode,profile)
    schema=layout(mode,profile)
    size=weights.stat().st_size
    if (m["plan"]!=spec or m["layout"]!=schema or size!=m["weights"]["bytes"]
        or not spec["payload_bytes"]<=size<=spec["payload_bytes"]+OVERHEAD
        or digest_file(weights)!=m["weights"]["sha256"]):
        raise ValueError("candidate payload integrity mismatch")
    expected={"fp32":torch.float32,"fp16":torch.float16,"int8":torch.int8}
    model=build_student(profile)
    state=canonical_state(model,profile)
    with safe_open(str(weights),framework="pt",device="cpu") as f,torch.no_grad():
        if set(f.keys())!=set(schema) or f.metadata()!={"rpdistill_schema":SCHEMA,"storage_mode":mode}:
            raise ValueError("candidate tensor names or metadata mismatch")
        for name,desc in schema.items():
            value=f.get_tensor(name)
            if tuple(value.shape)!=tuple(desc["shape"]) or value.dtype!=expected[desc["dtype"]]:
                raise ValueError("candidate tensor shape or dtype mismatch")
        for name in state:
            dtype=schema[name]["dtype"]
            value=f.get_tensor(name)
            scale=f.get_tensor(name+".row_scale") if dtype=="int8" else None
            state[name].copy_(unpack_tensor(value,dtype,scale))
    canonical_state(model,profile)
    return model.eval(),m
