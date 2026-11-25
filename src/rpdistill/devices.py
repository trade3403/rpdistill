"""Read-only hardware discovery; no model loading or GPU allocation."""
import csv
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
        result = subprocess.run(
            [binary, "--query-gpu=index,name,memory.total,memory.free",
             "--format=csv,noheader,nounits"],
            capture_output=True, text=True, check=True, timeout=5,
        )
        devices = []
        for row in csv.reader(result.stdout.splitlines(), skipinitialspace=True):
            if len(row) != 4:
                raise ValueError("unexpected nvidia-smi output")
            index, name, total, free = (value.strip() for value in row)
            devices.append({"index": int(index), "name": name,
                            "total_mib": int(total), "free_mib": int(free)})
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
