"""Install the unsigned candidate in an isolated Windows directory, run native smoke, uninstall."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile

def main():
    if sys.platform!="win32":
        raise SystemExit("Windows only")
    p=argparse.ArgumentParser()
    p.add_argument("--installer",required=True,type=Path)
    p.add_argument("--report",required=True,type=Path)
    args=p.parse_args()
    installer=args.installer.resolve(strict=True)
    with tempfile.TemporaryDirectory(prefix="rpdistill-install-") as tmp:
        root=Path(tmp)
        install=root/"app"
        if " " in str(install):
            raise ValueError("NSIS silent test requires unquoted destination without spaces")
        subprocess.run([str(installer),"/S","/D="+str(install)],check=True,timeout=180)
        exe=install/"RPDistill Studio.exe"
        if not exe.is_file():
            raise ValueError("installed application missing")
        uninstall=list(install.glob("Uninstall*.exe"))
        if len(uninstall)!=1:
            raise ValueError("uninstaller missing")
        desktop=Path(os.environ["USERPROFILE"])/"Desktop"/"RPDistill Studio.lnk"
        menu=Path(os.environ["APPDATA"])/"Microsoft"/"Windows"/"Start Menu"/"Programs"/"RPDistill Studio.lnk"
        try:
            if not desktop.is_file() or not menu.is_file():
                raise ValueError("installation shortcuts missing")
            sentinel=root/"user-data.sqlite3"
            sentinel.write_bytes(b"preserve independent user data")
            # Same-version reinstall, not a cross-version migration test.
            subprocess.run([str(installer),"/S","/D="+str(install)],check=True,timeout=180)
            if not exe.is_file() or sentinel.read_bytes()!=b"preserve independent user data":
                raise ValueError("reinstall did not preserve application and independent data")
            if not desktop.is_file() or not menu.is_file():
                raise ValueError("reinstall shortcuts missing")
            smoke=Path(__file__).with_name("studio_desktop_smoke.py")
            subprocess.run([sys.executable,str(smoke),"--installed",str(exe)],check=True,timeout=180)
        finally:
            subprocess.run([str(uninstall[0]),"/S"],check=True,timeout=180)
        # NSIS may remove its temporary uninstaller asynchronously.
        import time
        for _ in range(40):
            if not exe.exists() and not desktop.exists() and not menu.exists():
                break
            time.sleep(0.25)
        if exe.exists() or desktop.exists() or menu.exists():
            raise ValueError("uninstall did not remove program and shortcuts")
        if sentinel.read_bytes()!=b"preserve independent user data":
            raise ValueError("independent user data changed")
        report={"installer_sha256":hashlib.file_digest(installer.open("rb"),"sha256").hexdigest(),
                "bytes":installer.stat().st_size,"installed_launch":True,"bundled_base_backend":True,
                "shortcuts":True,"same_version_reinstall":True,"uninstalled":True,"isolated_user_data_preserved":True,
                "signed":False,"release_ready":False}
        args.report.write_text(json.dumps(report,indent=2),encoding="utf-8")
        print(json.dumps(report))

if __name__=="__main__":
    main()
