"""Independent candidate integration review; never production release authorization.

Re-run quality on verified package weights, re-check training snapshot and
operator rights assertions, recompute human review, then execute trusted Rust
diagnostics. Local hashes are not signatures. D production remains separate.
"""
from dataclasses import asdict
import math
from pathlib import Path
import time

from .evaluation import checked_text, validate_benchmark, hash_json
from .model_export import verify_package, valid_id
from .quality_review import collect_review, ReviewGate, report_outputs
from .student_evaluation import load_evaluation_model, generate_one, GenerationConfig
from .student import FIXED, StudentCodec, canonical_state
from .distill import prepare_reviewed_snapshot
from .rust_parity import rust_parity, D_REFERENCE
from .resumable import SCHEMA as TRAINING_STATE_SCHEMA


SCHEMA="rpdistill-integration-review-v1"


def verify_source_weights(root,checkpoint,manifest):
    """Compare every actual canonical tensor, not just claimed checkpoint ID."""
    import torch
    from safetensors import safe_open
    model,source=load_evaluation_model(checkpoint,
        expected_dataset=manifest["origin"]["training_dataset"],profile=FIXED)
    origin=manifest["origin"]
    if (source["checkpoint_id"]!=origin["checkpoint_id"]
        or source["schema"]!=origin["checkpoint_schema"]
        or hash_json(source["provenance"])!=origin["training_provenance_sha256"]):
        raise ValueError("package source checkpoint binding mismatch")
    state=canonical_state(model,FIXED)
    with safe_open(str(Path(root)/"weights.safetensors"),framework="pt",device="cpu") as reader:
        if set(reader.keys())!=set(state):
            raise ValueError("package source tensor inventory mismatch")
        for name,tensor in state.items():
            if not torch.equal(tensor,reader.get_tensor(name)):
                raise ValueError("package source tensor differs: "+name)
    return model,source


def review_rights(db_path,root,source,manifest,*,reviewed_dataset,reviewed_teacher_license,
                  reviewed_model_license,rights_note,reviewer,training_limit):
    rights_note=checked_text(rights_note,"rights review note",2000)
    reviewer=checked_text(reviewer,"operator reviewer",128)
    reviewed_model_license=checked_text(reviewed_model_license,"reviewed model license",128)
    origin=manifest["origin"]
    if (reviewed_dataset!=origin["training_dataset"]
        or reviewed_model_license!=manifest["rights"]["operator_declared_model_license"]):
        raise ValueError("exact dataset and model license review required")
    # Re-run current train selection (rights, hashes, codec, registry license).
    # The selected ordered pair IDs must match the actual checkpoint provenance.
    examples,provenance=prepare_reviewed_snapshot(db_path,reviewed_dataset,root,
        reviewed_dataset=reviewed_dataset,reviewed_teacher_license=reviewed_teacher_license,
        limit=training_limit)
    if source["provenance"]!=provenance or not examples:
        raise ValueError("current training provenance differs from checkpoint")
    if source.get("schema")==TRAINING_STATE_SCHEMA and source.get("data_sha256")!=hash_json(examples):
        raise ValueError("current training token data differs from checkpoint")
    return {"reviewer":reviewer,"operator_note":rights_note,"dataset":reviewed_dataset,
            "teacher":provenance["teacher"],"teacher_license":reviewed_teacher_license,
            "model_license":reviewed_model_license,"training_selection":provenance["selected"],
            "training_pair_ids_sha256":provenance["training_pair_ids_sha256"],
            "operator_rights_asserted":True,"legal_rights_verified_by_software":False,
            "distribution_authorized":False}


def check_replay(model,codec,benchmark,student,*,deadline):
    """Replay actual generation and match all outputs and EOS/token counts."""
    config=GenerationConfig(**student["generation_config"])
    outputs=report_outputs(student,benchmark)
    generation=student.get("generation",[])
    if len(generation)!=len(outputs):
        raise ValueError("missing generation records")
    for case,output,record in zip(benchmark["cases"],outputs,generation):
        if time.monotonic()>=deadline:
            raise ValueError("integration review soft time budget exhausted")
        if record.get("id")!=case["id"] or record.get("finish_reason")!="eos":
            raise ValueError("original generation incomplete")
        actual=generate_one(model,codec,case["source"],config)
        if (actual["hypothesis"]!=output["hypothesis"] or actual["finish_reason"]!="eos"
            or actual["generated_tokens"]!=record.get("generated_tokens")):
            raise ValueError("actual model output differs from reviewed evaluation")
    if time.monotonic()>=deadline:
        raise ValueError("integration review soft time budget exhausted")
    return {"cases":len(outputs),"hypotheses_sha256":hash_json(outputs),
            "generation_config":asdict(config),"actual_output_replay":True}


def review_integration(db_path,root,checkpoint,benchmark,student,baseline,packet,key,reviews,
                       *,expected_package_id,reviewed_dataset,reviewed_teacher_license,
                       reviewed_model_license,rights_note,reviewer,executable,
                       acknowledge_local_candidate_only=False,training_limit=1000,
                       max_cases=1000,max_seconds=3600,parity_timeout=180):
    if acknowledge_local_candidate_only is not True:
        raise ValueError("explicit local candidate-only acknowledgment required")
    if not valid_id(expected_package_id):
        raise ValueError("independent package pin required")
    if type(max_cases) is not int or not 1<=max_cases<=10000:
        raise ValueError("invalid case budget")
    if type(training_limit) is not int or not 1<=training_limit<=10000:
        raise ValueError("invalid training selection limit")
    if type(max_seconds) not in (int,float) or not math.isfinite(max_seconds) or not 0<max_seconds<=86400:
        raise ValueError("invalid time budget")
    if type(parity_timeout) is not int or not 1<=parity_timeout<=900:
        raise ValueError("invalid parity timeout")
    start=time.monotonic()
    deadline=start+max_seconds
    benchmark=validate_benchmark(db_path,benchmark)
    if len(benchmark["cases"])>max_cases:
        raise ValueError("benchmark exceeds case budget; no partial approval")
    manifest=verify_package(root,expected_package_id=expected_package_id)
    origin=manifest["origin"]
    if (origin["training_dataset"]!=benchmark["training_dataset"] or
        origin["checkpoint_id"]!=student.get("checkpoint_id")):
        raise ValueError("evaluation/package binding mismatch")
    # Default review and automatic gates cannot be weakened by a caller.
    human=collect_review(db_path,benchmark,student,baseline,packet,key,reviews,gate=ReviewGate())
    if not human["candidate_gate_passed"]:
        raise ValueError("quality review gate rejected: "+",".join(human["failures"]))
    if time.monotonic()>=deadline:
        raise ValueError("integration review soft time budget exhausted")
    model,source=verify_source_weights(root,checkpoint,manifest)
    rights=review_rights(db_path,root,source,manifest,reviewed_dataset=reviewed_dataset,
        reviewed_teacher_license=reviewed_teacher_license,reviewed_model_license=reviewed_model_license,
        rights_note=rights_note,reviewer=reviewer,training_limit=training_limit)
    replay=check_replay(model,StudentCodec.from_assets(root),benchmark,student,deadline=deadline)
    del model
    remaining=math.floor(deadline-time.monotonic())
    if remaining<1:
        raise ValueError("integration review soft time budget exhausted")
    parity=rust_parity(root,expected_package_id=expected_package_id,executable=executable,
                       timeout_seconds=min(parity_timeout,remaining))
    if (parity["package_id"]!=expected_package_id
        or parity["weights_sha256"]!=manifest["files"]["weights.safetensors"]["sha256"]
        or parity["d_reference"]!=D_REFERENCE or parity["diagnostic_passed"] is not True
        or time.monotonic()>=deadline):
        raise ValueError("Rust diagnostics or review time budget rejected")
    # Do not publish a receipt if the candidate or local rights record changed
    # while generation/diagnostics were running. Stable local files are assumed.
    if verify_package(root,expected_package_id=expected_package_id)!=manifest:
        raise ValueError("candidate changed during review")
    current_rights=review_rights(db_path,root,source,manifest,reviewed_dataset=reviewed_dataset,
        reviewed_teacher_license=reviewed_teacher_license,reviewed_model_license=reviewed_model_license,
        rights_note=rights_note,reviewer=reviewer,training_limit=training_limit)
    if current_rights!=rights or time.monotonic()>=deadline:
        raise ValueError("rights changed or review time budget exhausted")
    receipt={"schema":SCHEMA,"package_id":expected_package_id,
        "weights_sha256":manifest["files"]["weights.safetensors"]["sha256"],
        "checkpoint_id":origin["checkpoint_id"],"training_dataset":origin["training_dataset"],
        "benchmark_id":benchmark["benchmark_id"],"student_report":student["report_id"],
        "baseline_report":baseline["report_id"],"quality_review":human,
        "rights_review":rights,"output_replay":replay,"rust_diagnostics":parity,
        "candidate_integration_gate_passed":True,"production_loader_verified":False,
        "reviewer_identity_verified":False,"baseline_identity_verified":False,
        "distribution_authorized":False,"release_ready":False,
        "elapsed_seconds":time.monotonic()-start,
        "scope":"local diagnostic integration candidate, not production approval or signature"}
    return receipt|{"receipt_id":hash_json(receipt)}


def check_integration_receipt(root,receipt,*,expected_package_id,expected_receipt_id):
    """Validate a prior local receipt with two independently obtained pins.

    Integrity only: no new review of rights, quality or production loader.
    """
    if not valid_id(expected_package_id) or not valid_id(expected_receipt_id):
        raise ValueError("independent package and receipt pins required")
    if (not isinstance(receipt,dict) or receipt.get("schema")!=SCHEMA
        or receipt.get("receipt_id")!=expected_receipt_id
        or hash_json({k:v for k,v in receipt.items() if k!="receipt_id"})!=expected_receipt_id
        or receipt.get("package_id")!=expected_package_id
        or receipt.get("candidate_integration_gate_passed") is not True
        or any(receipt.get(k) is not False for k in ("production_loader_verified",
             "reviewer_identity_verified","baseline_identity_verified","distribution_authorized","release_ready"))):
        raise ValueError("invalid integration receipt identity")
    manifest=verify_package(root,expected_package_id=expected_package_id)
    origin=manifest["origin"]
    if (receipt.get("weights_sha256")!=manifest["files"]["weights.safetensors"]["sha256"]
        or receipt.get("checkpoint_id")!=origin["checkpoint_id"]
        or receipt.get("training_dataset")!=origin["training_dataset"]
        or not all(valid_id(receipt.get(k)) for k in ("benchmark_id","student_report","baseline_report"))):
        raise ValueError("receipt/package binding mismatch")
    quality=receipt.get("quality_review",{})
    if (quality.get("schema")!="rpdistill-quality-review-v1"
        or not valid_id(quality.get("review_id"))
        or hash_json({k:v for k,v in quality.items() if k!="review_id"})!=quality["review_id"]
        or quality.get("candidate_gate_passed") is not True or quality.get("failures")!=[]
        or quality.get("release_ready") is not False or quality.get("review_gate")!=asdict(ReviewGate())
        or any(quality.get(k)!=receipt[k] for k in ("benchmark_id","training_dataset","checkpoint_id","student_report","baseline_report"))):
        raise ValueError("invalid nested quality evidence")
    rights=receipt.get("rights_review",{})
    replay=receipt.get("output_replay",{})
    parity=receipt.get("rust_diagnostics",{})
    if (rights.get("dataset")!=origin["training_dataset"]
        or rights.get("model_license")!=manifest["rights"]["operator_declared_model_license"]
        or rights.get("operator_rights_asserted") is not True
        or rights.get("legal_rights_verified_by_software") is not False
        or rights.get("distribution_authorized") is not False
        or replay.get("actual_output_replay") is not True
        or replay.get("cases")!=quality.get("case_count")
        or not valid_id(replay.get("hypotheses_sha256"))
        or parity.get("schema")!="rpdistill-rust-parity-v1"
        or not valid_id(parity.get("report_id"))
        or hash_json({k:v for k,v in parity.items() if k!="report_id"})!=parity["report_id"]
        or parity.get("diagnostic_passed") is not True
        or parity.get("package_id")!=expected_package_id
        or parity.get("weights_sha256")!=receipt["weights_sha256"]
        or parity.get("d_reference")!=D_REFERENCE
        or parity.get("production_loader_verified") is not False
        or parity.get("release_ready") is not False):
        raise ValueError("invalid nested rights, replay or Rust evidence")
    return {"package_id":expected_package_id,"receipt_id":expected_receipt_id,
            "handoff_integrity_verified":True,"current_rights_revalidated":False,
            "production_loader_verified":False,"distribution_authorized":False,"release_ready":False}
