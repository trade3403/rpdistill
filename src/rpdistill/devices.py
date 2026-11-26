"""Read-only hardware discovery; no model loading or GPU allocation."""
import csv
import math
import os
from pathlib import Path
import platform
import shutil
import subprocess


def memory_bytes() -> int | None:
    try:
        if os.name == "nt":
            import ctypes
            from ctypes import wintypes

            class MemoryStatus(ctypes.Structure):
                _fields_ = [("length", wintypes.DWORD), ("load", wintypes.DWORD)] + [
                    (name, ctypes.c_ulonglong) for name in
                    ("total_phys", "avail_phys", "total_page", "avail_page",
                     "total_virtual", "avail_virtual", "avail_extended")
                ]
            status = MemoryStatus()
            status.length = ctypes.sizeof(status)
            if ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(status)):
                return int(status.total_phys)
            return None
        total = os.sysconf("SC_PHYS_PAGES") * os.sysconf("SC_PAGE_SIZE")
        return total if total > 0 else None
    except (AttributeError, OSError, ValueError):
        return None


def nvidia_info() -> dict:
    binary = shutil.which("nvidia-smi")
    if not binary:
        return {"status": "unavailable", "devices": []}
    try:
        def query(fields):
            return subprocess.run([binary, "--query-gpu="+fields,
                "--format=csv,noheader,nounits"],capture_output=True,text=True,check=True,timeout=5)
        try:
            result=query("index,name,memory.total,memory.free,utilization.gpu,temperature.gpu,power.draw")
        except subprocess.CalledProcessError:
            # Older drivers may reject optional fields; keep basic memory discovery.
            result=query("index,name,memory.total,memory.free")
        def optional(raw,low,high):
            try:
                value=float(raw)
                return value if math.isfinite(value) and low<=value<=high else None
            except ValueError:
                return None
        devices = []
        for row in csv.reader(result.stdout.splitlines(), skipinitialspace=True):
            if len(row) not in (4,7):
                raise ValueError("unexpected nvidia-smi output")
            index,name,total,free=(v.strip() for v in row[:4])
            total,free=int(total),int(free)
            if not 0<=free<=total or int(index)<0:
                raise ValueError("invalid GPU memory values")
            extra=row[4:] if len(row)==7 else ["","",""]
            devices.append({"index":int(index),"name":name,"total_mib":total,"free_mib":free,
                            "utilization_percent":optional(extra[0],0,100),
                            "temperature_c":optional(extra[1],-50,150),
                            "power_w":optional(extra[2],0,10000)})
        return {"status": "detected" if devices else "unavailable", "devices": devices}
    except (OSError, subprocess.SubprocessError, ValueError):
        return {"status": "probe_failed", "devices": []}


def device_report(path: str | Path = ".") -> dict:
    disk = shutil.disk_usage(path)
    return {
        "platform": platform.system(),
        "architecture": platform.machine(),
        "logical_cpus": os.cpu_count(),
        "memory_bytes": memory_bytes(),
        "disk": {"path": str(Path(path).resolve()), "total_bytes": disk.total,
                 "free_bytes": disk.free},
        "nvidia": nvidia_info(),
        "note": "Detection only; CUDA/PyTorch training readiness is not verified.",
    }
