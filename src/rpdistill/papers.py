"""Europe PMC metadata discovery; no full-text retrieval or training authorization."""
from __future__ import annotations

from contextlib import closing
from dataclasses import asdict, dataclass
from datetime import date, datetime, timezone
import json
import re
import sqlite3
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import Request
from urllib.error import HTTPError, URLError
from email.utils import parsedate_to_datetime
import time

from .transfer import open_https

ENDPOINT = "https://www.ebi.ac.uk/europepmc/webservices/rest/search"
MAX_RESPONSE = 8 * 1024 * 1024


def phrase(value):
    if (not isinstance(value, str) or not value.strip() or len(value) > 200
            or any(ord(c) < 32 or c in '"\\' for c in value)):
        raise ValueError("invalid search phrase")
    return '"' + value.strip() + '"'


def iso_date(value):
    if not isinstance(value, str) or not re.fullmatch(r"[0-9]{4}-[0-9]{2}-[0-9]{2}", value):
        raise ValueError("date must be YYYY-MM-DD")
    return date.fromisoformat(value)


@dataclass(frozen=True)
class PaperQuery:
    keywords: tuple[str, ...]
    start_date: str
    end_date: str
    subject: str | None = None
    language: str | None = "eng"
    limit: int = 100
    open_access_only: bool = True

    def __post_init__(self):
        if not isinstance(self.keywords, (tuple, list)) or not 1 <= len(self.keywords) <= 10:
            raise ValueError("supply 1–10 keywords")
        for term in self.keywords:
            phrase(term)
        object.__setattr__(self, "keywords", tuple(self.keywords))
        if self.subject is not None:
            phrase(self.subject)
        if iso_date(self.start_date) > iso_date(self.end_date):
            raise ValueError("invalid date range")
        if self.language is not None and not re.fullmatch(r"[a-z]{3}", self.language):
            raise ValueError("language must be a three-letter lowercase code")
        if type(self.limit) is not int or not 1 <= self.limit <= 500:
            raise ValueError("limit must be 1–500")
        if type(self.open_access_only) is not bool:
            raise ValueError("open_access_only must be boolean")

    def expression(self):
        clauses = ["(" + " OR ".join(phrase(x) for x in self.keywords) + ")"]
        if self.subject:
            clauses.append(phrase(self.subject))
        clauses.append(f"FIRST_PDATE:[{self.start_date} TO {self.end_date}]")
        if self.language:
            clauses.append("LANG:" + self.language)
        if self.open_access_only:
            clauses.append("OPEN_ACCESS:Y")
        return " AND ".join(clauses)


def retry_delay(error, attempt):
    delay = 2 ** (attempt + 1)
    if isinstance(error, HTTPError):
        value = error.headers.get("Retry-After") if error.headers else None
        if value:
            try:
                requested = int(value)
            except ValueError:
                try:
                    stamp = parsedate_to_datetime(value)
                    if stamp.tzinfo is None:
                        stamp = stamp.replace(tzinfo=timezone.utc)
                    requested = (stamp - datetime.now(timezone.utc)).total_seconds()
                except (ValueError, TypeError, OverflowError):
                    requested = 0
            delay = max(delay, requested)
    # Respect long server backoff by aborting instead of retrying too early.
    if delay > 60:
        raise error
    return delay


def fetch_page(params, *, opener=open_https, sleep=time.sleep, attempts=4, endpoint=ENDPOINT):
    if type(attempts) is not int or not 1 <= attempts <= 5:
        raise ValueError("attempts must be 1–5")
    request = Request(endpoint + "?" + urlencode(params),
                      headers={"Accept":"application/json", "User-Agent":"RPDistill/0.1"})
    for attempt in range(attempts):
        try:
            with opener(request, timeout=30) as response:
                raw = response.read(MAX_RESPONSE + 1)
            break
        except (HTTPError, URLError, TimeoutError, ConnectionError) as exc:
            if isinstance(exc, HTTPError):
                transient = exc.code in (408, 429, 500, 502, 503, 504)
                exc.close()
            elif isinstance(exc, URLError):
                import ssl
                transient = not isinstance(exc.reason, ssl.SSLError)
            else:
                transient = True
            if not transient or attempt == attempts - 1:
                raise
            sleep(retry_delay(exc, attempt))
    if len(raw) > MAX_RESPONSE:
        raise ValueError("Europe PMC metadata response exceeds limit")
    data = json.loads(raw)
    if not isinstance(data, dict):
        raise ValueError("invalid Europe PMC response")
    return data


def normalize_doi(value):
    if not isinstance(value, str):
        return None
    value = re.sub(r"^(?:https?://(?:dx\.)?doi\.org/|doi:\s*)", "", value.strip(), flags=re.I)
    value = value.lower()
    return value if len(value) <= 512 and re.fullmatch(r"10\.[0-9]{4,9}/[^\s\x00-\x1f]+", value) else None


def license_code(value):
    """Conservative exact matching; no substring matching of restricted licenses."""
    if not isinstance(value, str):
        return None
    value = value.strip().lower().rstrip("/")
    if re.fullmatch(r"https?://creativecommons\.org/licenses/by/(?:2\.0|2\.5|3\.0|4\.0)", value):
        return "cc-by"
    if re.fullmatch(r"https?://creativecommons\.org/publicdomain/zero/1\.0", value):
        return "cc0"
    value = re.sub(r"[ _-]+", "-", value)
    if re.fullmatch(r"cc-by(?:-(?:2\.0|2\.5|3\.0|4\.0))?", value):
        return "cc-by"
    if value in ("cc0", "cc0-1.0", "cc-zero"):
        return "cc0"
    return None


@dataclass(frozen=True)
class Paper:
    provider_id: str
    title: str
    doi: str | None
    pmcid: str | None
    publication_date: str | None
    journal: str
    authors: str
    license_raw: str | None
    license_hint: str | None
    open_access: bool
    eligibility: str
    discovered_at: str


def paper_from_record(row):
    source, identifier = row.get("source"), row.get("id")
    if not isinstance(source, str) or not re.fullmatch(r"[A-Z0-9]{1,12}", source):
        raise ValueError("missing publication source")
    if not isinstance(identifier, str) or not re.fullmatch(r"[A-Za-z0-9._:/-]{1,200}", identifier):
        raise ValueError("missing publication id")
    title = row.get("title")
    if not isinstance(title, str) or not title.strip() or len(title) > 10000:
        raise ValueError("invalid title")
    pmcid = row.get("pmcid")
    if not isinstance(pmcid, str) or not re.fullmatch(r"PMC[0-9]+", pmcid):
        pmcid = None
    pubdate = row.get("firstPublicationDate")
    try:
        iso_date(pubdate)
    except (ValueError, TypeError):
        pubdate = None
    raw = row.get("license")
    raw = raw if isinstance(raw, str) and len(raw) <= 1000 else None
    hint = license_code(raw)
    oa = row.get("isOpenAccess") == "Y"
    # Metadata is only a pre-screen. Even positive hints require full-text rights review.
    eligibility = "pending_fulltext_license" if oa and pmcid and hint else "blocked_metadata"
    def bounded(key):
        value = row.get(key)
        return value[:10000] if isinstance(value, str) else ""
    return Paper(f"{source}:{identifier}", title.strip(), normalize_doi(row.get("doi")),
                 pmcid, pubdate, bounded("journalTitle"), bounded("authorString"),
                 raw, hint, oa, eligibility, datetime.now(timezone.utc).isoformat())


class PaperCatalog:
    def __init__(self, db_path):
        self.path = Path(db_path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with closing(self.connect()) as db, db:
            db.execute("""CREATE TABLE IF NOT EXISTS papers (
                paper_id INTEGER PRIMARY KEY, doi TEXT UNIQUE, pmcid TEXT UNIQUE,
                record TEXT NOT NULL)""")
            db.execute("""CREATE TABLE IF NOT EXISTS paper_aliases (
                provider_id TEXT PRIMARY KEY, paper_id INTEGER NOT NULL REFERENCES papers(paper_id))""")

    def connect(self):
        db = sqlite3.connect(self.path, timeout=10)
        db.execute("PRAGMA foreign_keys=ON")
        return db

    def ingest(self, paper):
        with closing(self.connect()) as db, db:
            db.execute("BEGIN IMMEDIATE")
            matches = set()
            for sql, value in (
                ("SELECT paper_id FROM paper_aliases WHERE provider_id=?", paper.provider_id),
                ("SELECT paper_id FROM papers WHERE doi=?", paper.doi),
                ("SELECT paper_id FROM papers WHERE pmcid=?", paper.pmcid),
            ):
                if value:
                    found = db.execute(sql, (value,)).fetchone()
                    if found:
                        matches.add(found[0])
            if len(matches) > 1:
                return "conflict"
            if matches:
                pid = matches.pop()
                old_doi, old_pmcid, raw = db.execute(
                    "SELECT doi,pmcid,record FROM papers WHERE paper_id=?", (pid,)).fetchone()
                if ((old_doi and paper.doi and old_doi != paper.doi)
                        or (old_pmcid and paper.pmcid and old_pmcid != paper.pmcid)):
                    return "conflict"
                record = json.loads(raw)
                # Never upgrade a prior blocked record from conflicting metadata.
                if record["eligibility"] != paper.eligibility or record["license_hint"] != paper.license_hint:
                    record["eligibility"] = "blocked_metadata"
                record["doi"] = old_doi or paper.doi
                record["pmcid"] = old_pmcid or paper.pmcid
                db.execute("UPDATE papers SET doi=?,pmcid=?,record=? WHERE paper_id=?",
                           (record["doi"], record["pmcid"], json.dumps(record), pid))
                result = "duplicate"
            else:
                pid = db.execute("INSERT INTO papers(doi,pmcid,record) VALUES (?,?,?)",
                                 (paper.doi, paper.pmcid, json.dumps(asdict(paper)))).lastrowid
                result = "inserted"
            db.execute("INSERT OR IGNORE INTO paper_aliases VALUES (?,?)", (paper.provider_id, pid))
            return result

    def list(self, limit=100):
        if type(limit) is not int or not 1 <= limit <= 500:
            raise ValueError("limit must be 1–500")
        with closing(self.connect()) as db:
            return [json.loads(row[0]) | {"paper_id": row[1]} for row in db.execute(
                "SELECT record,paper_id FROM papers ORDER BY paper_id LIMIT ?", (limit,))]


def discover(query, catalog, *, fetch=fetch_page, sleep=time.sleep):
    """Limit refers to inspected result records, not guaranteed new/eligible papers."""
    if not isinstance(query, PaperQuery):
        raise ValueError("expected PaperQuery")
    stats = dict(inspected=0, inserted=0, duplicate=0, conflict=0, invalid=0, pages=0)
    cursor = "*"
    seen = set()
    while stats["inspected"] < query.limit and stats["pages"] < 20:
        params = dict(query=query.expression(), format="json", resultType="core",
                      pageSize=min(50, query.limit-stats["inspected"]), cursorMark=cursor,
                      sort="P_PDATE_D desc")
        payload = fetch(params)
        stats["pages"] += 1
        rows = payload.get("resultList", {}).get("result")
        if not isinstance(rows, list):
            raise ValueError("invalid Europe PMC result list")
        for row in rows[:query.limit-stats["inspected"]]:
            stats["inspected"] += 1
            try:
                paper = paper_from_record(row) if isinstance(row, dict) else None
                if paper is None or (paper.publication_date and not
                    query.start_date <= paper.publication_date <= query.end_date):
                    raise ValueError("invalid or out-of-range publication")
                stats[catalog.ingest(paper)] += 1
            except (ValueError, TypeError):
                stats["invalid"] += 1
        nxt = payload.get("nextCursorMark")
        if (not rows or not isinstance(nxt, str) or not nxt or nxt == cursor
                or nxt in seen or stats["inspected"] >= query.limit):
            break
        seen.add(cursor)
        cursor = nxt
        sleep(1)
    return stats
