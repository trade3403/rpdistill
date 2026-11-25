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


def runtime_info() -> dict[str, str]:
    return {
        "application": "RPDistill",
        "version": __version__,
        "python": platform.python_version(),
        "platform": platform.system(),
        "architecture": platform.machine(),
        "stage": "E1.2",
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
    # State transitions are internal API only until a real worker exists.
    return p


def main(argv=None) -> int:
    args = parser().parse_args(argv)
    try:
        if args.command in (None, "info"):
            result = runtime_info()
        elif args.command == "devices":
            result = device_report(args.path)
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
