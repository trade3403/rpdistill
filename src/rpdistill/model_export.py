"""Independent FP32 candidate package; never an official RPModel v1.

Only completed local training checkpoints are accepted. A candidate package is
diagnostic, not a release, signature, or authorization to distribute weights.
"""
from dataclasses import asdict
import hashlib
import json
from pathlib import Path
import re
import shutil
import tempfile

from .datasets import encoded
from .evaluation import hash_json,checked_text
from .student import (FIXED,ASSETS,ALIASES,BASE_SOURCE,BASE_REVISION,checked_assets,
                      canonical_state,contract,expected_shapes,no_duplicate_keys)
from .student_evaluation import load_evaluation_model
from .transfer import digest_file

SCHEMA="rpdistill-model-candidate-v1"
D_AUDIT="cce002dd2667e6fcd0ec4c86c9b41a3da144b26e"
MAX_MANIFEST=65536
MAX_WEIGHT_HEADER=8*1024*1024+8
PAYLOAD=contract()["fp32_payload_bytes"]
REQUIRED_BYTES=PAYLOAD+MAX_WEIGHT_HEADER+sum(v[0] for v in ASSETS.values())+MAX_MANIFEST
FILES=set(ASSETS)|{"weights.safetensors"}


def valid_id(value):
    return isinstance(value,str) and re.fullmatch(r"[a-f0-9]{64}",value) is not None


def export_plan():
    return {"schema":SCHEMA,"profile":asdict(FIXED),"dtype":"F32",
            "canonical_tensors":256,"payload_bytes":PAYLOAD,
            "asset_bytes":sum(v[0] for v in ASSETS.values()),
            "conservative_required_bytes":REQUIRED_BYTES,"d_audit_revision":D_AUDIT,
            "official_rpmodel_v1":False,"rust_deployable":False,"release_ready":False}


def metadata(checkpoint_id):
    return {"format":"pt","rpdistill_format":"1","source_checkpoint_id":checkpoint_id}


def file_record(path):
    return {"bytes":path.stat().st_size,"sha256":digest_file(path)}


def export_candidate(checkpoint,assets,destination,*,dataset_version,license_label,
                     rights_note,max_bytes,acknowledge_candidate_only=False):
    from safetensors.torch import save_file
    if acknowledge_candidate_only is not True:
        raise ValueError("explicit candidate-only acknowledgment required")
    if not valid_id(dataset_version):
        raise ValueError("invalid dataset version")
    license_label=checked_text(license_label,"operator declared model license",128)
    rights_note=checked_text(rights_note,"operator rights note",2000)
    if type(max_bytes) is not int or not REQUIRED_BYTES<=max_bytes<=2**40:
        raise ValueError("export byte budget below conservative required size")
    dest=Path(destination)
    if dest.exists() or dest.is_symlink():
        raise ValueError("export destination already exists")
    dest=dest.resolve()
    asset_root=checked_assets(assets)
    if dest==asset_root or asset_root in dest.parents:
        raise ValueError("export must be separate from tokenizer assets")
    dest.parent.mkdir(parents=True,exist_ok=True)
    if shutil.disk_usage(dest.parent).free<REQUIRED_BYTES:
        raise ValueError("insufficient export disk space")
    model,source=load_evaluation_model(checkpoint,expected_dataset=dataset_version,profile=FIXED)
    state=canonical_state(model)
    checkpoint_id=source["checkpoint_id"]
    if not valid_id(checkpoint_id):
        raise ValueError("invalid source checkpoint identity")
    manifest={"schema":SCHEMA,"plan":export_plan(),"aliases":ALIASES,
              "origin":{"kind":"rpdistill_training_checkpoint","checkpoint_id":checkpoint_id,
                        "checkpoint_schema":source["schema"],"training_dataset":dataset_version,
                        "training_provenance_sha256":hash_json(source["provenance"])},
              "tokenizer_origin":{"source":BASE_SOURCE,"revision":BASE_REVISION,
                                  "license_label":"Apache-2.0","weights_from_tokenizer_source":False},
              "rights":{"operator_declared_model_license":license_label,"operator_note":rights_note,
                        "verified_by_software":False,"distribution_authorized":False},
              "quality_approved":False,"release_ready":False}
    stage=Path(tempfile.mkdtemp(prefix=".rpdistill-export-",dir=dest.parent))
    try:
        for name in ASSETS:
            shutil.copyfile(asset_root/name,stage/name)
        checked_assets(stage)
        save_file({k:v.detach().cpu().contiguous() for k,v in state.items()},
                  str(stage/"weights.safetensors"),metadata=metadata(checkpoint_id))
        manifest["files"]={n:file_record(stage/n) for n in sorted(FILES)}
        manifest["package_id"]=hash_json(manifest)
        raw=encoded(manifest).encode()
        if len(raw)>MAX_MANIFEST or len(raw)+sum(r["bytes"] for r in manifest["files"].values())>max_bytes:
            raise ValueError("export exceeded byte budget")
        (stage/"manifest.json").write_bytes(raw)
        verify_package(stage,expected_package_id=manifest["package_id"])
        if dest.exists() or dest.is_symlink():
            raise ValueError("export destination already exists")
        stage.rename(dest)
    finally:
        if stage.exists():
            shutil.rmtree(stage)
    return manifest|{"path":str(dest)}


def verify_package(root,*,expected_package_id):
    """Verify an independently pinned package ID and all canonical FP32 tensors.

    Assumes stable local directory with no concurrent writer. External pin is
    required; a self-hash alone is not authentication.
    """
    import torch
    from safetensors import safe_open
    root=Path(root)
    if not valid_id(expected_package_id) or root.is_symlink() or not root.is_dir():
        raise ValueError("invalid package root or expected package ID")
    if {p.name for p in root.iterdir()}!=FILES|{"manifest.json"}:
        raise ValueError("unexpected package inventory")
    if any(p.is_symlink() or not p.is_file() for p in root.iterdir()):
        raise ValueError("invalid package file")
    meta=root/"manifest.json"
    if meta.stat().st_size>MAX_MANIFEST:
        raise ValueError("package manifest exceeds budget")
    with meta.open("rb") as f:
        raw=f.read(MAX_MANIFEST+1)
    if len(raw)>MAX_MANIFEST:
        raise ValueError("package manifest exceeds budget")
    m=json.loads(raw.decode("utf-8"),object_pairs_hook=no_duplicate_keys)
    if (not isinstance(m,dict) or set(m)!={"schema","plan","aliases","origin","tokenizer_origin","rights",
                                            "quality_approved","release_ready","files","package_id"}
        or m["schema"]!=SCHEMA or m["package_id"]!=expected_package_id
        or hash_json({k:v for k,v in m.items() if k!="package_id"})!=expected_package_id
        or m["plan"]!=export_plan() or m["aliases"]!=ALIASES
        or m["quality_approved"] is not False or m["release_ready"] is not False):
        raise ValueError("candidate manifest identity mismatch")
    origin=m["origin"]
    if (set(origin)!={"kind","checkpoint_id","checkpoint_schema","training_dataset","training_provenance_sha256"}
        or origin["kind"]!="rpdistill_training_checkpoint"
        or origin["checkpoint_schema"] not in ("rpdistill-weights-v1","rpdistill-training-state-v1")
        or not all(valid_id(origin[k]) for k in ("checkpoint_id","training_dataset","training_provenance_sha256"))):
        raise ValueError("invalid source provenance")
    if m["tokenizer_origin"]!={"source":BASE_SOURCE,"revision":BASE_REVISION,
                               "license_label":"Apache-2.0","weights_from_tokenizer_source":False}:
        raise ValueError("invalid tokenizer provenance")
    rights=m["rights"]
    if (set(rights)!={"operator_declared_model_license","operator_note","verified_by_software","distribution_authorized"}
        or rights["verified_by_software"] is not False or rights["distribution_authorized"] is not False):
        raise ValueError("invalid candidate rights record")
    checked_text(rights["operator_declared_model_license"],"operator model license",128)
    checked_text(rights["operator_note"],"operator rights note",2000)
    if set(m["files"])!=FILES:
        raise ValueError("invalid package manifest inventory")
    checked_assets(root)
    for name,record in m["files"].items():
        path=root/name
        size=path.stat().st_size
        if name in ASSETS:
            if record!={"bytes":ASSETS[name][0],"sha256":ASSETS[name][1]}:
                raise ValueError("asset identity mismatch")
        elif not PAYLOAD<=size<=PAYLOAD+MAX_WEIGHT_HEADER:
            raise ValueError("invalid weights file size")
        if record!=file_record(path):
            raise ValueError("package file integrity mismatch: "+name)
    with safe_open(str(root/"weights.safetensors"),framework="pt",device="cpu") as f:
        shapes=expected_shapes()
        if set(f.keys())!=set(shapes) or f.metadata()!=metadata(origin["checkpoint_id"]):
            raise ValueError("unexpected candidate weight inventory or metadata")
        for name,shape in shapes.items():
            t=f.get_tensor(name)
            if tuple(t.shape)!=shape or t.dtype!=torch.float32 or not bool(torch.isfinite(t).all()):
                raise ValueError("invalid canonical tensor: "+name)
    return m
