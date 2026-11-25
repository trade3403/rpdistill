"""Local student-checkpoint generation on a frozen reference benchmark.

CPU FP32 greedy reference path. No optimizer state is loaded for evaluation.
Scores are not a release certificate or proof of real-world independence.
"""
from dataclasses import asdict,dataclass
import json
import math
from pathlib import Path
import time
import sys

from .distill import load_checkpoint
from .evaluation import evaluate,validate_benchmark,QualityGate,hash_json
from .resumable import SCHEMA,MANIFEST_LIMIT,required_bytes
from .student import FIXED,StudentProfile,StudentCodec,ALIASES,build_student,canonical_state,expected_shapes,contract
from .transfer import digest_file


@dataclass(frozen=True)
class GenerationConfig:
    max_new_tokens:int=128
    max_logits:int=16777216

    def __post_init__(self):
        if type(self.max_new_tokens) is not int or not 1<=self.max_new_tokens<=511:
            raise ValueError("invalid generation length")
        if type(self.max_logits) is not int or not 1<=self.max_logits<=134217728:
            raise ValueError("invalid logits budget")


def load_evaluation_model(root,*,expected_dataset,profile=FIXED):
    """Accept only verified, completed training checkpoints bound to this dataset."""
    import torch
    from safetensors import safe_open
    root=Path(root)
    meta=root/"manifest.json"
    if root.is_symlink() or meta.is_symlink() or not meta.is_file() or meta.stat().st_size>MANIFEST_LIMIT:
        raise ValueError("invalid checkpoint manifest")
    m=json.loads(meta.read_text(encoding="utf-8"))
    if (m.get("checkpoint_id")!=hash_json({k:v for k,v in m.items() if k!="checkpoint_id"})
        or m.get("profile")!=asdict(profile) or m.get("aliases")!=ALIASES
        or m.get("provenance",{}).get("dataset_version")!=expected_dataset
        or m.get("provenance",{}).get("split")!="train"):
        raise ValueError("checkpoint identity, profile or training dataset mismatch")
    if m.get("schema")=="rpdistill-weights-v1":
        model,loaded=load_checkpoint(root)
        if loaded!=m or len(m["history"])!=m["config"]["steps"]:
            raise ValueError("incomplete checkpoint")
        return model,m
    if (m.get("schema")!=SCHEMA or m.get("status")!="complete"
        or m.get("optimizer_saved") is not True or m.get("resume_boundary")!="optimizer_step"
        or type(m.get("step")) is not int or not 1<=m["step"]<=10000
        or m["step"]!=m["config"]["training"]["steps"] or len(m["history"])!=m["step"]):
        raise ValueError("completed training state required")
    path=root/"training.safetensors"
    if (path.is_symlink() or not path.is_file() or path.stat().st_size>required_bytes(profile)
        or path.stat().st_size!=m["tensors"]["bytes"] or digest_file(path)!=m["tensors"]["sha256"]):
        raise ValueError("training checkpoint integrity mismatch")
    shapes=expected_shapes(profile)
    state={}
    with safe_open(str(path),framework="pt",device="cpu") as f:
        if {k for k in f.keys() if k.startswith("model.")}!={"model."+k for k in shapes}:
            raise ValueError("unexpected model tensors")
        for k,shape in shapes.items():
            tensor=f.get_tensor("model."+k)
            if tuple(tensor.shape)!=shape or tensor.dtype!=torch.float32 or not bool(torch.isfinite(tensor).all()):
                raise ValueError("invalid model tensor: "+k)
            state[k]=tensor
        model=build_student(profile,seed=m["config"]["training"]["seed"])
        model.load_state_dict(state|{a:state[k] for a,k in ALIASES.items()},strict=True)
    canonical_state(model,profile)
    return model.eval(),m


def decode_generated(ids,codec):
    """Network piece concatenation follows the audited Rust decode convention.
    Unlike production skip-special decoding, invalid/unknown output is flagged.
    """
    p=codec.profile
    inverse={v:k for k,v in codec.vocab.items()}
    pieces=[]
    for i in ids:
        if type(i) is not int or i not in inverse or i in (p.pad,p.eos,p.unk):
            raise ValueError("invalid generated token")
        piece=inverse[i]
        if piece.startswith(">>") and piece.endswith("<<"):
            raise ValueError("unexpected language token")
        pieces.append(piece)
    return "".join(pieces).replace("▁"," ").strip()


def generate_one(model,codec,source,config=GenerationConfig()):
    import torch
    p=codec.profile
    if config.max_new_tokens>=p.positions or config.max_new_tokens*p.vocab>config.max_logits:
        raise ValueError("generation exceeds positional or logits budget")
    start=time.perf_counter()
    try:
        ids=codec.encode(source)
    except ValueError:
        return {"hypothesis":"","finish_reason":"source_rejected","generated_tokens":0,
                "latency_seconds":time.perf_counter()-start}
    source_ids=torch.tensor([ids],dtype=torch.long)
    mask=torch.ones_like(source_ids)
    generated=[]
    reason="length_limit"
    model.eval()
    with torch.inference_mode():
        encoder=model.get_encoder()(input_ids=source_ids,attention_mask=mask,return_dict=True)
        for _ in range(config.max_new_tokens):
            decoder=torch.tensor([[p.pad]+generated],dtype=torch.long)
            output=model(encoder_outputs=encoder,attention_mask=mask,decoder_input_ids=decoder,
                decoder_attention_mask=torch.ones_like(decoder),use_cache=False,return_dict=True)
            logits=output.logits[0,-1].clone()
            if not bool(torch.isfinite(logits).all()):
                raise ValueError("nonfinite generation logits")
            logits[p.pad]=-torch.inf
            token=int(logits.argmax())
            if token==p.eos:
                reason="eos"
                break
            generated.append(token)
    try:
        text=decode_generated(generated,codec)
    except ValueError:
        text=""
        reason="invalid_output_token"
    return {"hypothesis":text,"finish_reason":reason,"generated_tokens":len(generated),
            "latency_seconds":time.perf_counter()-start}


def peak_process_rss():
    """Process lifetime high-water RSS on Linux/macOS, not model-only or GPU memory."""
    if sys.platform not in ("linux","darwin"):
        return None
    import resource
    value=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    return int(value*(1024 if sys.platform=="linux" else 1))


def evaluate_checkpoint(db_path,benchmark,checkpoint,assets,*,config=GenerationConfig(),
                        gate=QualityGate(),baseline=None,profile=FIXED,codec=None):
    import torch
    benchmark=validate_benchmark(db_path,benchmark)
    if not isinstance(config,GenerationConfig) or not isinstance(gate,QualityGate):
        raise ValueError("invalid evaluation configuration")
    # The CLI always uses pinned fixed-profile assets; injected codec is only a library test seam.
    if codec is None:
        if profile!=FIXED:
            raise ValueError("nonproduction profile requires explicit test codec")
        codec=StudentCodec.from_assets(assets)
    if codec.profile!=profile:
        raise ValueError("codec profile mismatch")
    start=time.perf_counter()
    model,m=load_evaluation_model(checkpoint,expected_dataset=benchmark["training_dataset"],profile=profile)
    load_seconds=time.perf_counter()-start
    outputs=[]
    generation=[]
    for case in benchmark["cases"]:
        item=generate_one(model,codec,case["source"],config)
        outputs.append({"id":case["id"],"hypothesis":item["hypothesis"]})
        generation.append({"id":case["id"],**{k:v for k,v in item.items() if k!="hypothesis"}})
    report=evaluate(db_path,benchmark,outputs,gate=gate,label="local student checkpoint")
    report.pop("report_id")
    failures=[r["id"] for r in generation if r["finish_reason"]!="eos"]
    if failures:
        report["failures"].append("generation:incomplete_or_invalid")
        report["automatic_gate_passed"]=False
    elapsed=sum(r["latency_seconds"] for r in generation)
    times=sorted(r["latency_seconds"] for r in generation)
    report.update(checkpoint_id=m["checkpoint_id"],model_output_generated_locally=True,
        model_output_authenticated=False, # local provenance, not an external signature
        generation_config=asdict(config),generation=generation,
        generation_failures=failures,release_ready=False,
        performance={"device":"cpu","dtype":"float32","threads":torch.get_num_threads(),
            "checkpoint_load_seconds":load_seconds,"total_generation_seconds":elapsed,
            "median_case_seconds":(times[(len(times)-1)//2]+times[len(times)//2])/2,
            "p95_case_seconds":times[math.ceil(len(times)*0.95)-1],
            "generated_tokens_per_second":sum(r["generated_tokens"] for r in generation)/elapsed if elapsed else None,
            "canonical_weight_bytes":contract(profile)["fp32_payload_bytes"],
            "process_peak_rss_bytes":peak_process_rss(),
            "measurement_scope":"single-case greedy no KV cache; RSS is process-lifetime high water, not isolated model memory; unavailable on unsupported OS"})
    if baseline is not None:
        comparison=evaluate(db_path,benchmark,baseline,gate=gate,label="external baseline")
        report["baseline"]={"report_id":comparison["report_id"],"hypotheses_sha256":comparison["hypotheses_sha256"],
            "metrics":comparison["metrics"],"model_output_authenticated":False,
            "delta_student_minus_baseline":{k:(v-comparison["metrics"][k] if v is not None and comparison["metrics"][k] is not None else None)
                                          for k,v in report["metrics"].items()}}
    return report|{"report_id":hash_json(report)}
