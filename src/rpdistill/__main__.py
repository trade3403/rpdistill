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


def runtime_info() -> dict[str, str]:
    return {
        "application": "RPDistill",
        "version": __version__,
        "python": platform.python_version(),
        "platform": platform.system(),
        "architecture": platform.machine(),
        "stage": "E2.1",
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
    commands.add_parser("model-list")
    fetch = commands.add_parser("model-download")
    fetch.add_argument("model_id")
    fetch.add_argument("--revision", required=True)
    fetch.add_argument("--reviewed-license", required=True,
                       help="License identifier after reviewing intended-use rights")
    fetch.add_argument("--max-bytes", type=int, required=True)
    fetch.add_argument("--cache-dir", default=str(Path.home() / ".rpdistill" / "hub"))
    # State transitions are internal API only until a real worker exists.
    return p


def main(argv=None) -> int:
    args = parser().parse_args(argv)
    try:
        if args.command in (None, "info"):
            result = runtime_info()
        elif args.command == "devices":
            result = device_report(args.path)
        elif args.command == "model-search":
            result = [asdict(x) for x in search_teachers(args.query, args.limit)]
        elif args.command == "model-list":
            result = TeacherRegistry(args.db).list()
        elif args.command == "model-download":
            result = download_teacher(
                args.model_id, args.revision, reviewed_license=args.reviewed_license,
                max_bytes=args.max_bytes, cache_dir=args.cache_dir,
                registry=TeacherRegistry(args.db))
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
    except (ValueError, KeyError, OSError) as exc:
        print(str(exc), file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
