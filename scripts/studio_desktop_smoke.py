"""Native Windows desktop launch and real persisted queue IPC smoke.

Linux and macOS GUI are out of scope; their backend tests remain independent.
Uses isolated temporary files and the actual local Python executable.
"""
import os
from pathlib import Path
import subprocess
import sys
import tempfile


def main():
    if sys.platform != "win32":
        raise SystemExit("Desktop smoke supports Windows only")
    desktop = Path(__file__).resolve().parents[1] / "desktop"
    cli = desktop / "node_modules" / "electron" / "cli.js"
    if not cli.is_file():
        raise SystemExit("Install desktop dependencies and build first")
    with tempfile.TemporaryDirectory(prefix="rpdistill-studio-") as tmp:
        root = Path(tmp)
        db = root / "studio.sqlite3"
        env = dict(os.environ, RPDISTILL_PYTHON=sys.executable, RPDISTILL_DB=str(db),
                   PYTHONIOENCODING="utf-8",RPDISTILL_STUDENT_ASSETS=str(root/"assets"),
                   RPDISTILL_CHECKPOINT_ROOT=str(root/"checkpoints"))
        subprocess.run([sys.executable, "-m", "rpdistill", "--db", str(db),
            "download-enqueue", "fixture/model", "--revision", "a" * 40,
            "--reviewed-license", "apache-2.0", "--max-bytes", "1024",
            "--cache-dir", str(root / "cache")], env=env, check=True, timeout=30)
        # Isolated registry fixture for pipeline creation only; never load its weights.
        from rpdistill.teachers import TeacherRegistry, Teacher
        TeacherRegistry(db).put(Teacher("fixture/model", "a" * 40, "apache-2.0", False, False, None), root / "cache", [])
        result = subprocess.run(["node", str(cli), ".", "--studio-smoke"],
            cwd=desktop, env=env, check=True, timeout=150, capture_output=True,
            text=True, encoding="utf-8", errors="replace")
        print(result.stdout, end="")
        print(result.stderr, end="", file=sys.stderr)
        if "studio_smoke=true" not in result.stdout.splitlines():
            raise SystemExit("Native Electron smoke did not confirm IPC and UI")
        print("native_desktop_smoke_pass=" + sys.platform)


if __name__ == "__main__":
    main()
