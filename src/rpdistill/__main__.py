"""Bootstrap CLI: report the local runtime without loading model weights."""
import json
import platform
import sys

from . import __version__


def runtime_info() -> dict[str, str]:
    return {
        "application": "RPDistill",
        "version": __version__,
        "python": platform.python_version(),
        "platform": platform.system(),
        "architecture": platform.machine(),
        "stage": "E1.1",
    }


def main() -> int:
    print(json.dumps(runtime_info(), ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
