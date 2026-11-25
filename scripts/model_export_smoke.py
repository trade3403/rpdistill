"""Full fixed-shape actual one-step synthetic CPU training and Rust byte roundtrip.

No official model weights are downloaded. This is NOT a quality benchmark or
production loader test. Only the five pinned tokenizer/config assets are fetched.
"""
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile

import torch
from safetensors import safe_open
from rpdistill.student import FIXED,build_student,canonical_state
from rpdistill.distill import DistillConfig,train_sequence,save_checkpoint
from rpdistill.training_data import acquire_assets,ASSET_BYTES
from rpdistill.model_export import export_candidate,verify_package,REQUIRED_BYTES,PAYLOAD
from rpdistill.rust_parity import rust_parity

torch.set_num_threads(2)
exe=Path(sys.argv[1]).resolve()
official=Path(sys.argv[2]).resolve()
bridge=Path(sys.argv[3]).resolve()
with tempfile.TemporaryDirectory() as tmp:
    root=Path(tmp)
    assets=root/"assets"
    acquire_assets(assets,max_bytes=ASSET_BYTES+1048576)
    cfg=DistillConfig(steps=1,batch_size=1,learning_rate=1e-4,seed=42)
    model=build_student(FIXED,seed=cfg.seed)
    before=canonical_state(model)["model.shared.weight"][3].clone()
    history=train_sequence(model,[{"source_ids":[2,3,0],"target_ids":[4,0]}],cfg,FIXED)
    assert not torch.equal(before,canonical_state(model)["model.shared.weight"][3])
    version="a"*64
    source=save_checkpoint(model,FIXED,cfg,history,root/"checkpoint",
                           provenance={"dataset_version":version,"split":"train",
                                       "fixture":"synthetic token targets; no quality or rights certification"})
    del model
    package=export_candidate(root/"checkpoint",assets,root/"candidate",dataset_version=version,
                              license_label="internal-test-only",rights_note="Synthetic CI fixture only",
                              max_bytes=REQUIRED_BYTES,acknowledge_candidate_only=True)
    m=verify_package(root/"candidate",expected_package_id=package["package_id"])
    assert m["origin"]["checkpoint_id"]==source["checkpoint_id"]
    assert m["release_ready"] is False and m["plan"]["rust_deployable"] is False
    expected=hashlib.sha256()
    weights=root/"candidate"/"weights.safetensors"
    with safe_open(str(weights),framework="pt",device="cpu") as f, safe_open(
            str(root/"checkpoint"/"student.safetensors"),framework="pt",device="cpu") as original:
        assert set(f.keys())==set(original.keys())
        for name in sorted(f.keys()):
            a=f.get_tensor(name)
            assert torch.equal(a,original.get_tensor(name))
            flat=a.reshape(-1)
            for offset in range(0,flat.numel(),1048576):
                expected.update(flat[offset:offset+1048576].numpy().astype("<f4",copy=False).tobytes())
    actual=hashlib.sha256()
    count=0
    with subprocess.Popen([str(exe),str(weights)],stdout=subprocess.PIPE) as proc:
        while chunk:=proc.stdout.read(1024*1024):
            count+=len(chunk)
            if count>PAYLOAD:
                proc.kill()
                raise AssertionError("Rust payload overflow")
            actual.update(chunk)
        assert proc.wait()==0
    assert count==PAYLOAD and actual.hexdigest()==expected.hexdigest()
    parity=rust_parity(root/"candidate",expected_package_id=m["package_id"],executable=bridge)
    assert parity["diagnostic_passed"] and len(parity["cases"])==2
    assert all(r["greedy_match"] for r in parity["cases"])
    for wrong_weight,wrong_checkpoint in (("0"*64,m["origin"]["checkpoint_id"]),
                                          (m["files"]["weights.safetensors"]["sha256"],"0"*64)):
        rejected_pin=subprocess.run([str(bridge),str(root/"candidate"),wrong_weight,wrong_checkpoint],
                                    capture_output=True,timeout=180)
        assert rejected_pin.returncode!=0 and not rejected_pin.stdout
    print(json.dumps({"actual_rust_inference":True,"wrong_weight_and_checkpoint_pin_rejected":True,
        "parity":parity}))
    # Current official package loader MUST reject the distinct package.
    rejected=subprocess.run([str(official),str(root/"candidate")],capture_output=True)
    assert rejected.returncode!=0,"official package loader accepted independent candidate"
    try:
        verify_package(root/"candidate",expected_package_id="0"*64)
    except ValueError:
        pass
    else:
        raise AssertionError("wrong external pin accepted")
    with (root/"candidate"/"weights.safetensors").open("ab") as stream:
        stream.write(b"x")
    try:
        verify_package(root/"candidate",expected_package_id=m["package_id"])
    except ValueError:
        pass
    else:
        raise AssertionError("tampered weights accepted")
    print(json.dumps({"actual_full_shape_training_steps":1,"fixture":"synthetic tokens",
        "canonical_tensors":256,"rust_roundtrip_bytes":count,"canonical_sha256":actual.hexdigest(),
        "weights_file_bytes":m["files"]["weights.safetensors"]["bytes"],
        "external_pin_rejected":True,"corruption_rejected":True,"official_loader_rejected":True,
        "rust_raw_reader_parity":True,"rust_model_inference":True,"release_ready":False}))
