"""Bounded local diagnostic parity with a trusted, separately built Rust bridge.

This is not the production RPTranslate loader. Both implementations compute
FP32; no quality or distribution authorization is inferred.
"""
import json
from pathlib import Path
import struct
import subprocess
import tempfile
import time

from .evaluation import hash_json
from .model_export import verify_package
from .student import FIXED,ALIASES,build_student,canonical_state

D_REFERENCE="2fa70c175de7a25415489ecb12ffe3d09485f777"
CASES=(
    ((2,3,0),(True,True,True),(65000,4),(True,True)),
    ((2047,2048,0,65000),(True,True,True,False),(65000,17,65000,4),(True,True,False,True)),
)
ATOL=3e-4
RTOL=3e-4
MAX_OUTPUT=sum((len(s)*512+2*len(t)*65001)*4+20 for s,_,t,_ in CASES)


def read_exact(stream,n):
    result=stream.read(n)
    if len(result)!=n:
        raise ValueError("truncated Rust parity output")
    return result


def compare_tensor(stream,reference):
    import torch
    import numpy as np
    raw=read_exact(stream,reference.numel()*4)
    actual=torch.from_numpy(np.frombuffer(raw,dtype="<f4").copy()).reshape(reference.shape)
    if not bool(torch.isfinite(actual).all()) or not bool(torch.isfinite(reference).all()):
        raise ValueError("nonfinite parity output")
    error=(actual-reference).abs()
    if not bool((error<=ATOL+RTOL*reference.abs()).all()):
        raise ValueError("Rust/Python parity tolerance exceeded: "+str(float(error.max())))
    return {"elements":reference.numel(),"max_abs_error":float(error.max())}


def load_model(root):
    from safetensors.torch import load_file
    model=build_student(FIXED)
    state=load_file(str(Path(root)/"weights.safetensors"),device="cpu")
    model.load_state_dict(state|{a:state[k] for a,k in ALIASES.items()},strict=True)
    canonical_state(model)
    return model.eval()


def rust_parity(root,*,expected_package_id,executable,timeout_seconds=180):
    import torch
    if type(timeout_seconds) is not int or not 1<=timeout_seconds<=900:
        raise ValueError("invalid Rust subprocess timeout")
    # The caller must explicitly select a trusted local executable.
    exe=Path(executable).resolve(strict=True)
    if not exe.is_file():
        raise ValueError("invalid Rust bridge executable")
    start=time.monotonic()
    m=verify_package(root,expected_package_id=expected_package_id)
    args=[str(exe),str(Path(root).resolve()),m["files"]["weights.safetensors"]["sha256"],
          m["origin"]["checkpoint_id"]]
    # The trusted bridge has fixed output size. Use a temp file instead of
    # holding subprocess output in memory; reject unexpected output length.
    with tempfile.TemporaryFile() as stream:
        result=subprocess.run(args,stdout=stream,stderr=subprocess.DEVNULL,timeout=timeout_seconds)
        if result.returncode:
            raise ValueError("Rust candidate bridge failed")
        if stream.tell()>MAX_OUTPUT:
            raise ValueError("Rust parity output exceeds fixed case budget")
        stream.seek(0)
        model=load_model(root)
        cases=[]
        with torch.inference_mode():
            for s,sm,t,tm in CASES:
                source=torch.tensor([s],dtype=torch.long)
                source_mask=torch.tensor([sm],dtype=torch.long)
                target=torch.tensor([t],dtype=torch.long)
                target_mask=torch.tensor([tm],dtype=torch.long)
                encoded=model.get_encoder()(input_ids=source,attention_mask=source_mask,return_dict=True)
                logits=model(encoder_outputs=encoded,attention_mask=source_mask,decoder_input_ids=target,
                    decoder_attention_mask=target_mask,use_cache=False,return_dict=True).logits[0]
                memory=compare_tensor(stream,encoded.last_hidden_state[0])
                full=compare_tensor(stream,logits)
                cached=compare_tensor(stream,logits)
                n=struct.unpack("<I",read_exact(stream,4))[0]
                if not 2<=n<=4:
                    raise ValueError("invalid Rust generated token count")
                actual=list(struct.unpack("<"+"I"*n,read_exact(stream,n*4)))
                prefix=[FIXED.pad]
                for _ in range(3):
                    ids=torch.tensor([prefix],dtype=torch.long)
                    out=model(encoder_outputs=encoded,attention_mask=source_mask,decoder_input_ids=ids,
                        decoder_attention_mask=torch.ones_like(ids),use_cache=False,return_dict=True).logits[0,-1].clone()
                    out[FIXED.pad]=-torch.inf
                    token=int(out.argmax())
                    prefix.append(token)
                    if token==FIXED.eos:
                        break
                if actual!=prefix:
                    raise ValueError("Rust/Python greedy token mismatch")
                cases.append({"memory":memory,"full_logits":full,"cached_logits":cached,
                              "greedy_ids":actual,"greedy_match":True})
        if stream.read(1):
            raise ValueError("trailing Rust parity data")
    report={"schema":"rpdistill-rust-parity-v1","package_id":expected_package_id,
            "weights_sha256":m["files"]["weights.safetensors"]["sha256"],
            "d_reference":D_REFERENCE,"cases":cases,"atol":ATOL,"rtol":RTOL,
            "elapsed_seconds":time.monotonic()-start,"diagnostic_passed":True,
            "production_loader_verified":False,"quality_test":False,"release_ready":False}
    return report|{"report_id":hash_json(report)}
