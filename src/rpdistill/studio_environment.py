"""Explicit Windows managed training environment deployment; never install into base Python."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
from uuid import uuid4

from . import __version__

PROFILES={"cpu":"https://download.pytorch.org/whl/cpu","cu128":"https://download.pytorch.org/whl/cu128"}
TORCH="2.7.1"
PROBE=r"""
import importlib, json, platform, struct, sys
assert sys.platform=="win32" and struct.calcsize("P")==8 and platform.machine().lower() in ("amd64","x86_64")
assert sys.version_info[:2] in ((3,11),(3,12))
print(json.dumps({"python":platform.python_version()}))
"""
VERIFY=r"""
import json, sys, torch, transformers, sentencepiece, safetensors, huggingface_hub, modelscope_hub, sacrebleu, rpdistill
profile=sys.argv[1]
assert rpdistill.__version__==sys.argv[2]
assert torch.__version__.split("+")[0]=="2.7.1"
assert sys.prefix!=sys.base_prefix
assert float((torch.tensor([2.0])*3).item())==6.0
cuda=bool(torch.cuda.is_available())
if profile=="cu128":
    assert torch.version.cuda=="12.8" and cuda
    assert float((torch.tensor([2.0],device="cuda")*3).item())==6.0
else:
    assert torch.version.cuda is None
print(json.dumps({"torch":torch.__version__,"cuda_available":cuda,"cuda_version":torch.version.cuda,"backend":rpdistill.__version__}))
"""

def stage(name):
    print(json.dumps({"stage":name}),flush=True)

def child_env():
    env={k:v for k,v in os.environ.items() if not k.upper().startswith(("PYTHON","PIP_"))}
    env["PIP_CONFIG_FILE"]=os.devnull
    env["PYTHONIOENCODING"]="utf-8"
    return env

def run(args,timeout=1800,*,capture=False):
    return subprocess.run([str(x) for x in args],check=True,timeout=timeout,env=child_env(),
        stdin=subprocess.DEVNULL,stdout=subprocess.PIPE if capture else subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,text=True,encoding="utf-8")

def deploy(python,wheel,root,profile,*,approved=False):
    if approved is not True or profile not in PROFILES or sys.platform!="win32":
        raise ValueError("explicit Windows deployment approval required")
    python=Path(python).resolve(strict=True)
    wheel=Path(wheel).resolve(strict=True)
    if not python.is_file() or python.name.lower()!="python.exe" or not wheel.is_file() or not re.fullmatch(r"rpdistill-"+re.escape(__version__)+r"-py3-none-any\.whl",wheel.name):
        raise ValueError("trusted Python executable and exact packaged wheel required")
    with wheel.open("rb") as stream:
        wheel_hash=hashlib.file_digest(stream,"sha256").hexdigest()
    root=Path(root).absolute()
    if root.is_symlink():
        raise ValueError("symlink managed root")
    stage("python-probe")
    run([python,"-I","-c",PROBE],30,capture=True)
    root.mkdir(parents=True,exist_ok=True)
    # Conservative free-space preflight, not a hard pip download or disk quota.
    if shutil.disk_usage(root).free < (12 if profile=="cpu" else 25)*1024**3:
        raise ValueError("insufficient free disk space")
    id=uuid4().hex
    dest=root/id
    stage("venv")
    run([python,"-I","-m","venv",dest],300)
    exe=dest/"Scripts"/"python.exe"
    pip=[exe,"-I","-m","pip","--isolated","--disable-pip-version-check","--no-input","install","--no-cache-dir","--only-binary=:all:"]
    stage("torch")
    run([*pip,"--index-url",PROFILES[profile],"torch=="+TORCH])
    stage("dependencies")
    run([*pip,"--index-url","https://pypi.org/simple",str(wheel)+"[hub,modelscope,student,evaluation]"])
    stage("verify")
    run([exe,"-I","-m","pip","--isolated","check"],120)
    measured=json.loads(run([exe,"-I","-c",VERIFY,profile,__version__],180,capture=True).stdout)
    with wheel.open("rb") as stream:
        if hashlib.file_digest(stream,"sha256").hexdigest()!=wheel_hash:
            raise ValueError("packaged wheel changed")
    snapshot=json.loads(run([exe,"-I","-m","rpdistill","--db",dest/"probe.sqlite3","studio-snapshot"],60,capture=True).stdout)
    if snapshot.get("version")!=__version__ or snapshot.get("read_only") is not True or snapshot.get("database_exists") is not False:
        raise ValueError("backend protocol verification failed")
    receipt={"schema":"rpdistill-managed-environment-v1","id":id,"profile":profile,"backend":__version__,
             "torch":measured["torch"],"cuda_available":measured["cuda_available"],"cuda_version":measured["cuda_version"],
             "runtime_verified":True,"wheel_sha256":wheel_hash}
    with (dest/"verified.json").open("x",encoding="utf-8") as f:
        json.dump(receipt,f,allow_nan=False)
    # No prior environment or active pointer is modified. Main process activates separately.
    print(json.dumps({"stage":"complete","id":id}),flush=True)
    return receipt

def main():
    p=argparse.ArgumentParser()
    for k in ("python","wheel","root","profile"):
        p.add_argument("--"+k,required=True)
    p.add_argument("--approved",action="store_true")
    a=p.parse_args()
    try:
        deploy(a.python,a.wheel,a.root,a.profile,approved=a.approved)
    except (ValueError,OSError,subprocess.SubprocessError) as exc:
        print(json.dumps({"stage":"failed","error":type(exc).__name__}),flush=True)
        return 2
    return 0

if __name__=="__main__":
    sys.exit(main())
