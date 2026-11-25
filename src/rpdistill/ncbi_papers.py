"""NCBI PMC E-utilities discovery fallback; no full-text or training authorization."""
from datetime import datetime, timezone
import re
import ssl
import time
from urllib.error import HTTPError, URLError

from .papers import Paper, PaperQuery, discover, fetch_page, normalize_doi, phrase

BASE = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/"
TRANSIENT = (408, 429, 500, 502, 503, 504)


def expression(query):
    terms = ["(" + " OR ".join(phrase(x) for x in query.keywords) + ")"]
    if query.subject:
        terms.append(phrase(query.subject))
    terms.append(query.start_date.replace("-", "/") + ":" +
                 query.end_date.replace("-", "/") + "[dp]")
    if query.language:
        terms.append(query.language + "[la]")
    if query.open_access_only:
        terms.append('"open access"[filter]')
        terms.append('("cc by license"[filter] OR "cc0 license"[filter])')
    return " AND ".join(terms)


def request(kind, params):
    if kind not in ("esearch", "esummary"):
        raise ValueError("unsupported NCBI operation")
    return fetch_page({"db":"pmc", "retmode":"json", "tool":"rpdistill", **params},
                      endpoint=BASE + kind + ".fcgi")


def paper_from_summary(row, uid, query):
    if not isinstance(row, dict) or row.get("uid") != uid:
        raise ValueError("NCBI summary identity mismatch")
    title = row.get("title")
    if not isinstance(title, str) or not title.strip() or len(title) > 10000:
        raise ValueError("invalid NCBI title")
    ids = {}
    for item in row.get("articleids", []):
        if isinstance(item, dict) and isinstance(item.get("idtype"), str):
            key = item["idtype"]
            if key in ids and ids[key] != item.get("value"):
                raise ValueError("conflicting article identifiers")
            ids[key] = item.get("value")
    pmcid = "PMC" + uid
    if ids.get("pmcid") != pmcid:
        raise ValueError("NCBI PMCID mismatch")
    pubdate = None
    for value in (row.get("epubdate"), row.get("pubdate")):
        if isinstance(value, str) and re.fullmatch(r"[0-9]{4} [A-Za-z]{3} [0-9]{1,2}", value):
            try:
                pubdate = datetime.strptime(value, "%Y %b %d").date().isoformat()
                break
            except ValueError:
                continue
    # ESearch filters publication date; exact day may be absent in ESummary.
    # The combined license filter is only a hint: never invent an exact license.
    oa = query.open_access_only
    authors = "; ".join(a["name"] for a in row.get("authors", [])
                        if isinstance(a, dict) and isinstance(a.get("name"), str))
    journal = row.get("fulljournalname") or row.get("source") or ""
    return Paper("NCBI-PMC:" + uid, title.strip(), normalize_doi(ids.get("doi")),
                 pmcid, pubdate, str(journal)[:10000], authors[:10000],
                 "NCBI OA CC BY/CC0 query filter (unverified)" if oa else None,
                 None, oa, "pending_fulltext_license" if oa else "blocked_metadata",
                 datetime.now(timezone.utc).isoformat())


def discover_ncbi(query, catalog, *, fetch=request, sleep=time.sleep):
    if not isinstance(query, PaperQuery):
        raise ValueError("expected PaperQuery")
    payload = fetch("esearch", {"term":expression(query), "retmax":query.limit,
                                 "retstart":0})
    result = payload.get("esearchresult")
    if (not isinstance(result, dict) or result.get("ERROR") or result.get("errorlist")
            or not isinstance(result.get("idlist"), list)):
        raise ValueError("invalid NCBI search response")
    ids = result["idlist"][:query.limit]
    if any(not isinstance(x, str) or not re.fullmatch(r"[0-9]{1,15}", x) for x in ids):
        raise ValueError("invalid NCBI identifier")
    if len(set(ids)) != len(ids):
        raise ValueError("duplicate NCBI search identifiers")
    stats = dict(inspected=0, inserted=0, duplicate=0, conflict=0, invalid=0, pages=1)
    for start in range(0, len(ids), 50):
        sleep(1)
        batch = ids[start:start+50]
        payload = fetch("esummary", {"id":",".join(batch)})
        result = payload.get("result")
        if not isinstance(result, dict) or not isinstance(result.get("uids"), list):
            raise ValueError("invalid NCBI summary response")
        stats["pages"] += 1
        for uid in batch:
            stats["inspected"] += 1
            try:
                paper = paper_from_summary(result.get(uid), uid, query)
                stats[catalog.ingest(paper)] += 1
            except (ValueError, TypeError):
                stats["invalid"] += 1
    return stats


def transient(exc):
    if isinstance(exc, HTTPError):
        return exc.code in TRANSIENT
    if isinstance(exc, URLError):
        return not isinstance(exc.reason, ssl.SSLError)
    return isinstance(exc, (TimeoutError, ConnectionError))


def discover_with_source(query, catalog, *, source="auto", epmc_fetch=fetch_page,
                         ncbi_fetch=request, sleep=time.sleep):
    if source not in ("auto", "europe-pmc", "ncbi-pmc"):
        raise ValueError("unknown paper source")
    if source == "ncbi-pmc":
        return discover_ncbi(query, catalog, fetch=ncbi_fetch, sleep=sleep) | {
            "provider":"ncbi-pmc", "fallback_from":None}
    successful_pages = 0

    def tracked(params):
        nonlocal successful_pages
        result = epmc_fetch(params)
        successful_pages += 1
        return result

    try:
        return discover(query, catalog, fetch=tracked, sleep=sleep) | {
            "provider":"europe-pmc", "fallback_from":None}
    except (HTTPError, URLError, TimeoutError, ConnectionError) as exc:
        # Do not reset the record budget after a partially successful search.
        # Respect a long Retry-After by stopping this provider, not retrying it.
        if source != "auto" or successful_pages or not transient(exc):
            raise
        error = "HTTP " + str(exc.code) if isinstance(exc, HTTPError) else type(exc).__name__
        return discover_ncbi(query, catalog, fetch=ncbi_fetch, sleep=sleep) | {
            "provider":"ncbi-pmc", "fallback_from":"europe-pmc", "fallback_reason":error}
