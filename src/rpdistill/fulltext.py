"""Bounded PMC OAI-PMH full-text acquisition with conservative rights checks."""
from contextlib import closing
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import shutil
import sqlite3
import tempfile
import time
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request
import xml.etree.ElementTree as ET

from .papers import license_code, retry_delay, normalize_doi
from .ncbi_papers import transient
from .transfer import open_https

ENDPOINT = "https://pmc.ncbi.nlm.nih.gov/api/oai/v1/mh/"
OAI = "{http://www.openarchives.org/OAI/2.0/}"
XLINK = "{http://www.w3.org/1999/xlink}href"
MAX_FILE = 16 * 1024 * 1024


class Blocked(ValueError):
    pass


class BudgetExceeded(ValueError):
    pass


def tag(node):
    return node.tag.rsplit("}", 1)[-1]


def children(node, name):
    return [x for x in node if tag(x) == name]


def one(node, name):
    rows = children(node, name)
    if len(rows) != 1:
        raise Blocked("missing or ambiguous " + name)
    return rows[0]


def pmcid_value(value):
    if not isinstance(value, str) or not re.fullmatch(r"PMC[0-9]{1,15}", value):
        raise ValueError("invalid PMCID")
    return value


class Budget:
    def __init__(self, limit):
        if type(limit) is not int or not 1 <= limit <= 2**40:
            raise ValueError("invalid download byte budget")
        self.limit, self.used = limit, 0

    def consume(self, size):
        self.used += size
        if self.used > self.limit:
            raise BudgetExceeded("response exceeds run byte budget")


def fetch_record(pmcid, prefix, budget, *, opener=open_https, sleep=time.sleep):
    pmcid_value(pmcid)
    if prefix not in ("pmc_fm", "pmc"):
        raise ValueError("invalid metadata prefix")
    request = Request(ENDPOINT + "?" + urlencode({
        "verb":"GetRecord", "identifier":"oai:pubmedcentral.nih.gov:" + pmcid[3:],
        "metadataPrefix":prefix}), headers={"Accept":"application/xml",
        "Accept-Encoding":"identity", "User-Agent":"RPDistill/0.1"})
    for attempt in range(3):
        try:
            with opener(request, timeout=30) as response:
                chunks = []
                total = 0
                while True:
                    remaining = min(MAX_FILE-total, budget.limit-budget.used)
                    # Probe at most one additional byte to detect oversize.
                    chunk = response.read(min(65536, max(1, remaining+1)))
                    if not chunk:
                        break
                    budget.consume(len(chunk))
                    total += len(chunk)
                    if total > MAX_FILE:
                        raise BudgetExceeded("XML exceeds per-response cap")
                    chunks.append(chunk)
                return b"".join(chunks)
        except (HTTPError, URLError, TimeoutError, ConnectionError) as exc:
            if isinstance(exc, HTTPError):
                exc.close()
            if not transient(exc) or attempt == 2:
                raise
            sleep(retry_delay(exc, attempt))


def inspect_record(raw, pmcid, *, full=False, expected_doi=None):
    """Require matching OAI identity and an explicit article-level CC BY/CC0 URI."""
    pmcid_value(pmcid)
    try:
        text = raw.decode("utf-8-sig")
        # Avoid entity expansion, external DTDs and non-UTF8 declaration tricks.
        if re.search(r"<!\s*(?:DOCTYPE|ENTITY)", text, re.I):
            raise Blocked("XML DTD or entity declaration is not supported")
        root = ET.fromstring(text)
    except (UnicodeError, ET.ParseError) as exc:
        raise Blocked("invalid XML") from exc
    if root.tag != OAI + "OAI-PMH" or root.find(OAI + "error") is not None:
        raise Blocked("OAI error or unexpected envelope")
    record = one(one(root, "GetRecord"), "record")
    header = one(record, "header")
    if header.get("status") == "deleted" or one(header, "identifier").text != (
            "oai:pubmedcentral.nih.gov:" + pmcid[3:]):
        raise Blocked("OAI identity mismatch or deleted record")
    article = one(one(record, "metadata"), "article")
    meta = one(one(article, "front"), "article-meta")
    ids = {}
    for node in children(meta, "article-id"):
        kind = node.get("pub-id-type")
        value = (node.text or "").strip()
        if kind in ids and ids[kind] != value:
            raise Blocked("conflicting article identifiers")
        ids[kind] = value
    values = [ids[k] for k in ("pmc", "pmcid") if k in ids]
    if not values or any(v not in (pmcid, pmcid[3:]) for v in values):
        raise Blocked("article PMCID mismatch")
    if expected_doi and normalize_doi(ids.get("doi")) != expected_doi:
        raise Blocked("article DOI mismatch")
    permissions = one(meta, "permissions")
    licenses = children(permissions, "license")
    if len(licenses) != 1:
        raise Blocked("ambiguous article license")
    lic = licenses[0]
    href = lic.get(XLINK) or lic.get("href")
    if not isinstance(href, str) or not re.fullmatch(
            r"https?://creativecommons\.org/(?:licenses/by/(?:2\.0|2\.5|3\.0|4\.0)|publicdomain/zero/1\.0)/?",
            href, re.I):
        raise Blocked("article license URI not allowlisted")
    code = license_code(href)
    if code is None:
        raise Blocked("unsupported license")
    # Alternate article-level permissions or explicitly restricted license text.
    wording = " ".join(lic.itertext()).lower()
    if re.search(r"non[- ]commercial|no[- ]derivatives|all rights reserved|cc[- ]by[- ](?:nc|nd|sa)", wording):
        raise Blocked("conflicting or restricted license wording")
    if full and not children(article, "body"):
        raise Blocked("full-text body missing")
    return {"license_uri":href, "license":code,
            "license_text":" ".join(lic.itertext()).strip(),
            "doi":normalize_doi(ids.get("doi")),
            "datestamp":one(header,"datestamp").text}


class FulltextLibrary:
    def __init__(self, db_path, root):
        self.db = Path(db_path)
        self.root = Path(root).resolve()
        self.root.mkdir(parents=True, exist_ok=True)
        with closing(sqlite3.connect(self.db)) as db, db:
            db.execute("""CREATE TABLE IF NOT EXISTS paper_fulltexts (
                pmcid TEXT PRIMARY KEY, record TEXT NOT NULL)""")

    def list(self):
        with closing(sqlite3.connect(self.db)) as db:
            return [json.loads(r[0]) for r in db.execute(
                "SELECT record FROM paper_fulltexts ORDER BY pmcid")]

    def path_for(self, pmcid):
        return self.root / (pmcid_value(pmcid) + ".xml")

    def save(self, db, record):
        db.execute("""INSERT INTO paper_fulltexts VALUES (?,?)
            ON CONFLICT(pmcid) DO UPDATE SET record=excluded.record""",
            (record["pmcid"], json.dumps(record, ensure_ascii=True)))

    def download(self, papers, *, max_bytes, limit=20, fetch=fetch_record, sleep=time.sleep):
        if type(limit) is not int or not 1 <= limit <= 50:
            raise ValueError("limit must be 1–50")
        budget = Budget(max_bytes)
        if shutil.disk_usage(self.root).free < max_bytes:
            raise ValueError("insufficient disk for approved budget")
        stats = dict(saved=0, cached=0, blocked=0, failed=0, inspected=0, bytes=0,
                     budget_exhausted=False)
        # Serialize workers using the shared project DB; commit per paper.
        # Separate processes using other databases must not share this output directory.
        for paper in papers:
            if stats["inspected"] >= limit:
                break
            if paper.get("eligibility") != "pending_fulltext_license":
                continue
            pmcid = pmcid_value(paper.get("pmcid"))
            stats["inspected"] += 1
            with closing(sqlite3.connect(self.db, timeout=5)) as db, db:
                db.execute("BEGIN IMMEDIATE")
                # Recheck current eligibility in case metadata changed since listing.
                row = db.execute("SELECT record FROM papers WHERE pmcid=?", (pmcid,)).fetchone()
                if not row or json.loads(row[0]).get("eligibility") != "pending_fulltext_license":
                    stats["blocked"] += 1
                    continue
                current = json.loads(row[0])
                expected_doi = current.get("doi")
                dest = self.path_for(pmcid)
                previous = db.execute("SELECT record FROM paper_fulltexts WHERE pmcid=?", (pmcid,)).fetchone()
                if dest.is_symlink():
                    raise ValueError("symlink in full-text directory")
                if previous:
                    old = json.loads(previous[0])
                    if (old.get("status") == "downloaded_pending_content_review"
                        and old.get("path") == str(dest) and dest.is_file()
                        and dest.stat().st_size == old.get("size")
                        and dest.stat().st_size <= MAX_FILE
                        and hashlib.sha256(dest.read_bytes()).hexdigest() == old.get("sha256")):
                        stats["cached"] += 1
                        continue
                result = {"pmcid":pmcid, "doi":expected_doi, "source":"ncbi-pmc-oai",
                          "retrieved_at":datetime.now(timezone.utc).isoformat()}
                try:
                    if budget.used >= budget.limit:
                        raise BudgetExceeded("budget exhausted")
                    sleep(1)
                    front = inspect_record(fetch(pmcid, "pmc_fm", budget), pmcid,
                                           expected_doi=expected_doi)
                    sleep(1)
                    raw = fetch(pmcid, "pmc", budget)
                    rights = inspect_record(raw, pmcid, full=True, expected_doi=expected_doi)
                    if front["license_uri"].rstrip("/") != rights["license_uri"].rstrip("/"):
                        raise Blocked("front matter and full-text license differ")
                    if front["datestamp"] != rights["datestamp"]:
                        raise Blocked("record changed between requests")
                    # Keep original OAI XML and provenance. No extracted content is certified.
                    tmp = None
                    try:
                        with tempfile.NamedTemporaryFile(dir=self.root, delete=False) as stream:
                            tmp = Path(stream.name)
                            stream.write(raw)
                        tmp.replace(dest)
                    finally:
                        if tmp is not None:
                            tmp.unlink(missing_ok=True)
                    result.update(rights, status="downloaded_pending_content_review",
                                  path=str(dest), size=len(raw),
                                  sha256=hashlib.sha256(raw).hexdigest())
                    stats["saved"] += 1
                except Blocked as exc:
                    result.update(status="blocked", reason=str(exc))
                    stats["blocked"] += 1
                except BudgetExceeded:
                    result.update(status="failed", reason="BudgetExceeded")
                    stats["failed"] += 1
                    stats["budget_exhausted"] = True
                except (HTTPError, URLError, TimeoutError, OSError) as exc:
                    result.update(status="failed", reason=type(exc).__name__)
                    stats["failed"] += 1
                self.save(db, result)
            if stats["budget_exhausted"]:
                break
        stats["bytes"] = budget.used
        return stats
