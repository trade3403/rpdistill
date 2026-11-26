"""Real bounded public model download, process loss, explicit recovery and registration.

The model is a random-weight transport fixture, not a translation quality benchmark.
No model code or weights are executed. Only an isolated temporary DB/cache is used.
"""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
from unittest.mock import patch

from rpdistill.downloads import DownloadQueue
from rpdistill.teachers import TeacherRegistry, describe, hub_client, plan_files, verify_snapshot
from rpdistill.transfer import transfer_file

MODEL = "optimum-internal-testing/tiny-random-llama"
LICENSE = "apache-2.0"
BUDGET = 16 * 1024 * 1024
EXIT_INTERRUPTED = 73


def interrupted_worker(db):
    # Test-only fault injection: exit abruptly after a real verified-hash weight
    # transfer has persisted a nonempty partial file. No synthetic payloads.
    def interrupt(url, dest, *, size, sha256=None, checkpoint=None, **kwargs):
        part = dest.with_name(dest.name + ".rpdistill-part")
        def check():
            if checkpoint:
                checkpoint()
            if dest.name.endswith(".safetensors") and sha256 and part.exists():
                if 0 < part.stat().st_size < size:
                    os._exit(EXIT_INTERRUPTED)
        return transfer_file(url, dest, size=size, sha256=sha256,
                             checkpoint=check, **kwargs)
    with patch("rpdistill.transfer.transfer_file", side_effect=interrupt):
        DownloadQueue(db).run_next()
    raise RuntimeError("expected abrupt interruption not observed")


def run():
    info = hub_client().model_info(MODEL, files_metadata=True, timeout=30, token=False)
    teacher = describe(info)
    assert teacher.model_id == MODEL and not teacher.private and not teacher.gated
    assert teacher.license == LICENSE
    selected = plan_files(info, BUDGET)
    weights = [(name, size, sha) for name, (size, sha) in selected.items()
               if name.endswith(".safetensors")]
    assert len(weights) == 1 and weights[0][1] > 512 * 1024 and weights[0][2]
    total = sum(size for size, _ in selected.values())
    with tempfile.TemporaryDirectory(prefix="rpdistill-live-download-") as tmp:
        root = Path(tmp)
        db = root / "queue.sqlite3"
        queue = DownloadQueue(db)
        job = queue.enqueue(MODEL, teacher.revision, reviewed_license=LICENSE,
                            max_bytes=BUDGET, cache_dir=root / "cache")
        child = subprocess.run([sys.executable, str(Path(__file__).resolve()),
                                "--interrupt-worker", str(db)], timeout=180)
        assert child.returncode == EXIT_INTERRUPTED, child.returncode
        active = queue.get(job["id"])
        assert active["state"] == "running"
        name, size, sha = weights[0]
        partial = root / "cache" / "rpdistill-http" / MODEL / teacher.revision / (name + ".rpdistill-part")
        offset = partial.stat().st_size
        assert 0 < offset < size
        assert TeacherRegistry(db).list() == []
        try:
            queue.recover(job["id"])
        except ValueError:
            pass
        else:
            raise AssertionError("unconfirmed recovery accepted")
        # subprocess.run has returned, proving this particular worker exited.
        assert queue.recover(job["id"], worker_stopped=True)["state"] == "interrupted"
        assert queue.control(job["id"], "resume")["state"] == "queued"
        received = []
        from rpdistill.transfer import open_https
        def observe(url, dest, **kw):
            def opener(request, timeout):
                response = open_https(request, timeout)
                if dest.name == name:
                    received.append((request.get_header("Range"), response.status))
                return response
            return transfer_file(url, dest, opener=opener, **kw)
        with patch("rpdistill.transfer.transfer_file", side_effect=observe):
            result = queue.run_next()
        assert result["state"] == "succeeded", result.get("error")
        assert result["done_bytes"] == result["total_bytes"] == total
        assert received and received[0][0] == f"bytes={offset}-"
        assert received[0][1] in (200, 206)  # 200 is a safe full-file restart.
        if received[0][1] == 206:
            assert result["network_bytes"] < total
        assert 0 < result["network_bytes"] <= total
        record = TeacherRegistry(db).get(MODEL, teacher.revision)
        assert record["license"] == LICENSE
        assert record["manifest"] == verify_snapshot(Path(record["path"]), selected)
        assert any(m["name"] == name and m["upstream_sha256_verified"] for m in record["manifest"])
        assert not partial.exists() and queue.run_next() is None
        print(json.dumps({"model": MODEL, "revision": teacher.revision,
                          "license": LICENSE, "total_verified_bytes": total,
                          "partial_bytes": offset, "range_response": received[0][1],
                          "byte_resume_confirmed": received[0][1] == 206,
                          "resumed_network_bytes": result["network_bytes"],
                          "registered": True, "process_recovery": True,
                          "quality_test": False}))


if __name__ == "__main__":
    if len(sys.argv) == 3 and sys.argv[1] == "--interrupt-worker":
        interrupted_worker(Path(sys.argv[2]))
    else:
        run()
