"""Conservative JATS prose extraction and persistent candidate translations.

Candidates are not a certified training dataset. Unhandled markup and suspicious
rights notices are excluded; semantic quality and broader rights review remain
separate gates.
"""
from contextlib import closing
from collections import Counter
import hashlib
import json
from pathlib import Path
import re
import sqlite3
import tempfile
import xml.etree.ElementTree as ET

from .fulltext import MAX_FILE, Blocked, inspect_record, one, children, tag, pmcid_value
from .inference import PROMPT_VERSION

PARSER_VERSION = "jats-prose-v1"
POLICY_VERSION = "candidate-check-v1"
INLINE = {"italic", "bold", "underline", "monospace", "sc", "styled-content", "xref"}
RIGHTS = re.compile(r"third[- ]party|reproduced (?:from|with)|adapted (?:from|with)|"
                    r"used with permission|all rights reserved|copyright|"
                    r"not (?:covered|included) (?:by|in) (?:the|this) license|"
                    r"non[- ]commercial|no[- ]derivatives", re.I)
NUMBERS = re.compile(r"(?<![A-Za-z0-9])[-+−]?[0-9]+(?:[.,][0-9]+)*(?:[eE][-+]?[0-9]+)?%?")
SENTENCE = re.compile(r"(?<=[.!?。！？])\s+")
MAX_SEGMENTS = 2000


def digest(data):
    return hashlib.sha256(data).hexdigest()


def clean(text):
    return " ".join(text.split())


def stable_split(pmcid):
    bucket = int(digest(("rpdistill-paper-split-v1:" + pmcid).encode())[:8],16) % 100
    return "train" if bucket < 80 else "validation" if bucket < 90 else "test"


def split_prose(text, max_chars):
    """Never slice a token or silently truncate a long paragraph."""
    parts = SENTENCE.split(text)
    result, current = [], ""
    for part in parts:
        if len(part) > max_chars:
            return None
        if current and len(current) + 1 + len(part) > max_chars:
            result.append(current)
            current = ""
        current = (current + " " + part).strip()
    if current:
        result.append(current)
    return result


def extract(raw, record, catalog, *, max_chars=1200):
    if type(max_chars) is not int or not 128 <= max_chars <= 8000:
        raise ValueError("max_chars must be 128–8000")
    pmcid = pmcid_value(record["pmcid"])
    if record.get("status") != "downloaded_pending_content_review":
        raise Blocked("fulltext is not available for content screening")
    if catalog.get("eligibility") != "pending_fulltext_license":
        raise Blocked("current paper metadata no longer eligible")
    if len(raw) > MAX_FILE or len(raw) != record.get("size") or digest(raw) != record.get("sha256"):
        raise Blocked("fulltext integrity mismatch")
    rights = inspect_record(raw, pmcid, full=True, expected_doi=catalog.get("doi"))
    if rights["license_uri"] != record.get("license_uri") or rights["datestamp"] != record.get("datestamp"):
        raise Blocked("registered rights or version mismatch")
    root = ET.fromstring(raw.decode("utf-8-sig"))
    article = one(one(one(one(root,"GetRecord"),"record"),"metadata"),"article")
    meta = one(one(article,"front"),"article-meta")
    # Restrict to prose in English research articles; uncertain language is blocked.
    lang = article.get("{http://www.w3.org/XML/1998/namespace}lang", "").lower()
    if lang and lang not in ("en","eng","en-us","en-gb"):
        raise Blocked("unsupported article language")
    # Missing XML language is not asserted as English: require catalog query
    # evidence in future stages; for now use a conservative Latin-prose heuristic.
    if article.get("article-type") in ("retraction","correction","expression-of-concern"):
        raise Blocked("excluded article type")
    authors = []
    for group in children(meta,"contrib-group"):
        for contrib in children(group,"contrib"):
            if contrib.get("contrib-type") not in (None,"author"):
                continue
            names = children(contrib,"name") + children(contrib,"string-name") + children(contrib,"collab")
            for name in names:
                value = clean(" ".join(name.itertext()))
                if value and value not in authors:
                    authors.append(value)
    author = "; ".join(authors) or catalog.get("authors","")
    title = catalog.get("title","")
    if not author or not title:
        raise Blocked("missing attribution metadata")
    attribution = {"pmcid":pmcid,"doi":rights["doi"],"title":title,"authors":author,
                   "url":"https://pmc.ncbi.nlm.nih.gov/articles/"+pmcid+"/",
                   "license_uri":rights["license_uri"],"license_text":rights["license_text"],
                   "xml_sha256":record["sha256"],"datestamp":rights["datestamp"]}
    rows, seen, stats = [], set(), Counter()
    ordinal = 0

    def paragraph(node, section):
        nonlocal ordinal
        ordinal += 1
        # Rights attributes/complex structures may carry third-party material.
        for item in node.iter():
            if (item is not node and tag(item) not in INLINE
                    or any("license" in k.lower() or "copyright" in k.lower()
                           for k in item.attrib)):
                stats["excluded_markup"] += 1
                return
        text = clean("".join(node.itertext()))
        if RIGHTS.search(text):
            stats["excluded_rights_notice"] += 1
            return
        if len(text) < 40 or len(re.findall(r"[A-Za-z]",text)) < len(text)*0.35:
            stats["excluded_short_or_nonlatin"] += 1
            return
        pieces = split_prose(text,max_chars)
        if pieces is None:
            stats["excluded_long_sentence"] += 1
            return
        for idx, piece in enumerate(pieces):
            if len(piece) < 20:
                stats["excluded_short_or_nonlatin"] += 1
                continue
            text_hash = digest(piece.encode())
            if text_hash in seen:
                stats["duplicate"] += 1
                continue
            if len(rows) >= MAX_SEGMENTS:
                raise Blocked("paper exceeds segment safety limit")
            seen.add(text_hash)
            sid = digest(f"{pmcid}:{record['sha256']}:{PARSER_VERSION}:{ordinal}:{idx}:{text_hash}".encode())
            rows.append({"segment_id":sid,"pmcid":pmcid,"section":section,
                         "ordinal":ordinal,"part":idx,"source_text":piece,
                         "source_sha256":text_hash,"split":stable_split(pmcid),
                         "attribution":attribution,"parser_version":PARSER_VERSION,
                         "status":"candidate_source"})
            stats["extracted"] += 1

    def walk(node, section, depth=0):
        if depth > 32:
            raise Blocked("section nesting exceeds limit")
        # Do not descend into tables, figures, footnotes, quotations, references,
        # formulas, boxed text, supplementary files, or alternate sub-articles.
        if any(tag(x) in ("permissions","license","copyright-statement","license_ref")
               for x in node):
            stats["excluded_rights_section"] += 1
            return
        for item in node:
            name = tag(item)
            if name == "p":
                paragraph(item,section)
            elif name == "sec":
                titles = children(item,"title")
                label = clean("".join(titles[0].itertext()))[:200] if titles else "section"
                walk(item,section+" / "+label,depth+1)
            elif name != "title":
                stats["excluded_container"] += 1

    for abstract in children(meta,"abstract"):
        if abstract.get("abstract-type") not in (None,"summary"):
            continue
        walk(abstract,"abstract")
    walk(one(article,"body"),"body")
    return rows, dict(stats)


def quality(source, result):
    target = result.get("translation")
    reasons = []
    if not isinstance(target,str) or not target.strip():
        return ["empty_translation"]
    if result.get("status") != "candidate" or result.get("finish_reason") != "eos":
        reasons.append("incomplete_or_uncertain")
    if source.strip().casefold() == target.strip().casefold():
        reasons.append("unchanged_source")
    if Counter(NUMBERS.findall(source)) != Counter(NUMBERS.findall(target)):
        reasons.append("numeric_mismatch")
    if not 0.15 <= len(target)/len(source) <= 4:
        reasons.append("length_ratio")
    if "<think>" in target.lower() or "</think>" in target.lower():
        reasons.append("reasoning_markup")
    return reasons


class CorpusStore:
    def __init__(self, db_path):
        self.path = Path(db_path)
        self.path.parent.mkdir(parents=True,exist_ok=True)
        with closing(self.connect()) as db, db:
            db.execute("""CREATE TABLE IF NOT EXISTS corpus_segments (
                id TEXT PRIMARY KEY, pmcid TEXT NOT NULL, record TEXT NOT NULL)""")
            db.execute("""CREATE TABLE IF NOT EXISTS corpus_pairs (
                id TEXT PRIMARY KEY, segment_id TEXT NOT NULL, record TEXT NOT NULL,
                FOREIGN KEY(segment_id) REFERENCES corpus_segments(id) ON DELETE CASCADE)""")
            db.execute("""CREATE TABLE IF NOT EXISTS corpus_extractions (
                pmcid TEXT PRIMARY KEY, record TEXT NOT NULL)""")

    def connect(self):
        db = sqlite3.connect(self.path,timeout=10)
        db.execute("PRAGMA foreign_keys=ON")
        return db

    def parse(self, root, *, limit=20, max_chars=1200):
        if type(limit) is not int or not 1 <= limit <= 50:
            raise ValueError("limit must be 1–50")
        root = Path(root).resolve()
        stats = Counter(papers=0,segments=0,blocked=0,cached=0)
        with closing(self.connect()) as db, db:
            # Each extraction atomically replaces its own previous version.
            records = db.execute("""SELECT f.record,p.record FROM paper_fulltexts f
                JOIN papers p ON f.pmcid=p.pmcid ORDER BY f.pmcid LIMIT ?""",(limit,)).fetchall()
            for raw_record, raw_catalog in records:
                record,catalog = json.loads(raw_record),json.loads(raw_catalog)
                pmcid = record["pmcid"]
                stats["papers"] += 1
                previous = db.execute("SELECT record FROM corpus_extractions WHERE pmcid=?",(pmcid,)).fetchone()
                try:
                    path = root/(pmcid_value(pmcid)+".xml")
                    if (path.is_symlink() or str(path)!=record.get("path")
                            or path.stat().st_size>MAX_FILE):
                        raise Blocked("invalid fulltext path or size")
                    with path.open("rb") as stream:
                        raw = stream.read(MAX_FILE+1)
                    rows, detail = extract(raw,record,catalog,max_chars=max_chars)
                    signature = digest(json.dumps(rows,sort_keys=True).encode())
                    status = {"pmcid":pmcid,"status":"parsed_candidates","signature":signature,
                              "stats":detail,"max_chars":max_chars}
                    if previous and json.loads(previous[0]).get("signature")==signature:
                        stats["cached"] += 1
                        stats["segments"] += len(rows)
                        continue
                except (Blocked,OSError,KeyError,ValueError) as exc:
                    rows = []
                    status = {"pmcid":pmcid,"status":"blocked","reason":type(exc).__name__}
                    stats["blocked"] += 1
                db.execute("DELETE FROM corpus_segments WHERE pmcid=?",(pmcid,))
                db.executemany("INSERT INTO corpus_segments VALUES (?,?,?)",
                               [(r["segment_id"],pmcid,json.dumps(r)) for r in rows])
                db.execute("INSERT OR REPLACE INTO corpus_extractions VALUES (?,?)",
                           (pmcid,json.dumps(status)))
                stats["segments"] += len(rows)
        return dict(stats)

    def list_segments(self, limit=100):
        if type(limit) is not int or not 1 <= limit <= 1024:
            raise ValueError("limit must be 1–1024")
        with closing(self.connect()) as db:
            return [json.loads(r[0]) for r in db.execute(
                "SELECT record FROM corpus_segments ORDER BY pmcid,id LIMIT ?",(limit,))]

    def translate(self, translator, *, limit=100):
        from dataclasses import asdict
        if type(limit) is not int or not 1 <= limit <= 1024:
            raise ValueError("limit must be 1–1024")
        options = asdict(translator.options)
        teacher = {"source":translator.record.get("source","huggingface"),
                   "model_id":translator.record["model_id"],"revision":translator.record["revision"]}
        key = json.dumps([teacher,options,PROMPT_VERSION,POLICY_VERSION],sort_keys=True)
        stats = Counter(generated=0,cached=0,screened=0,rejected=0,failed=0)
        # Read bounded pending work, preserve already completed candidates.
        # Explicitly finalize the streaming SELECT before opening write transactions.
        # sqlite3.Connection.close() alone may leave an unfinished cursor holding
        # a read lock when the bounded loop exits early.
        pending = []
        with closing(self.connect()) as db:
            with closing(db.execute("""SELECT s.record FROM corpus_segments s
                JOIN papers p ON p.pmcid=s.pmcid JOIN paper_fulltexts f ON f.pmcid=s.pmcid
                WHERE json_extract(p.record,'$.eligibility')='pending_fulltext_license'
                AND json_extract(f.record,'$.status')='downloaded_pending_content_review'
                AND json_extract(f.record,'$.sha256')=json_extract(s.record,'$.attribution.xml_sha256')
                ORDER BY row_number() OVER (PARTITION BY s.pmcid ORDER BY s.id),s.pmcid,s.id""")) as rows:
                for row in rows:
                    segment = json.loads(row[0])
                    pid = digest((segment["segment_id"]+key).encode())
                    with closing(db.execute("SELECT 1 FROM corpus_pairs WHERE id=?",(pid,))) as existing:
                        cached = existing.fetchone() is not None
                    if cached:
                        stats["cached"] += 1
                        continue
                    pending.append((pid,segment))
                    if len(pending)>=limit:
                        break
        for offset in range(0,len(pending),translator.options.batch_size):
            batch = pending[offset:offset+translator.options.batch_size]
            try:
                outputs = translator.translate([s["source_text"] for _,s in batch])
                if len(outputs)!=len(batch):
                    raise ValueError("teacher output count mismatch")
                for (_,s),r in zip(batch,outputs):
                    if r.get("source_text")!=s["source_text"] or r.get("teacher")!=teacher or r.get("options")!=options or r.get("prompt_version")!=PROMPT_VERSION:
                        raise ValueError("teacher provenance mismatch")
            except (ValueError,RuntimeError,OSError):
                stats["failed"] += len(batch)
                continue
            with closing(self.connect()) as db, db:
                for (pid,s),r in zip(batch,outputs):
                    reasons = quality(s["source_text"],r)
                    record = s | {"pair_id":pid,"teacher":teacher,"options":options,
                                  "prompt_version":PROMPT_VERSION,"policy_version":POLICY_VERSION,
                                  "translation":r["translation"],"finish_reason":r["finish_reason"],
                                  "quality_flags":reasons,
                                  "status":"rejected" if reasons else "screened_candidate"}
                    db.execute("INSERT OR IGNORE INTO corpus_pairs VALUES (?,?,?)",
                               (pid,s["segment_id"],json.dumps(record)))
                    stats["generated"] += 1
                    stats["rejected" if reasons else "screened"] += 1
        return dict(stats)

    def export_candidates(self, destination, *, limit=10000):
        if type(limit) is not int or not 1 <= limit <= 100000:
            raise ValueError("limit must be 1–100000")
        destination = Path(destination).resolve()
        if destination==self.path.resolve() or destination.exists():
            raise ValueError("export requires a new destination file")
        destination.parent.mkdir(parents=True,exist_ok=True)
        tmp = None
        count = 0
        seen = set()
        try:
            with tempfile.NamedTemporaryFile(mode="w",encoding="utf-8",newline="\n",
                    dir=destination.parent,delete=False) as out, closing(self.connect()) as db:
                tmp = Path(out.name)
                for row in db.execute("""SELECT c.record FROM corpus_pairs c
                    JOIN corpus_segments s ON s.id=c.segment_id
                    JOIN papers p ON p.pmcid=s.pmcid JOIN paper_fulltexts f ON f.pmcid=s.pmcid
                    WHERE json_extract(p.record,'$.eligibility')='pending_fulltext_license'
                    AND json_extract(f.record,'$.status')='downloaded_pending_content_review'
                    AND json_extract(f.record,'$.sha256')=json_extract(s.record,'$.attribution.xml_sha256')
                    AND json_extract(c.record,'$.status')='screened_candidate'
                    ORDER BY s.pmcid,c.id"""):
                    record = json.loads(row[0])
                    # Exact cross-paper duplicate text occurs in only one split.
                    if record["source_sha256"] in seen:
                        continue
                    seen.add(record["source_sha256"])
                    out.write(json.dumps(record,ensure_ascii=False)+"\n")
                    count += 1
                    if count>=limit:
                        break
            # Hardlink creation is atomic and refuses an existing destination.
            import os
            os.link(tmp,destination)
        finally:
            if tmp:
                tmp.unlink(missing_ok=True)
        return {"path":str(destination),"count":count,"training_ready":False}
