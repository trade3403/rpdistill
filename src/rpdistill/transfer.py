"""Bounded, revision-pinned public HTTP transfers with verified Range recovery."""
from __future__ import annotations

import hashlib
import re
from pathlib import Path
from urllib.request import Request, build_opener, HTTPRedirectHandler
from urllib.parse import urlsplit, quote


class HttpsRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        if urlsplit(newurl).scheme != "https":
            raise ValueError("HTTPS downgrade rejected")
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def open_https(request, timeout):
    if urlsplit(request.full_url).scheme != "https":
        raise ValueError("HTTPS required")
    return build_opener(HttpsRedirect()).open(request, timeout=timeout)


def digest_file(path):
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def transfer_file(url, dest, *, size, sha256=None, on_bytes=None, checkpoint=None,
                  opener=open_https, chunk_size=256 * 1024):
    """Report newly read payload bytes only, never cached or resumed bytes.

    A partial file is reusable only with an immutable URL and expected size;
    the caller must bind it to a revision. If available, verify upstream SHA-256.
    """
    if type(size) is not int or size < 0 or type(chunk_size) is not int or chunk_size <= 0:
        raise ValueError("invalid transfer size")
    if sha256 is not None and not re.fullmatch(r"[a-f0-9]{64}", sha256):
        raise ValueError("invalid expected SHA-256")
    dest = Path(dest)
    dest.parent.mkdir(parents=True, exist_ok=True)
    part = dest.with_name(dest.name + ".rpdistill-part")
    if dest.is_symlink() or part.is_symlink():
        raise ValueError("symlink in transfer destination")
    if dest.is_file() and dest.stat().st_size == size and (
        sha256 is not None and digest_file(dest) == sha256
    ):
        return dest
    # Without an upstream digest, restart unverified complete files.
    offset = part.stat().st_size if part.is_file() else 0
    if offset > size or (offset and sha256 is None):
        part.unlink()
        offset = 0
    if checkpoint:
        checkpoint()
    if offset < size or not part.exists():
        headers = {"Accept-Encoding": "identity"}
        if offset:
            headers["Range"] = f"bytes={offset}-"
        with opener(Request(url, headers=headers), timeout=30) as response:
            status = response.status
            if response.headers.get("Content-Encoding", "identity").lower() != "identity":
                raise ValueError("unexpected content encoding")
            if status == 206:
                expected_range = f"bytes {offset}-{size-1}/{size}"
                if not offset or response.headers.get("Content-Range") != expected_range:
                    raise ValueError("invalid Content-Range")
            elif status == 200:
                offset = 0  # Server ignored Range: replace, never append.
            else:
                raise ValueError("unexpected HTTP status")
            length = response.headers.get("Content-Length")
            if length is not None and int(length) != size - offset:
                raise ValueError("unexpected Content-Length")
            with part.open("ab" if offset else "wb") as stream:
                while True:
                    if checkpoint:
                        checkpoint()
                    data = response.read(chunk_size)
                    if not data:
                        break
                    if on_bytes:
                        on_bytes(len(data))
                    if offset + len(data) > size:
                        raise ValueError("response exceeds approved size")
                    stream.write(data)
                    offset += len(data)
    if offset != size:
        raise OSError("incomplete transfer; partial retained")
    if sha256 is not None and digest_file(part) != sha256:
        part.unlink()
        raise ValueError("upstream hash mismatch")
    if checkpoint:
        checkpoint()
    part.replace(dest)
    return dest


def hf_url(model_id, revision, filename):
    from .teachers import validate_id, validate_revision, safe_filename
    return ("https://huggingface.co/" + quote(validate_id(model_id), safe="/")
            + "/resolve/" + validate_revision(revision) + "/"
            + quote(safe_filename(filename), safe="/"))
