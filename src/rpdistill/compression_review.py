"""Compare verified storage candidates against their exact FP32 source.

All inference is reconstructed FP32. Selection is an engineering candidate
recommendation, never a release authorization or native INT8 benchmark.
"""
from dataclasses import asdict,dataclass
import math
from pathlib import Path
import time

from .compression import load_candidate,layout,pack_tensor,unpack_tensor
from .evaluation import evaluate,validate_benchmark,QualityGate,hash_json
from .quality_review import leakage_audit
from .student import FIXED,StudentCodec,canonical_state
from .student_evaluation import GenerationConfig,generate_one,load_evaluation_model,peak_process_rss


@dataclass(frozen=True)
class RegressionGate:
    max_bleu_drop:float=1.0
    max_chrf_drop:float=1.0
    max_changed_fraction:float=0.10

    def __post_init__(self):
        for name,upper in (("max_bleu_drop",100),("max_chrf_drop",100),("max_changed_fraction",1)):
            v=getattr(self,name)
            if type(v) not in (int,float) or not math.isfinite(v) or not 0<=v<=upper:
                raise ValueError("invalid regression threshold: "+name)


def verify_derivation(source_state,restored,mode,profile):
    """Recompute the declared transform from source, not merely trust manifest IDs."""
    import torch
    target=canonical_state(restored,profile)
    schema=layout(mode,profile)
    for name,value in source_state.items():
        dtype=schema[name]["dtype"]
        packed,scale=pack_tensor(value,dtype)
        expected=unpack_tensor(packed,dtype,scale)
        if not torch.equal(expected,target[name]):
            raise ValueError("candidate differs from exact source conversion: "+name)


def score_model(db_path,benchmark,model,codec,config,deadline,label):
    outputs=[]
    generation=[]
    for case in benchmark["cases"]:
        if time.monotonic()>=deadline:
            raise ValueError("comparison soft time budget exhausted; no selection")
        item=generate_one(model,codec,case["source"],config)
        outputs.append({"id":case["id"],"hypothesis":item["hypothesis"]})
        generation.append({"id":case["id"],**{k:v for k,v in item.items() if k!="hypothesis"}})
    report=evaluate(db_path,benchmark,outputs,gate=QualityGate(),label=label)
    elapsed=sum(r["latency_seconds"] for r in generation)
    return {"evaluation":report,"generation":generation,
            "generation_complete":all(r["finish_reason"]=="eos" for r in generation),
            "total_generation_seconds":elapsed,
            "generated_tokens_per_second":sum(r["generated_tokens"] for r in generation)/elapsed if elapsed else None}


def regression(source,candidate,gate=RegressionGate()):
    """Compare per-case critical checks, absolute coverage and corpus metric deltas."""
    if not isinstance(gate,RegressionGate):
        raise ValueError("invalid regression gate")
    a,b=source["evaluation"],candidate["evaluation"]
    if (a["benchmark_id"]!=b["benchmark_id"] or a["training_dataset"]!=b["training_dataset"]
        or a["gate"]!=b["gate"] or a["metric_versions"]!=b["metric_versions"]
        or a["coverage"]!=b["coverage"] or not a["details"]
        or [r["id"] for r in a["details"]]!=[r["id"] for r in b["details"]]):
        raise ValueError("incomparable evaluations")
    changed=[]
    new_errors=[]
    for x,y in zip(a["details"],b["details"]):
        if x["hypothesis"]!=y["hypothesis"]:
            changed.append(x["id"])
        kinds=[]
        for k in ("numeric_exact","citation_exact"):
            if x[k] and not y[k]:
                kinds.append(k)
        for k in ("term_hits","protected_hits"):
            if y[k]<x[k]:
                kinds.append(k)
        if set(y["suspicious_flags"])-set(x["suspicious_flags"]):
            kinds.append("new_suspicious_flag")
        if kinds:
            new_errors.append({"id":x["id"],"kinds":kinds})
    delta={k:(v-a["metrics"][k] if v is not None and a["metrics"][k] is not None else None)
           for k,v in b["metrics"].items()}
    fraction=len(changed)/len(a["details"])
    failures=[]
    if not source["generation_complete"] or not a["automatic_gate_passed"]:
        failures.append("source_absolute_quality")
    if not candidate["generation_complete"] or not b["automatic_gate_passed"]:
        failures.append("candidate_absolute_quality")
    if delta["bleu"] is None or delta["bleu"] < -gate.max_bleu_drop:
        failures.append("bleu_drop")
    if delta["chrf"] is None or delta["chrf"] < -gate.max_chrf_drop:
        failures.append("chrf_drop")
    if fraction>gate.max_changed_fraction:
        failures.append("changed_fraction")
    if new_errors:
        failures.append("new_case_errors")
    return {"metric_delta":delta,"changed_fraction":fraction,"changed_ids":changed,
            "new_case_errors":new_errors,"failures":failures,"passed":not failures}


def choose(candidates,*,audit_passed):
    """Smallest measured artifact among eligible candidates, deterministic ties."""
    eligible=[c for c in candidates if c["regression"]["passed"] and audit_passed]
    if not eligible:
        return None
    winner=min(eligible,key=lambda c:(c["artifact_bytes"],c["mode"],c["candidate_id"]))
    return {k:winner[k] for k in ("candidate_id","mode","artifact_bytes")}


def compare_candidates(db_path,benchmark,checkpoint,assets,candidates,*,config=GenerationConfig(),
                       gate=RegressionGate(),max_cases=1000,max_seconds=3600,profile=FIXED,codec=None):
    if not isinstance(config,GenerationConfig) or not isinstance(gate,RegressionGate):
        raise ValueError("invalid comparison configuration")
    if type(max_cases) is not int or not 1<=max_cases<=10000:
        raise ValueError("invalid comparison case budget")
    if type(max_seconds) not in (int,float) or not math.isfinite(max_seconds) or not 0<max_seconds<=86400:
        raise ValueError("invalid comparison time budget")
    if not isinstance(candidates,(list,tuple)) or not 1<=len(candidates)<=3:
        raise ValueError("compare one to three candidate directories")
    paths=[Path(p).resolve() for p in candidates]
    if len(set(paths))!=len(paths):
        raise ValueError("duplicate candidate path")
    start=time.monotonic()
    deadline=start+max_seconds
    benchmark=validate_benchmark(db_path,benchmark)
    if len(benchmark["cases"])>max_cases:
        raise ValueError("benchmark exceeds case budget; no partial scoring")
    audit=leakage_audit(db_path,benchmark)
    if codec is None:
        if profile!=FIXED:
            raise ValueError("test profile requires explicit codec")
        codec=StudentCodec.from_assets(assets)
    if codec.profile!=profile:
        raise ValueError("codec profile mismatch")
    source,m=load_evaluation_model(checkpoint,expected_dataset=benchmark["training_dataset"],profile=profile)
    original=canonical_state(source,profile)
    source_score=score_model(db_path,benchmark,source,codec,config,deadline,"FP32 source")
    rows=[]
    modes=set()
    identities=set()
    for path in candidates:
        if time.monotonic()>=deadline:
            raise ValueError("comparison soft time budget exhausted; no selection")
        restored,c=load_candidate(path,dataset_version=benchmark["training_dataset"],
                                  source_checkpoint_id=m["checkpoint_id"],profile=profile)
        mode=c["plan"]["mode"]
        if mode in modes or c["candidate_id"] in identities:
            raise ValueError("duplicate candidate mode or identity")
        modes.add(mode)
        identities.add(c["candidate_id"])
        verify_derivation(original,restored,mode,profile)
        scored=score_model(db_path,benchmark,restored,codec,config,deadline,"candidate "+mode)
        row={"candidate_id":c["candidate_id"],"mode":mode,
             "weights_bytes":c["weights"]["bytes"],
             "artifact_bytes":c["weights"]["bytes"]+(Path(path)/"manifest.json").stat().st_size,
             "weights_sha256":c["weights"]["sha256"],"source_conversion_verified":True,
             "score":scored,"regression":regression(source_score,scored,gate)}
        rows.append(row)
        del restored
    if time.monotonic()>=deadline:
        raise ValueError("comparison soft time budget exhausted; no selection")
    rows.sort(key=lambda r:r["mode"])
    result={"schema":"rpdistill-compression-review-v1","benchmark_id":benchmark["benchmark_id"],
            "training_dataset":benchmark["training_dataset"],"source_checkpoint_id":m["checkpoint_id"],
            "generation_config":asdict(config),"regression_gate":asdict(gate),
            "absolute_gate":asdict(QualityGate()),"lexical_audit":audit,
            "source":source_score,"candidates":rows,
            "selected":choose(rows,audit_passed=audit["passed"]),
            "elapsed_seconds":time.monotonic()-start,"process_peak_rss_bytes":peak_process_rss(),
            "compute_dtype":"float32","native_low_precision_inference":False,
            "rust_deployable":False,"release_ready":False,
            "selection_scope":"smallest passing storage artifact; not deployment or human quality approval",
            "time_budget_scope":"soft checks between cases and candidates; individual operations may exceed budget"}
    return result|{"review_id":hash_json(result)}
