"""Real public network smoke: small config only, no model weight downloads."""
import json
from pathlib import Path
import tempfile
import sys

from rpdistill.teachers import hub_client, validate_revision
from rpdistill.modelscope_source import client, search_models
from rpdistill.transfer import transfer_file, hf_url


def hf():
    name = "openai-community/gpt2"
    api = hub_client()
    info = api.model_info(name, files_metadata=True, timeout=30, token=False)
    revision = validate_revision(info.sha)
    if info.private or info.gated or "license:mit" not in (info.tags or []):
        raise RuntimeError("public MIT smoke fixture changed")
    config = next(f for f in info.siblings if f.rfilename == "config.json")
    if not 0 < config.size <= 64 * 1024:
        raise RuntimeError("config exceeds smoke budget")
    with tempfile.TemporaryDirectory() as root:
        counts = []
        dest = transfer_file(hf_url(name, revision, "config.json"), Path(root)/"config.json",
                             size=config.size, on_bytes=counts.append)
        result = json.loads(dest.read_text(encoding="utf-8"))
        assert result.get("model_type") == "gpt2"
        assert sum(counts) == config.size
    print(json.dumps({"source":"huggingface","revision":revision,"bytes":sum(counts)}))


def ms():
    rows = search_models("Qwen", 5, api=client())
    if not rows:
        raise RuntimeError("no ModelScope search results")
    print(json.dumps({"source":"modelscope","count":len(rows)}))


if __name__ == "__main__":
    {"hf": hf, "ms": ms}[sys.argv[1]]()
