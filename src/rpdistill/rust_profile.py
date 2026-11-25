"""Fixed, bounded Rust CPU diagnostic profiling, not a release benchmark."""
import os
from pathlib import Path
import platform
import statistics
import subprocess
import tempfile
import time

from .evaluation import hash_json
from .model_export import verify_package
from .rust_parity import D_REFERENCE
from .student import FIXED
from .transfer import digest_file

SCHEMA="rpdistill-rust-profile-v1"
LOAD_FIELDS=("assets_and_config","weight_hash","header_and_shapes","embeddings_load","encoder_load","decoder_load")
CASE_FIELDS=("encoder","decoder_prepare","full_generation","cached_generation")
CASES=((16,8),(64,16))
MAX_OUTPUT=16384


def positive_int(text,maximum=2**63-1,*,allow_zero=False):
    if not isinstance(text,str) or not text.isascii() or not text.isdecimal() or len(text)>19:
        raise ValueError("invalid profile integer")
    n=int(text)
    if not (0 if allow_zero else 1)<=n<=maximum:
        raise ValueError("profile integer outside range")
    return n


def parse_profile(raw):
    if not isinstance(raw,bytes) or len(raw)>MAX_OUTPUT:
        raise ValueError("profile output exceeds budget")
    lines=raw.decode("ascii").splitlines()
    if len(lines)!=9 or lines[0]!="rpdistill-profile-v1":
        raise ValueError("invalid profile protocol")
    load=lines[1].split("\t")
    if len(load)!=7 or load[0]!="load":
        raise ValueError("invalid load profile")
    load_ns=dict(zip(LOAD_FIELDS,[positive_int(v,allow_zero=True) for v in load[1:]]))
    cases=[]
    for i,(source_len,max_new) in enumerate(CASES):
        runs=[]
        expected=None
        for repeat in (1,2,3):
            row=lines[2+3*i+repeat-1].split("\t")
            if len(row)!=10 or row[0]!="case" or tuple(positive_int(v) for v in row[1:4])!=(source_len,max_new,repeat):
                raise ValueError("invalid profile case identity")
            times=dict(zip(CASE_FIELDS,[positive_int(v) for v in row[4:8]]))
            if row[8] not in ("true","false"):
                raise ValueError("invalid generation end flag")
            ended=row[8]=="true"
            ids=[positive_int(v,FIXED.vocab-1,allow_zero=True) for v in row[9].split(",")]
            if (not 2<=len(ids)<=max_new+1 or ids[0]!=FIXED.pad
                or FIXED.pad in ids[1:] or FIXED.eos in ids[1:-1]
                or ended!=(ids[-1]==FIXED.eos) or (not ended and len(ids)!=max_new+1)):
                raise ValueError("invalid generated IDs")
            if expected is None:
                expected=ids
            elif ids!=expected:
                raise ValueError("profile repeat generation differs")
            runs.append({"repeat":repeat,"order":"cached_first" if repeat%2 else "full_first",
                         "times_ns":times})
        med={k:statistics.median(r["times_ns"][k] for r in runs) for k in CASE_FIELDS}
        tokens=len(expected)-1
        cases.append({"source_tokens":source_len,"max_new_tokens":max_new,
            "actual_generated_tokens":tokens,"greedy_ids":expected,"ended":ended,
            "full_cached_token_match":True,"warmup_repeats":1,"measured_repeats":3,
            "runs":runs,"median_ns":med,
            "cached_speedup_ratio":med["full_generation"]/med["cached_generation"],
            "full_tokens_per_second":tokens*1e9/med["full_generation"],
            "cached_tokens_per_second":tokens*1e9/med["cached_generation"]})
    rss=lines[-1].split("\t")
    if len(rss)!=2 or rss[0]!="rss":
        raise ValueError("invalid memory profile")
    return {"load_ns":load_ns,"cases":cases,
            "rust_process_peak_rss_bytes":positive_int(rss[1],allow_zero=True) or None}


def rust_profile(root,*,expected_package_id,executable,timeout_seconds=180):
    if type(timeout_seconds) is not int or not 1<=timeout_seconds<=900:
        raise ValueError("invalid Rust subprocess timeout")
    exe=Path(executable).resolve(strict=True)
    if not exe.is_file():
        raise ValueError("invalid trusted bridge")
    start=time.monotonic()
    manifest=verify_package(root,expected_package_id=expected_package_id)
    verify_seconds=time.monotonic()-start
    exe_hash=digest_file(exe)
    args=[str(exe),str(Path(root).resolve()),manifest["files"]["weights.safetensors"]["sha256"],
          manifest["origin"]["checkpoint_id"],"--profile"]
    start=time.monotonic()
    with tempfile.TemporaryFile() as out:
        proc=subprocess.run(args,stdout=out,stderr=subprocess.DEVNULL,timeout=timeout_seconds)
        if proc.returncode or out.tell()>MAX_OUTPUT:
            raise ValueError("Rust profiling failed or output exceeds budget")
        out.seek(0)
        measurements=parse_profile(out.read(MAX_OUTPUT+1))
    result={"schema":SCHEMA,"package_id":expected_package_id,
            "weights_sha256":manifest["files"]["weights.safetensors"]["sha256"],
            "executable_sha256":exe_hash,"d_reference":D_REFERENCE,
            "host":{"system":platform.system(),"machine":platform.machine(),"logical_cpus":os.cpu_count()},
            "python_package_verify_seconds":verify_seconds,"rust_subprocess_seconds":time.monotonic()-start,
            **measurements,"kernel":"Auto","compute_dtype":"float32",
            "measurement_scope":"fixed synthetic token workloads; warmups excluded; OS file cache uncontrolled; load once per subprocess; RSS Linux process high water",
            "trusted_executable_required":True,"quality_test":False,"production_loader_verified":False,
            "release_ready":False}
    return result|{"report_id":hash_json(result)}
