"""Command-line access to persistent experiment records and device discovery."""
import argparse
import json
from pathlib import Path
import platform
import sys

from . import __version__
from .config import TrainingConfig
from .devices import device_report
from .tasks import TaskStore
from .teachers import TeacherRegistry, search_teachers, download_teacher
from dataclasses import asdict
from .downloads import DownloadQueue
from .modelscope_source import search_models, revisions, download_modelscope
from .inference import TranslationOptions, load_teacher
from .papers import PaperQuery, PaperCatalog
from .ncbi_papers import discover_with_source
from .fulltext import FulltextLibrary
from .corpus import CorpusStore
from .datasets import DatasetStore, DatasetGate
from .pipeline import CorpusPipeline
from .student import contract as student_contract, checked_assets
from .training_data import acquire_assets, batch_plan
from .distill import DistillConfig, train_reviewed_snapshot
from .resumable import ResumeConfig, train_reviewed_segment
from .training_queue import TrainingQueue
from .evaluation import freeze_benchmark, evaluate, read_json, read_jsonl, write_new, QualityGate
from .student_evaluation import GenerationConfig, evaluate_checkpoint
from .quality_review import leakage_audit, create_blind_review, collect_review, ReviewGate
from .compression import plan as compression_plan, create_candidate
from .compression_review import RegressionGate, compare_candidates
from .model_export import export_plan, export_candidate, verify_package


def runtime_info() -> dict[str, str]:
    return {
        "application": "RPDistill",
        "version": __version__,
        "python": platform.python_version(),
        "platform": platform.system(),
        "architecture": platform.machine(),
        "stage": "E9a",
    }


def parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="rpdistill")
    p.add_argument("--db", default=str(Path.home() / ".rpdistill" / "tasks.sqlite3"))
    commands = p.add_subparsers(dest="command")
    commands.add_parser("info")
    dev = commands.add_parser("devices")
    dev.add_argument("--path", default=".")
    create = commands.add_parser("create")
    create.add_argument("--teacher", required=True)
    create.add_argument("--student", required=True)
    create.add_argument("--batch-size", type=int, default=8)
    create.add_argument("--epochs", type=int, default=1)
    create.add_argument("--learning-rate", type=float, default=1e-4)
    create.add_argument("--seed", type=int, default=42)
    commands.add_parser("list")
    for name in ("show", "events"):
        cmd = commands.add_parser(name)
        cmd.add_argument("id")
    search = commands.add_parser("model-search")
    search.add_argument("query")
    search.add_argument("--limit", type=int, default=20)
    listing = commands.add_parser("model-list")
    listing.add_argument("--source", choices=["huggingface", "modelscope"], default="huggingface")
    search.add_argument("--source", choices=["huggingface", "modelscope"], default="huggingface")
    rev = commands.add_parser("model-revisions")
    rev.add_argument("model_id")
    fetch = commands.add_parser("model-download")
    fetch.add_argument("model_id")
    fetch.add_argument("--source", choices=["huggingface", "modelscope"], default="huggingface")
    fetch.add_argument("--revision", required=True)
    fetch.add_argument("--reviewed-license", required=True,
                       help="License identifier after reviewing intended-use rights")
    fetch.add_argument("--max-bytes", type=int, required=True)
    fetch.add_argument("--cache-dir", default=str(Path.home() / ".rpdistill" / "hub"))
    enqueue = commands.add_parser("download-enqueue")
    enqueue.add_argument("model_id")
    enqueue.add_argument("--source", choices=["huggingface", "modelscope"], default="huggingface")
    enqueue.add_argument("--revision", required=True)
    enqueue.add_argument("--reviewed-license", required=True)
    enqueue.add_argument("--max-bytes", type=int, required=True)
    enqueue.add_argument("--cache-dir", default=str(Path.home() / ".rpdistill" / "hub"))
    commands.add_parser("download-list")
    commands.add_parser("download-run")
    for action in ("show", "pause", "resume", "cancel", "recover"):
        cmd = commands.add_parser("download-" + action)
        cmd.add_argument("id")
        if action == "recover":
            cmd.add_argument("--worker-stopped", action="store_true")
    translate = commands.add_parser("teacher-translate")
    translate.add_argument("model_id")
    translate.add_argument("--revision", required=True)
    translate.add_argument("--source", choices=["huggingface", "modelscope"], default="huggingface")
    translate.add_argument("--source-language", default="English")
    translate.add_argument("--target-language", default="Chinese")
    translate.add_argument("--device", default="cpu")
    translate.add_argument("--dtype", default="float32")
    translate.add_argument("--max-input-tokens", type=int, default=2048)
    translate.add_argument("--max-new-tokens", type=int, default=1024)
    translate.add_argument("--batch-size", type=int, default=1)
    translate.add_argument("--input", required=True, help="UTF-8 JSON array of source strings")
    papers = commands.add_parser("paper-search")
    papers.add_argument("--keyword", action="append", required=True)
    papers.add_argument("--subject")
    papers.add_argument("--start-date", required=True)
    papers.add_argument("--end-date", required=True)
    papers.add_argument("--language", default="eng")
    papers.add_argument("--limit", type=int, default=100)
    papers.add_argument("--include-closed", action="store_true")
    papers.add_argument("--provider", choices=["auto", "europe-pmc", "ncbi-pmc"], default="ncbi-pmc")
    listing = commands.add_parser("paper-list")
    listing.add_argument("--limit", type=int, default=100)
    download = commands.add_parser("paper-download")
    download.add_argument("--root", default=str(Path.home()/".rpdistill"/"papers"))
    download.add_argument("--max-bytes", type=int, required=True)
    download.add_argument("--limit", type=int, default=20)
    texts = commands.add_parser("paper-fulltexts")
    texts.add_argument("--root", default=str(Path.home()/".rpdistill"/"papers"))
    parse = commands.add_parser("corpus-parse")
    parse.add_argument("--root", default=str(Path.home()/".rpdistill"/"papers"))
    parse.add_argument("--limit", type=int, default=20)
    parse.add_argument("--max-chars", type=int, default=1200)
    segments = commands.add_parser("corpus-list")
    segments.add_argument("--limit", type=int, default=100)
    gen = commands.add_parser("corpus-translate")
    gen.add_argument("model_id")
    gen.add_argument("--revision", required=True)
    gen.add_argument("--source", choices=["huggingface","modelscope"], default="huggingface")
    gen.add_argument("--device", default="cpu")
    gen.add_argument("--dtype", default="float32")
    gen.add_argument("--batch-size", type=int, default=1)
    gen.add_argument("--max-input-tokens", type=int, default=2048)
    gen.add_argument("--max-new-tokens", type=int, default=1024)
    gen.add_argument("--limit", type=int, default=100)
    export = commands.add_parser("corpus-export")
    export.add_argument("--output", required=True)
    export.add_argument("--limit", type=int, default=10000)
    dataset = commands.add_parser("dataset-create")
    pipeline = commands.add_parser("pipeline-create")
    for cmd in (dataset,pipeline):
        cmd.add_argument("model_id")
        cmd.add_argument("--revision",required=True)
        cmd.add_argument("--source",choices=["huggingface","modelscope"],default="huggingface")
        cmd.add_argument("--device",default="cpu")
        cmd.add_argument("--dtype",default="float32")
        cmd.add_argument("--batch-size",type=int,default=1)
        cmd.add_argument("--max-input-tokens",type=int,default=2048)
        cmd.add_argument("--max-new-tokens",type=int,default=1024)
        cmd.add_argument("--min-train",type=int,default=10)
        cmd.add_argument("--min-validation",type=int,default=1)
        cmd.add_argument("--min-test",type=int,default=1)
        cmd.add_argument("--max-pairs",type=int,default=10000)
    pipeline.add_argument("--keyword",action="append",required=True)
    pipeline.add_argument("--subject")
    pipeline.add_argument("--start-date",required=True)
    pipeline.add_argument("--end-date",required=True)
    pipeline.add_argument("--search-limit",type=int,default=100)
    pipeline.add_argument("--paper-limit",type=int,default=20)
    pipeline.add_argument("--segment-limit",type=int,default=1000)
    pipeline.add_argument("--max-bytes",type=int,required=True)
    pipeline.add_argument("--root",default=str(Path.home()/".rpdistill"/"papers"))
    commands.add_parser("dataset-list")
    ds_export = commands.add_parser("dataset-export")
    ds_export.add_argument("version")
    ds_export.add_argument("--output",required=True)
    for action in ("run","show","resume"):
        cmd = commands.add_parser("pipeline-"+action)
        cmd.add_argument("id")
        if action=="resume":
            cmd.add_argument("--worker-stopped",action="store_true")
    student = commands.add_parser("student-info")
    student.add_argument("--assets",help="Verify pinned local configuration and tokenizer assets")
    asset = commands.add_parser("student-assets")
    asset.add_argument("--root",required=True)
    asset.add_argument("--max-bytes",type=int,required=True)
    batch = commands.add_parser("student-batch-plan")
    batch.add_argument("version")
    batch.add_argument("--assets",required=True)
    batch.add_argument("--split",choices=["train","validation","test"],default="train")
    batch.add_argument("--limit",type=int,default=1000)
    batch.add_argument("--batch-size",type=int,default=4)
    batch.add_argument("--max-padded-tokens",type=int,default=4096)
    batch.add_argument("--max-logits",type=int,default=16777216)
    train = commands.add_parser("student-distill")
    train.add_argument("version")
    train.add_argument("--assets",required=True)
    train.add_argument("--output",required=True)
    train.add_argument("--reviewed-dataset",required=True,
        help="Exact dataset version after operator review of content rights and translation quality")
    train.add_argument("--reviewed-teacher-license",required=True,
        help="Registered teacher license after reviewing intended distillation rights")
    train.add_argument("--steps",type=int,default=20)
    train.add_argument("--batch-size",type=int,default=1)
    train.add_argument("--learning-rate",type=float,default=1e-4)
    train.add_argument("--weight-decay",type=float,default=0.01)
    train.add_argument("--max-grad-norm",type=float,default=1.0)
    train.add_argument("--seed",type=int,default=42)
    train.add_argument("--max-padded-tokens",type=int,default=4096)
    train.add_argument("--max-logits",type=int,default=16777216)
    train.add_argument("--limit",type=int,default=1000)
    resume_train = commands.add_parser("student-train-resumable")
    resume_train.add_argument("version")
    resume_train.add_argument("--assets",required=True)
    resume_train.add_argument("--output",required=True)
    resume_train.add_argument("--reviewed-dataset",required=True,
        help="Exact dataset version after operator review of content rights and translation quality")
    resume_train.add_argument("--reviewed-teacher-license",required=True,
        help="Registered teacher license after reviewing intended distillation rights")
    resume_train.add_argument("--steps",type=int,default=20)
    resume_train.add_argument("--batch-size",type=int,default=1)
    resume_train.add_argument("--learning-rate",type=float,default=1e-4)
    resume_train.add_argument("--weight-decay",type=float,default=0.01)
    resume_train.add_argument("--max-grad-norm",type=float,default=1.0)
    resume_train.add_argument("--seed",type=int,default=42)
    resume_train.add_argument("--max-padded-tokens",type=int,default=4096)
    resume_train.add_argument("--max-logits",type=int,default=16777216)
    resume_train.add_argument("--limit",type=int,default=1000)
    resume_train.add_argument("--accumulation",type=int,default=1)
    resume_train.add_argument("--device",default="cpu",help="cpu or explicit cuda:N")
    resume_train.add_argument("--precision",choices=["float32","float16","bfloat16"],default="float32")
    resume_train.add_argument("--cuda-budget-bytes",type=int,default=0)
    resume_train.add_argument("--resume",help="Previous paused full-state checkpoint directory")
    resume_train.add_argument("--run-steps",type=int,default=100)
    resume_train.add_argument("--max-seconds",type=float,default=3600)
    resume_train.add_argument("--max-checkpoint-bytes",type=int,default=1073741824)
    queue_train = commands.add_parser("training-enqueue")
    queue_train.add_argument("version")
    queue_train.add_argument("--assets",required=True)
    queue_train.add_argument("--root",required=True)
    queue_train.add_argument("--reviewed-dataset",required=True,
        help="Exact dataset version after operator review of content rights and translation quality")
    queue_train.add_argument("--reviewed-teacher-license",required=True,
        help="Registered teacher license after reviewing intended distillation rights")
    queue_train.add_argument("--steps",type=int,default=20)
    queue_train.add_argument("--batch-size",type=int,default=1)
    queue_train.add_argument("--learning-rate",type=float,default=1e-4)
    queue_train.add_argument("--weight-decay",type=float,default=0.01)
    queue_train.add_argument("--max-grad-norm",type=float,default=1.0)
    queue_train.add_argument("--seed",type=int,default=42)
    queue_train.add_argument("--max-padded-tokens",type=int,default=4096)
    queue_train.add_argument("--max-logits",type=int,default=16777216)
    queue_train.add_argument("--limit",type=int,default=1000)
    queue_train.add_argument("--accumulation",type=int,default=1)
    queue_train.add_argument("--device",default="cpu",help="cpu or explicit cuda:N")
    queue_train.add_argument("--precision",choices=["float32","float16","bfloat16"],default="float32")
    queue_train.add_argument("--cuda-budget-bytes",type=int,default=0)
    queue_train.add_argument("--segment-steps",type=int,default=20)
    queue_train.add_argument("--segment-seconds",type=int,default=300)
    queue_train.add_argument("--max-checkpoint-bytes",type=int,default=1073741824)
    queue_train.add_argument("--total-seconds",type=int,required=True)
    queue_train.add_argument("--total-checkpoint-bytes",type=int,required=True)
    qrun=commands.add_parser("training-run")
    qrun.add_argument("--max-segments",type=int,default=1000)
    qlist=commands.add_parser("training-list")
    qlist.add_argument("--limit",type=int,default=100)
    for action in ("show","events","pause","resume","cancel","recover"):
        cmd=commands.add_parser("training-"+action)
        cmd.add_argument("id")
        if action=="recover":
            cmd.add_argument("--worker-stopped",action="store_true")
        if action=="events":
            cmd.add_argument("--limit",type=int,default=100)
    bench=commands.add_parser("benchmark-freeze")
    bench.add_argument("version")
    bench.add_argument("--input",required=True,help="Reviewed human-reference JSONL")
    bench.add_argument("--review-note",required=True)
    bench.add_argument("--output",required=True)
    ev=commands.add_parser("benchmark-score")
    ev.add_argument("--benchmark",required=True)
    ev.add_argument("--hypotheses",required=True,help="JSONL id and hypothesis")
    ev.add_argument("--label",default="external hypotheses")
    ev.add_argument("--gate",help="Optional JSON object overriding default QualityGate")
    ev.add_argument("--output",required=True)
    student_ev=commands.add_parser("benchmark-student")
    student_ev.add_argument("--benchmark",required=True)
    student_ev.add_argument("--checkpoint",required=True)
    student_ev.add_argument("--assets",required=True)
    student_ev.add_argument("--baseline",help="Optional external hypothesis JSONL for same benchmark")
    student_ev.add_argument("--gate",help="Optional JSON object overriding default QualityGate")
    student_ev.add_argument("--max-new-tokens",type=int,default=128)
    student_ev.add_argument("--max-logits",type=int,default=16777216)
    student_ev.add_argument("--output",required=True)
    audit=commands.add_parser("benchmark-leakage-audit")
    audit.add_argument("--benchmark",required=True)
    audit.add_argument("--output",required=True)
    blind=commands.add_parser("benchmark-blind")
    blind.add_argument("--benchmark",required=True)
    blind.add_argument("--student-report",required=True)
    blind.add_argument("--baseline-report",required=True)
    blind.add_argument("--packet",required=True)
    blind.add_argument("--key",required=True,help="Private mapping, keep away from reviewers")
    review=commands.add_parser("benchmark-review")
    review.add_argument("--benchmark",required=True)
    review.add_argument("--student-report",required=True)
    review.add_argument("--baseline-report",required=True)
    review.add_argument("--packet",required=True)
    review.add_argument("--key",required=True)
    review.add_argument("--reviews",required=True,help="JSON list of independent reviewer records")
    review.add_argument("--gate",help="Optional JSON ReviewGate; engineering thresholds, not release approval")
    review.add_argument("--output",required=True)
    compress_plan=commands.add_parser("student-compression-plan")
    compress_plan.add_argument("--mode",choices=["fp32","fp16","int8"],required=True)
    compress=commands.add_parser("student-compress")
    compress.add_argument("version")
    compress.add_argument("--checkpoint",required=True)
    compress.add_argument("--mode",choices=["fp32","fp16","int8"],required=True)
    compress.add_argument("--output",required=True)
    compress.add_argument("--max-bytes",type=int,required=True)
    compare=commands.add_parser("benchmark-compression")
    compare.add_argument("--benchmark",required=True)
    compare.add_argument("--checkpoint",required=True)
    compare.add_argument("--assets",required=True)
    compare.add_argument("--candidate",action="append",required=True)
    compare.add_argument("--gate",help="Optional JSON RegressionGate")
    compare.add_argument("--max-new-tokens",type=int,default=128)
    compare.add_argument("--max-logits",type=int,default=16777216)
    compare.add_argument("--max-cases",type=int,default=1000)
    compare.add_argument("--max-seconds",type=float,default=3600)
    compare.add_argument("--output",required=True)
    commands.add_parser("student-export-plan")
    export=commands.add_parser("student-export-candidate")
    export.add_argument("version")
    export.add_argument("--checkpoint",required=True)
    export.add_argument("--assets",required=True)
    export.add_argument("--output",required=True)
    export.add_argument("--license-label",required=True)
    export.add_argument("--rights-note",required=True)
    export.add_argument("--max-bytes",type=int,required=True)
    export.add_argument("--acknowledge-candidate-only",action="store_true")
    verify_export=commands.add_parser("student-verify-package")
    verify_export.add_argument("--root",required=True)
    verify_export.add_argument("--expected-package-id",required=True)
    # State transitions are internal API only until a real worker exists.
    return p


def main(argv=None) -> int:
    args = parser().parse_args(argv)
    try:
        if args.command in (None, "info"):
            result = runtime_info()
        elif args.command == "benchmark-freeze":
            result=freeze_benchmark(args.db,args.version,read_jsonl(args.input),review_note=args.review_note)
            path=write_new(args.output,result)
            result={"benchmark_id":result["benchmark_id"],"cases":len(result["cases"]),"path":path}
        elif args.command == "student-export-plan":
            result=export_plan()
        elif args.command == "student-export-candidate":
            result=export_candidate(args.checkpoint,args.assets,args.output,dataset_version=args.version,
                license_label=args.license_label,rights_note=args.rights_note,max_bytes=args.max_bytes,
                acknowledge_candidate_only=args.acknowledge_candidate_only)
        elif args.command == "student-verify-package":
            result=verify_package(args.root,expected_package_id=args.expected_package_id)
        elif args.command == "benchmark-compression":
            if Path(args.output).exists() or Path(args.output).is_symlink():
                raise ValueError("output must be a new file")
            result=compare_candidates(args.db,read_json(args.benchmark),args.checkpoint,args.assets,args.candidate,
                config=GenerationConfig(args.max_new_tokens,args.max_logits),
                gate=RegressionGate(**read_json(args.gate)) if args.gate else RegressionGate(),
                max_cases=args.max_cases,max_seconds=args.max_seconds)
            path=write_new(args.output,result)
            result={k:v for k,v in result.items() if k not in ("source","candidates","lexical_audit")}|{
                "path":path,"candidates":[{k:v for k,v in row.items() if k!="score"} for row in result["candidates"]]}
        elif args.command == "student-compression-plan":
            result=compression_plan(args.mode)
        elif args.command == "student-compress":
            result=create_candidate(args.checkpoint,args.output,dataset_version=args.version,
                mode=args.mode,max_bytes=args.max_bytes)
            result={k:v for k,v in result.items() if k not in ("layout","tensor_errors")}
        elif args.command == "benchmark-leakage-audit":
            result=leakage_audit(args.db,read_json(args.benchmark))
            path=write_new(args.output,result)
            result={k:v for k,v in result.items() if k!="matches"}|{"path":path,"match_count":len(result["matches"])}
        elif args.command == "benchmark-blind":
            if Path(args.packet).resolve()==Path(args.key).resolve() or any(
                    Path(p).exists() or Path(p).is_symlink() for p in (args.packet,args.key)):
                raise ValueError("packet and private key require two distinct new files")
            packet,key=create_blind_review(args.db,read_json(args.benchmark),
                read_json(args.student_report),read_json(args.baseline_report))
            private_path=write_new(args.key,key)
            packet_path=write_new(args.packet,packet)
            result={"packet_id":packet["packet_id"],"cases":len(packet["cases"]),
                    "packet_path":packet_path,"private_key_path":private_path}
        elif args.command == "benchmark-review":
            result=collect_review(args.db,read_json(args.benchmark),read_json(args.student_report),
                read_json(args.baseline_report),read_json(args.packet),read_json(args.key),
                read_json(args.reviews),gate=ReviewGate(**read_json(args.gate)) if args.gate else ReviewGate())
            path=write_new(args.output,result)
            result={k:v for k,v in result.items() if k!="lexical_audit"}|{"path":path}
        elif args.command == "benchmark-student":
            if Path(args.output).exists() or Path(args.output).is_symlink():
                raise ValueError("output must be a new file")
            gate=QualityGate(**read_json(args.gate)) if args.gate else QualityGate()
            result=evaluate_checkpoint(args.db,read_json(args.benchmark),args.checkpoint,args.assets,
                config=GenerationConfig(args.max_new_tokens,args.max_logits),gate=gate,
                baseline=read_jsonl(args.baseline) if args.baseline else None)
            path=write_new(args.output,result)
            result={k:v for k,v in result.items() if k not in ("details","generation")}|{"path":path}
        elif args.command == "benchmark-score":
            gate=QualityGate(**read_json(args.gate)) if args.gate else QualityGate()
            result=evaluate(args.db,read_json(args.benchmark),read_jsonl(args.hypotheses),gate=gate,label=args.label)
            path=write_new(args.output,result)
            result={k:v for k,v in result.items() if k!="details"}|{"path":path}
        elif args.command == "training-enqueue":
            config=ResumeConfig(DistillConfig(steps=args.steps,batch_size=args.batch_size,
                learning_rate=args.learning_rate,weight_decay=args.weight_decay,
                max_grad_norm=args.max_grad_norm,seed=args.seed,
                max_padded_tokens=args.max_padded_tokens,max_logits=args.max_logits),
                accumulation=args.accumulation,device=args.device,precision=args.precision,
                cuda_budget_bytes=args.cuda_budget_bytes)
            result=TrainingQueue(args.db).enqueue(args.version,args.assets,args.root,
                reviewed_dataset=args.reviewed_dataset,reviewed_teacher_license=args.reviewed_teacher_license,
                config=config,limit=args.limit,segment_steps=args.segment_steps,
                segment_seconds=args.segment_seconds,total_seconds=args.total_seconds,
                max_checkpoint_bytes=args.max_checkpoint_bytes,total_checkpoint_bytes=args.total_checkpoint_bytes)
        elif args.command.startswith("training-"):
            queue=TrainingQueue(args.db)
            action=args.command.removeprefix("training-")
            if action=="run":
                result=queue.run_next(max_segments=args.max_segments)
            elif action=="list":
                result=queue.list(args.limit)
            elif action=="show":
                result=queue.get(args.id)
            elif action=="events":
                result=queue.events(args.id,args.limit)
            elif action=="recover":
                result=queue.recover(args.id,worker_stopped=args.worker_stopped)
            else:
                result=queue.control(args.id,action)
        elif args.command == "student-train-resumable":
            config=ResumeConfig(DistillConfig(steps=args.steps,batch_size=args.batch_size,
                learning_rate=args.learning_rate,weight_decay=args.weight_decay,
                max_grad_norm=args.max_grad_norm,seed=args.seed,
                max_padded_tokens=args.max_padded_tokens,max_logits=args.max_logits),
                accumulation=args.accumulation,device=args.device,precision=args.precision,
                cuda_budget_bytes=args.cuda_budget_bytes)
            result=train_reviewed_segment(args.db,args.version,args.assets,args.output,
                reviewed_dataset=args.reviewed_dataset,reviewed_teacher_license=args.reviewed_teacher_license,
                config=config,limit=args.limit,resume=args.resume,run_steps=args.run_steps,
                max_seconds=args.max_seconds,max_checkpoint_bytes=args.max_checkpoint_bytes)
        elif args.command == "student-distill":
            config=DistillConfig(steps=args.steps,batch_size=args.batch_size,learning_rate=args.learning_rate,
                weight_decay=args.weight_decay,max_grad_norm=args.max_grad_norm,seed=args.seed,
                max_padded_tokens=args.max_padded_tokens,max_logits=args.max_logits)
            result=train_reviewed_snapshot(args.db,args.version,args.assets,args.output,
                reviewed_dataset=args.reviewed_dataset,reviewed_teacher_license=args.reviewed_teacher_license,
                config=config,limit=args.limit)
        elif args.command == "student-assets":
            result=acquire_assets(args.root,max_bytes=args.max_bytes)
        elif args.command == "student-batch-plan":
            result=batch_plan(args.db,args.version,args.assets,split=args.split,limit=args.limit,
                batch_size=args.batch_size,max_padded_tokens=args.max_padded_tokens,max_logits=args.max_logits)
        elif args.command == "student-info":
            result=student_contract()
            if args.assets:
                result["verified_assets"]=str(checked_assets(args.assets))
        elif args.command == "devices":
            result = device_report(args.path)
        elif args.command == "paper-search":
            query = PaperQuery(tuple(args.keyword), args.start_date, args.end_date,
                               subject=args.subject, language=args.language or None,
                               limit=args.limit, open_access_only=not args.include_closed)
            result = discover_with_source(query, PaperCatalog(args.db), source=args.provider)
        elif args.command == "paper-download":
            result = FulltextLibrary(args.db, args.root).download(PaperCatalog(args.db).list(500),
                max_bytes=args.max_bytes, limit=args.limit)
        elif args.command == "paper-fulltexts":
            result = FulltextLibrary(args.db, args.root).list()
        elif args.command in ("dataset-create","pipeline-create"):
            options=TranslationOptions(device=args.device,dtype=args.dtype,batch_size=args.batch_size,
                max_input_tokens=args.max_input_tokens,max_new_tokens=args.max_new_tokens)
            gate=DatasetGate(args.min_train,args.min_validation,args.min_test,args.max_pairs)
            if args.command=="dataset-create":
                result=DatasetStore(args.db).create(args.model_id,args.revision,options,
                    source=args.source,gate=gate)
            else:
                query=PaperQuery(tuple(args.keyword),args.start_date,args.end_date,
                    subject=args.subject,limit=args.search_limit)
                result=CorpusPipeline(args.db).create(query,args.model_id,args.revision,options,
                    root=args.root,max_bytes=args.max_bytes,paper_limit=args.paper_limit,
                    segment_limit=args.segment_limit,gate=gate,source=args.source)
        elif args.command=="dataset-list":
            result=DatasetStore(args.db).list()
        elif args.command=="dataset-export":
            result=DatasetStore(args.db).export(args.version,args.output)
        elif args.command in ("pipeline-run","pipeline-show","pipeline-resume"):
            engine=CorpusPipeline(args.db)
            if args.command=="pipeline-run":
                result=engine.run(args.id)
            elif args.command=="pipeline-resume":
                result=engine.resume(args.id,worker_stopped=args.worker_stopped)
            else:
                result=engine.get(args.id)
        elif args.command == "corpus-parse":
            result = CorpusStore(args.db).parse(args.root,limit=args.limit,max_chars=args.max_chars)
        elif args.command == "corpus-list":
            result = CorpusStore(args.db).list_segments(args.limit)
        elif args.command == "corpus-translate":
            options = TranslationOptions(device=args.device,dtype=args.dtype,batch_size=args.batch_size,
                max_input_tokens=args.max_input_tokens,max_new_tokens=args.max_new_tokens)
            result = CorpusStore(args.db).translate(load_teacher(args.db,args.model_id,args.revision,
                options,source=args.source),limit=args.limit)
        elif args.command == "corpus-export":
            result = CorpusStore(args.db).export_candidates(args.output,limit=args.limit)
        elif args.command == "paper-list":
            result = PaperCatalog(args.db).list(args.limit)
        elif args.command == "teacher-translate":
            input_path = Path(args.input)
            if input_path.stat().st_size > 8 * 1024 * 1024:
                raise ValueError("input JSON exceeds 8 MiB; split input")
            texts = json.loads(input_path.read_text(encoding="utf-8"))
            if not isinstance(texts, list):
                raise ValueError("input JSON must be an array of strings")
            options = TranslationOptions(source_language=args.source_language,
                target_language=args.target_language, device=args.device, dtype=args.dtype,
                max_input_tokens=args.max_input_tokens, max_new_tokens=args.max_new_tokens,
                batch_size=args.batch_size)
            result = load_teacher(args.db, args.model_id, args.revision, options,
                                  source=args.source).translate(texts)
        elif args.command.startswith("download-"):
            queue = DownloadQueue(args.db)
            action = args.command.removeprefix("download-")
            if action == "enqueue":
                result = queue.enqueue(args.model_id, args.revision,
                    reviewed_license=args.reviewed_license, max_bytes=args.max_bytes,
                    cache_dir=args.cache_dir, source=args.source)
            elif action == "list":
                result = queue.list()
            elif action == "run":
                result = queue.run_next()
            elif action == "show":
                result = queue.get(args.id)
            elif action == "recover":
                result = queue.recover(args.id, worker_stopped=args.worker_stopped)
            else:
                result = queue.control(args.id, action)
        elif args.command == "model-search":
            result = (search_models(args.query, args.limit) if args.source == "modelscope"
                      else [asdict(x) for x in search_teachers(args.query, args.limit)])
        elif args.command == "model-revisions":
            result = revisions(args.model_id)
        elif args.command == "model-list":
            result = TeacherRegistry(args.db, source=args.source).list()
        elif args.command == "model-download":
            download = download_modelscope if args.source == "modelscope" else download_teacher
            result = download(
                args.model_id, args.revision, reviewed_license=args.reviewed_license,
                max_bytes=args.max_bytes, cache_dir=args.cache_dir,
                registry=TeacherRegistry(args.db, source=args.source))
        else:
            store = TaskStore(args.db)
            if args.command == "create":
                result = store.create(TrainingConfig(
                    teacher=args.teacher, student=args.student,
                    batch_size=args.batch_size, epochs=args.epochs,
                    learning_rate=args.learning_rate, seed=args.seed))
            elif args.command == "list":
                result = store.list()
            elif args.command == "show":
                result = store.get(args.id)
            else:
                result = store.events(args.id)
        print(json.dumps(result, ensure_ascii=True, allow_nan=False))
        return 0
    except (ValueError, KeyError, OSError, RuntimeError) as exc:
        print(str(exc), file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
