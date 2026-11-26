"""Stage an offline base CPython runtime and exact local backend for Windows packaging.

Uses the trusted x64 setup-python runtime already installed on the build host.
No ML, model weights, pip cache, or developer site-packages are redistributed.
"""
import argparse
import json
import shutil
import subprocess
import sys
from pathlib import Path

def main():
    if sys.platform!="win32" or sys.maxsize<=2**32:
        raise SystemExit("Windows x64 packaging only")
    p=argparse.ArgumentParser()
    p.add_argument("--output",required=True,type=Path)
    args=p.parse_args()
    src=Path(sys.base_prefix).resolve()
    dest=args.output.resolve()
    if dest.exists():
        raise ValueError("new staging directory required")
    dest.mkdir(parents=True)
    for name in ("python.exe","python3.dll",f"python{sys.version_info.major}{sys.version_info.minor}.dll","LICENSE.txt"):
        shutil.copy2(src/name,dest/name)
    for f in src.glob("vcruntime*.dll"):
        shutil.copy2(f,dest/f.name)
    shutil.copytree(src/"DLLs",dest/"DLLs",ignore=shutil.ignore_patterns("__pycache__","*.pyc"))
    shutil.copytree(src/"Lib",dest/"Lib",ignore=shutil.ignore_patterns("site-packages","__pycache__","*.pyc","test","tests","ensurepip","idlelib","tkinter"))
    packages=dest/"packages"
    repo=Path(__file__).resolve().parents[1]
    wheels=dest/"wheels"
    subprocess.run([sys.executable,"-m","pip","wheel","--no-deps","--wheel-dir",str(wheels),str(repo)],check=True)
    wheel=list(wheels.glob("rpdistill-*.whl"))
    if len(wheel)!=1:
        raise ValueError("expected one exact backend wheel")
    subprocess.run([sys.executable,"-m","pip","install","--no-index","--no-deps","--no-compile","--target",str(packages),str(wheel[0])],check=True)
    pth=dest/f"python{sys.version_info.major}{sys.version_info.minor}._pth"
    pth.write_text(".\nLib\nDLLs\npackages\n",encoding="ascii")
    env=dict(__import__("os").environ)
    env.pop("PYTHONPATH",None);env.pop("PYTHONHOME",None)
    result=subprocess.run([str(dest/"python.exe"),"-I","-c",
        "import sys,sqlite3,ssl,rpdistill; print(rpdistill.__file__); assert sys.flags.isolated and sys.flags.no_site"],
        env=env,check=True,capture_output=True,text=True,timeout=30)
    if str(packages).casefold() not in result.stdout.casefold():
        raise ValueError("backend not imported from staged runtime")
    (dest/"runtime.json").write_text(json.dumps({"python":sys.version.split()[0],"architecture":"x64",
        "ml_dependencies_bundled":False,"source":"CI setup-python runtime","release_ready":False},indent=2),encoding="utf-8")
    (dest/"README.txt").write_text("RPDistill Studio offline base backend. ML/CUDA dependencies and model weights are not bundled. Use a trusted external Python environment via RPDISTILL_PYTHON for optional workloads. User data is separate from installation. Unsigned candidate build.\n",encoding="utf-8")

if __name__=="__main__":
    main()
