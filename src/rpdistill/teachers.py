"""Hugging Face teacher discovery and revision-pinned local model registration.

No model code is imported or executed. Downloads require explicit license review
and a byte budget. The optional Hub SDK manages transport/cache; CPU CI uses fakes.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from fnmatch import fnmatchcase
import hashlib
import json
from pathlib import Path, PurePosixPath
import re
import shutil
import sqlite3
import time
from contextlib import closing
from itertools import islice


def hub_client():
    try:
        from huggingface_hub import HfApi
    except ImportError as exc:
        raise ValueError("Install the Hub extra: python -m pip install -e .[hub]") from exc
    return HfApi(endpoint="https://huggingface.co")


def hub_download(**kwargs):
    from huggingface_hub import snapshot_download
    return snapshot_download(endpoint="https://huggingface.co", **kwargs)


def validate_id(value):
    if not isinstance(value, str) or not re.fullmatch(
        r"[A-Za-z0-9_][A-Za-z0-9_.-]{0,95}(?:/[A-Za-z0-9_][A-Za-z0-9_.-]{0,95})?", value
    ) or ".." in value or "--" in value or value.endswith((".", "-", ".git")):
        raise ValueError("invalid Hugging Face model identifier")
    return value


def validate_revision(value):
    if not isinstance(value, str) or not re.fullmatch(r"[a-f0-9]{40}", value):
        raise ValueError("a full immutable 40-character commit SHA is required")
    return value


@dataclass(frozen=True)
class Teacher:
    model_id: str
    revision: str
    license: str | None
    gated: bool
    private: bool
    pipeline: str | None


def describe(info) -> Teacher:
    tags = getattr(info, "tags", None) or []
    licenses = sorted({tag[8:] for tag in tags if isinstance(tag, str)
                       and tag.startswith("license:") and tag[8:]})
    return Teacher(
        validate_id(info.id), validate_revision(info.sha),
        licenses[0] if len(licenses) == 1 else None,
        bool(getattr(info, "gated", False)),
        bool(getattr(info, "private", False)),
        getattr(info, "pipeline_tag", None),
    )


def search_teachers(query: str, limit: int = 20, *, api=None) -> list[Teacher]:
    if not isinstance(query, str) or not query.strip() or len(query) > 100:
        raise ValueError("query must contain 1–100 characters")
    if type(limit) is not int or not 1 <= limit <= 100:
        raise ValueError("limit must be between 1 and 100")
    api = hub_client() if api is None else api
    models = api.list_models(search=query.strip(), limit=limit, full=True, token=False)
    result = []
    for model in islice(models, limit):
        try:
            result.append(describe(model))
        except (ValueError, AttributeError):
            # An unpinned or malformed search result is not a usable candidate.
            continue
    return result


PATTERNS = ("*.json", "*.safetensors", "*.model", "*.txt", "*.tiktoken", "*.jinja")


def safe_filename(name):
    if not isinstance(name, str) or not name or len(name) > 512:
        raise ValueError("invalid repository filename")
    path = PurePosixPath(name)
    if (path.is_absolute() or any(part in ("", ".", "..") for part in name.split("/"))
            or any(c in name for c in "\\:*?[]<>|\"") or any(ord(c) < 32 for c in name)):
        raise ValueError("unsafe repository filename")
    if any(part.rstrip(". ") != part or re.fullmatch(
        r"(?i)(CON|PRN|AUX|NUL|COM[1-9]|LPT[1-9])(?:\..*)?", part
    ) for part in path.parts):
        raise ValueError("unsafe Windows filename")
    return name


def plan_files(info, max_bytes):
    if type(max_bytes) is not int or max_bytes <= 0:
        raise ValueError("download budget must be a positive integer")
    selected = {}
    folded = set()
    for sibling in getattr(info, "siblings", None) or []:
        name = safe_filename(sibling.rfilename)
        if not any(fnmatchcase(name, pattern) for pattern in PATTERNS):
            continue
        if name.casefold() in folded:
            raise ValueError("duplicate or case-conflicting repository filenames")
        folded.add(name.casefold())
        size = getattr(sibling, "size", None)
        if type(size) is not int or size < 0:
            raise ValueError("missing file size; cannot enforce download budget")
        lfs = getattr(sibling, "lfs", None)
        sha = getattr(lfs, "sha256", None) if lfs is not None else None
        if sha is not None and not re.fullmatch(r"[a-f0-9]{64}", sha):
            raise ValueError("invalid upstream SHA-256")
        selected[name] = (size, sha)
    if ("config.json" not in selected
            or not any(n.endswith(".safetensors") for n in selected)
            or not any(n in selected for n in (
                "tokenizer.json", "tokenizer.model", "vocab.json", "vocab.txt",
                "spiece.model", "sentencepiece.bpe.model"))):
        raise ValueError("model requires config, tokenizer and SafeTensors weights")
    if sum(size for size, _ in selected.values()) > max_bytes:
        raise ValueError("model exceeds approved byte budget")
    return selected


def verify_snapshot(path, selected, *, checkpoint=None):
    manifest = []
    for name, (size, expected) in sorted(selected.items()):
        if checkpoint is not None:
            checkpoint()
        file = path.joinpath(*PurePosixPath(name).parts)
        if not file.is_file() or file.stat().st_size != size:
            raise ValueError(f"missing or truncated file: {name}")
        digest = hashlib.sha256()
        with file.open("rb") as stream:
            for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                digest.update(chunk)
        actual = digest.hexdigest()
        if expected is not None and actual != expected:
            raise ValueError(f"upstream hash mismatch: {name}")
        manifest.append({"name": name, "size": size, "sha256": actual,
                         "upstream_sha256_verified": expected is not None})
    return manifest


class TeacherRegistry:
    def __init__(self, db_path):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        with closing(sqlite3.connect(self.db_path)) as db, db:
            db.execute("""CREATE TABLE IF NOT EXISTS teachers (
                model_id TEXT NOT NULL, revision TEXT NOT NULL, record TEXT NOT NULL,
                PRIMARY KEY(model_id, revision))""")

    def put(self, teacher, path, manifest):
        record = asdict(teacher) | {"path": str(path), "manifest": manifest}
        with closing(sqlite3.connect(self.db_path)) as db, db:
            db.execute("""INSERT INTO teachers VALUES (?, ?, ?)
                ON CONFLICT(model_id, revision) DO UPDATE SET record=excluded.record""",
                (teacher.model_id, teacher.revision, json.dumps(record, allow_nan=False)))
        return record

    def list(self):
        with closing(sqlite3.connect(self.db_path)) as db:
            return [json.loads(row[0]) for row in db.execute(
                "SELECT record FROM teachers ORDER BY model_id, revision")]


def download_teacher(model_id, revision, *, reviewed_license, max_bytes, cache_dir,
                     registry, api=None, downloader=None, progress=None, checkpoint=None,
                     retry_limit=2):
    model_id, revision = validate_id(model_id), validate_revision(revision)
    if type(retry_limit) is not int or not 0 <= retry_limit <= 3:
        raise ValueError("retry_limit must be between 0 and 3")
    if checkpoint is not None:
        checkpoint()
    if not isinstance(reviewed_license, str) or not reviewed_license.strip():
        raise ValueError("explicit license review is required")
    api = hub_client() if api is None else api
    info = api.model_info(model_id, revision=revision, files_metadata=True,
                          timeout=30, token=False)
    teacher = describe(info)
    if teacher.model_id != model_id or teacher.revision != revision:
        raise ValueError("upstream model identity or revision mismatch")
    if teacher.gated or teacher.private:
        raise ValueError("restricted models require a future authorized access adapter")
    if teacher.license is None or teacher.license != reviewed_license:
        raise ValueError("license missing or does not match reviewed license")
    selected = plan_files(info, max_bytes)
    cache = Path(cache_dir).resolve()
    cache.mkdir(parents=True, exist_ok=True)
    if shutil.disk_usage(cache).free < sum(size for size, _ in selected.values()):
        raise ValueError("insufficient disk space for selected files")
    downloader = hub_download if downloader is None else downloader
    def fetch(names):
        for attempt in range(retry_limit + 1):
            if checkpoint is not None:
                checkpoint()
            try:
                result = Path(downloader(repo_id=model_id, revision=revision,
                    cache_dir=cache, allow_patterns=names, token=False,
                    max_workers=2)).resolve()
                if not result.is_relative_to(cache):
                    raise ValueError("snapshot is outside configured cache")
                return result
            except Exception as exc:
                response = getattr(exc, "response", None)
                status = getattr(response, "status_code", None)
                transient = status in (408, 429, 500, 502, 503, 504) or (
                    status is None and isinstance(exc, (TimeoutError, ConnectionError)))
                if not transient or attempt >= retry_limit:
                    raise
                time.sleep(min(2 ** attempt, 4))

    if progress is None:
        path = fetch(list(selected))
        manifest = verify_snapshot(path, selected, checkpoint=checkpoint)
    else:
        total = sum(size for size, _ in selected.values())
        done = 0
        manifest = []
        path = None
        progress(0, total)
        for name, metadata in sorted(selected.items()):
            current = fetch([name])
            if path is not None and current != path:
                raise ValueError("snapshot location changed between files")
            path = current
            manifest.extend(verify_snapshot(path, {name: metadata}, checkpoint=checkpoint))
            done += metadata[0]
            progress(done, total)
    if checkpoint is not None:
        checkpoint()
    with (path / "config.json").open(encoding="utf-8") as stream:
        if not isinstance(json.load(stream), dict):
            raise ValueError("invalid model configuration")
    return registry.put(teacher, path, manifest)
