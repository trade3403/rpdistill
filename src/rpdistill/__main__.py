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


def runtime_info() -> dict[str, str]:
    return {
        "application": "RPDistill",
        "version": __version__,
        "python": platform.python_version(),
        "platform": platform.system(),
        "architecture": platform.machine(),
        "stage": "E2.3",
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
    # State transitions are internal API only until a real worker exists.
    return p


def main(argv=None) -> int:
    args = parser().parse_args(argv)
    try:
        if args.command in (None, "info"):
            result = runtime_info()
        elif args.command == "devices":
            result = device_report(args.path)
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
