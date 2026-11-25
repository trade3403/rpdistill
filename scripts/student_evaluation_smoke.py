"""Actual tiny CPU student generation from two checkpoint formats, synthetic data only."""
import json
from contextlib import closing
from pathlib import Path
import tempfile
from unittest.mock import Mock
import torch

from rpdistill.datasets import DatasetStore,encoded,sha
from rpdistill.evaluation import freeze_benchmark,QualityGate,evaluate
from rpdistill.quality_review import leakage_audit,create_blind_review,collect_review,ReviewGate
from rpdistill.student import StudentProfile,StudentCodec,build_student
from rpdistill.distill import DistillConfig,train_sequence,save_checkpoint
from rpdistill.resumable import ResumeConfig,run_segment
from rpdistill.student_evaluation import GenerationConfig,evaluate_checkpoint,load_evaluation_model

torch.set_num_threads(1)
p=StudentProfile(vocab=8,hidden=16,heads=2,ffn=32,encoder_layers=1,decoder_layers=1,positions=16,pad=7)
vocab={"</s>":0,"<unk>":1,">>cmn_Hans<<":2,"▁test":3,"科研":4,"翻译":5,"。":6,"<pad>":7}
src=Mock();src.encode.return_value=["▁test"]
codec=StudentCodec(vocab,src,Mock(),p)
examples=[{"source_ids":[2,3,0],"target_ids":[4,5,6,0]}]
cfg=DistillConfig(steps=50,batch_size=1,learning_rate=0.01,seed=42)
with tempfile.TemporaryDirectory() as tmp:
    root=Path(tmp)
    store=DatasetStore(root/"db")
    row={"source_text":"Training-only synthetic sample.","source_sha256":sha(b"Training-only synthetic sample."),
         "split":"train","pmcid":"PMC999","attribution":{"doi":"10.1234/train"}}
    raw=encoded(row)
    manifest={"status":"candidate_snapshot","counts":{"train":1},"count":1,
              "payload_sha256":sha((raw+"\n").encode("ascii"))}
    version=sha(encoded(manifest).encode())
    manifest["version"]=version
    with closing(store.corpus.connect()) as db,db:
        db.execute("INSERT INTO dataset_versions VALUES (?,?)",(version,encoded(manifest)))
        db.execute("INSERT INTO dataset_members VALUES (?,?,?)",(version,0,raw))
    benchmark=freeze_benchmark(root/"db",version,[{"id":"a","paper_id":"fixture",
        "source":"Scientific translation.","reference":"科研翻译。","rights_note":"Synthetic fixture"}],
        review_note="Synthetic test of scoring integration, not independent quality")
    prov={"dataset_version":version,"split":"train","fixture":"synthetic"}
    model=build_student(p,seed=cfg.seed)
    history=train_sequence(model,examples,cfg,p)
    save_checkpoint(model,p,cfg,history,root/"weights",provenance=prov)
    run_segment(examples,root/"full",profile=p,config=ResumeConfig(cfg),provenance=prov)
    reports=[]
    for name in ("weights","full"):
        report=evaluate_checkpoint(root/"db",benchmark,root/name,None,profile=p,codec=codec,
             config=GenerationConfig(max_new_tokens=8),baseline=[{"id":"a","hypothesis":"科研翻译。"}])
        assert report["model_output_generated_locally"] and not report["release_ready"]
        assert len(report["generation"])==1 and report["performance"]["canonical_weight_bytes"]>0
        assert report["generation"][0]["finish_reason"]=="eos",report["generation"]
        assert report["details"][0]["hypothesis"]=="科研翻译。",report["details"]
        assert report["metrics"]["chrf"]>99 and "baseline" in report
        assert not report["automatic_gate_passed"] # insufficient coverage
        reports.append(report)
    assert reports[0]["performance"]["process_peak_rss_bytes"]>0
    baseline=evaluate(root/"db",benchmark,[{"id":"a","hypothesis":"科研翻译。"}],label="synthetic baseline")
    audit=leakage_audit(root/"db",benchmark)
    assert audit["passed"]
    packet,key=create_blind_review(root/"db",benchmark,reports[0],baseline)
    scores=[{"id":r["id"],"A":{"adequacy":4,"fluency":4,"critical_error":False},
             "B":{"adequacy":4,"fluency":4,"critical_error":False},"preference":"tie"} for r in packet["cases"]]
    reviews=[{"reviewer":name,"packet_id":packet["packet_id"],"independent_review_asserted":True,
              "scores":scores} for name in ("synthetic-reviewer-1","synthetic-reviewer-2")]
    reviewed=collect_review(root/"db",benchmark,reports[0],baseline,packet,key,reviews,gate=ReviewGate(min_cases=1))
    assert reviewed["reviewer_count"]==2 and not reviewed["candidate_gate_passed"]
    assert "automatic_quality" in reviewed["failures"] and not reviewed["release_ready"]
    print(json.dumps({"lexical_audit_pass":True,"blind_review_roundtrip":True,
        "synthetic_reviewer_count":2,"insufficient_automatic_coverage_rejected":True,
        "process_peak_rss_bytes":reports[0]["performance"]["process_peak_rss_bytes"],
        "real_human_review":False}))
    try:
        load_evaluation_model(root/"full",profile=p,expected_dataset="0"*64)
    except ValueError:
        pass
    else:
        raise AssertionError("wrong dataset accepted")
    with (root/"full"/"training.safetensors").open("ab") as out:
        out.write(b"x")
    try:
        load_evaluation_model(root/"full",profile=p,expected_dataset=version)
    except ValueError:
        pass
    else:
        raise AssertionError("tampered checkpoint accepted")
    print(json.dumps({"checkpoint_formats":2,"actual_generation":True,"eos":True,
        "synthetic_chrf":[r["metrics"]["chrf"] for r in reports],"wrong_dataset_rejected":True,
        "corrupt_checkpoint_rejected":True,"insufficient_coverage_rejected":True,
        "model_quality_test":False}))
