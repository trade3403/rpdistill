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


def runtime_info() -> dict[str, str]:
    return {
        "application": "RPDistill",
        "version": __version__,
        "python": platform.python_version(),
        "platform": platform.system(),
        "architecture": platform.machine(),
        "stage": "E4b",
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
    # State transitions are internal API only until a real worker exists.
    return p


def main(argv=None) -> int:
    args = parser().parse_args(argv)
    try:
        if args.command in (None, "info"):
            result = runtime_info()
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
