"""ModelScope public model discovery and SHA-pinned, verified download adapter."""
from dataclasses import asdict
from pathlib import Path, PurePosixPath
from types import SimpleNamespace
from itertools import islice
import json
import shutil

from .teachers import Teacher, TeacherRegistry, validate_id, validate_revision, plan_files, verify_snapshot


def client():
    try:
        from modelscope_hub import HubApi
    except ImportError as exc:
        raise ValueError("Install the ModelScope extra: python -m pip install -e .[modelscope]") from exc
    return HubApi(endpoint="https://modelscope.cn", token="")


def model_id(value):
    value = validate_id(value)
    if "/" not in value:
        raise ValueError("ModelScope requires owner/name")
    return value


def search_models(query, limit=20, *, api=None):
    if not isinstance(query, str) or not query.strip() or len(query) > 100:
        raise ValueError("query must contain 1–100 characters")
    if type(limit) is not int or not 1 <= limit <= 100:
        raise ValueError("limit must be between 1 and 100")
    api = client() if api is None else api
    page = api.list_repos("model", search=query.strip(), page_size=limit)
    results = []
    for item in islice(page.items, limit):
        try:
            name = model_id(item.repo_id)
        except (AttributeError, ValueError):
            continue
        results.append({"source": "modelscope", "model_id": name,
                        "license": getattr(item, "license", None),
                        "private": getattr(item, "private", None),
                        "gated": getattr(item, "gated", None),
                        "revision": None})
    return results


def revisions(name, *, api=None):
    api = client() if api is None else api
    return api.list_repo_revisions(model_id(name), "model")


def download_modelscope(model_id, revision, *, reviewed_license, max_bytes, cache_dir,
                        registry, api=None, progress=None, checkpoint=None):
    name = validate_id(model_id)
    if "/" not in name:
        raise ValueError("ModelScope requires owner/name")
    revision = validate_revision(revision)
    if not isinstance(reviewed_license, str) or not reviewed_license.strip():
        raise ValueError("explicit license review required")
    api = client() if api is None else api
    if checkpoint:
        checkpoint()
    detail = api.get_model(name)
    # Fail closed: repository-level license metadata is not a legal conclusion.
    if (detail.get("id") != name or detail.get("visibility") != "public"
            or detail.get("private") or detail.get("gated") or detail.get("login_required")):
        raise ValueError("public, unrestricted model identity could not be established")
    if detail.get("license") != reviewed_license:
        raise ValueError("license missing or differs from reviewed license")
    entries = api.list_repo_files(name, "model", revision=revision, recursive=True)
    siblings = []
    for entry in entries:
        if entry.is_dir:
            continue
        siblings.append(SimpleNamespace(rfilename=entry.path, size=entry.size,
            lfs=SimpleNamespace(sha256=entry.sha256)))
    selected = plan_files(SimpleNamespace(siblings=siblings), max_bytes)
    if any(not digest for _, digest in selected.values()):
        raise ValueError("ModelScope requires upstream SHA-256 for every selected file")
    root = Path(cache_dir).resolve()
    path = root / "modelscope" / name / revision
    path.mkdir(parents=True, exist_ok=True)
    if not path.resolve().is_relative_to(root):
        raise ValueError("snapshot outside configured cache")
    total = sum(size for size, _ in selected.values())
    if shutil.disk_usage(path).free < total:
        raise ValueError("insufficient disk space")
    done = 0
    manifest = []
    if progress:
        progress(0, total)
    for filename, (size, digest) in sorted(selected.items()):
        if checkpoint:
            checkpoint()
        dest = path.joinpath(*PurePosixPath(filename).parts)
        if not dest.resolve().is_relative_to(path.resolve()):
            raise ValueError("file path outside snapshot")
        downloaded = Path(api.download_file(name, "model", filename, revision=revision,
                    local_dir=path, expected_sha256=digest, file_size=size)).resolve()
        if downloaded != dest.resolve():
            raise ValueError("unexpected downloaded file location")
        manifest.extend(verify_snapshot(path, {filename: (size, digest)}, checkpoint=checkpoint))
        done += size
        if progress:
            progress(done, total)
    if checkpoint:
        checkpoint()
    with (path / "config.json").open(encoding="utf-8") as stream:
        if not isinstance(json.load(stream), dict):
            raise ValueError("invalid model configuration")
    teacher = Teacher(name, revision, reviewed_license, False, False, None)
    return registry.put(teacher, path, manifest)
