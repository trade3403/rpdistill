"""Same-package comparison of original and experimental Rust diagnostic builds."""
import math
from pathlib import Path
import subprocess

from .evaluation import hash_json
from .model_export import verify_package
from .rust_profile import rust_profile,SCHEMA
from .rust_parity import MAX_OUTPUT,D_REFERENCE
from .transfer import digest_file


def compare_profiles(baseline,experiment):
    for field in ("package_id","weights_sha256","d_reference","host","kernel","compute_dtype"):
        if baseline[field]!=experiment[field]:
            raise ValueError("incomparable profiling identity: "+field)
    if (baseline["schema"]!=SCHEMA or experiment["schema"]!=SCHEMA
        or baseline["executable_sha256"]==experiment["executable_sha256"]
        or len(baseline["cases"])!=2 or len(experiment["cases"])!=2):
        raise ValueError("incomparable profile builds")
    rows=[]
    for a,b in zip(baseline["cases"],experiment["cases"]):
        for field in ("source_tokens","max_new_tokens","actual_generated_tokens","greedy_ids","ended",
                      "warmup_repeats","measured_repeats"):
            if a[field]!=b[field]:
                raise ValueError("optimization changed generation workload: "+field)
        if not a["full_cached_token_match"] or not b["full_cached_token_match"]:
            raise ValueError("full and cached generation differ")
        times={}
        for field in ("encoder","full_generation","cached_generation"):
            x,y=a["median_ns"][field],b["median_ns"][field]
            if any(type(v) not in (int,float) or not math.isfinite(v) or v<=0 for v in (x,y)):
                raise ValueError("invalid profile timing")
            times[field]={"baseline_ns":x,"experiment_ns":y,"speedup_ratio":x/y}
        rows.append({"source_tokens":a["source_tokens"],"generated_tokens":a["actual_generated_tokens"],
                     "greedy_ids":a["greedy_ids"],"measurements":times})
    return rows


def raw_diagnostic(exe,args,timeout):
    # Both programs are explicitly trusted local builds with a fixed output protocol.
    # A temporary file avoids unbounded in-memory capture from a faulty program.
    import tempfile
    with tempfile.TemporaryFile() as out:
        result=subprocess.run([str(exe),*args],stdout=out,stderr=subprocess.DEVNULL,timeout=timeout)
        if result.returncode or not 0<out.tell()<=MAX_OUTPUT:
            raise ValueError("diagnostic bridge output invalid")
        out.seek(0)
        return out.read(MAX_OUTPUT+1)


def compare_projection(root,*,expected_package_id,baseline_executable,experiment_executable,
                       timeout_seconds=300,baseline_profile=None):
    if type(timeout_seconds) is not int or not 1<=timeout_seconds<=900:
        raise ValueError("invalid subprocess timeout")
    old=Path(baseline_executable).resolve(strict=True)
    new=Path(experiment_executable).resolve(strict=True)
    if old==new or not old.is_file() or not new.is_file() or digest_file(old)==digest_file(new):
        raise ValueError("two distinct trusted executables required")
    m=verify_package(root,expected_package_id=expected_package_id)
    args=[str(Path(root).resolve()),m["files"]["weights.safetensors"]["sha256"],m["origin"]["checkpoint_id"]]
    original=raw_diagnostic(old,args,timeout_seconds)
    optimized=raw_diagnostic(new,args,timeout_seconds)
    if original!=optimized:
        raise ValueError("experimental full/cached logits or greedy output not bitwise identical")
    if baseline_profile is None:
        baseline_profile=rust_profile(root,expected_package_id=expected_package_id,executable=old,
                                      timeout_seconds=timeout_seconds)
    # A caller-provided baseline is intentionally not trusted unless it binds
    # the exact bytes and current package. The CLI always measures both.
    if (baseline_profile.get("report_id")!=hash_json({k:v for k,v in baseline_profile.items() if k!="report_id"})
        or baseline_profile.get("executable_sha256")!=digest_file(old)
        or baseline_profile.get("package_id")!=expected_package_id):
        raise ValueError("baseline report identity mismatch")
    experiment=rust_profile(root,expected_package_id=expected_package_id,executable=new,
                            timeout_seconds=timeout_seconds)
    rows=compare_profiles(baseline_profile,experiment)
    if verify_package(root,expected_package_id=expected_package_id)!=m:
        raise ValueError("package changed during experiment")
    result={"schema":"rpdistill-projection-experiment-v1","package_id":expected_package_id,
        "weights_sha256":m["files"]["weights.safetensors"]["sha256"],"d_reference":D_REFERENCE,
        "bitwise_diagnostic_parity":True,"diagnostic_bytes":len(original),
        "baseline":baseline_profile,"experiment":experiment,"comparisons":rows,
        "optimization":"bounded vocabulary row parallelism, up to four workers; same FP32 accumulation order",
        "measurement_scope":"sequential builds on same host; timing noise and OS cache uncontrolled; synthetic tokens",
        "speed_threshold_enforced":False,"production_loader_verified":False,"quality_test":False,
        "release_ready":False}
    return result|{"report_id":hash_json(result)}
