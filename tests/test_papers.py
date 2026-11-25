import tempfile
from pathlib import Path
import unittest
from unittest.mock import Mock

from rpdistill.papers import PaperQuery, PaperCatalog, paper_from_record, license_code, normalize_doi, discover


def row(**kw):
    return dict(source="MED", id="123", title="Scientific article",
                doi="https://doi.org/10.1234/AbC", pmcid="PMC123",
                firstPublicationDate="2025-04-01", isOpenAccess="Y", license="cc by") | kw


class PaperTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.db = Path(tmp.name)/"papers.db"
        self.catalog = PaperCatalog(self.db)
        self.query = PaperQuery(("battery", "electrolyte"), "2025-01-01", "2025-12-31",
                                subject="materials", limit=3)

    def test_query(self):
        q = self.query.expression()
        self.assertIn('("battery" OR "electrolyte")', q)
        self.assertIn('"materials"', q)
        self.assertIn("FIRST_PDATE:[2025-01-01 TO 2025-12-31]", q)
        self.assertIn("LANG:eng", q)
        self.assertIn("OPEN_ACCESS:Y", q)

    def test_invalid_queries(self):
        for kw in (dict(keywords=('bad" OR x',)), dict(limit=0), dict(start_date="2026-01-01"),
                   dict(language="en OR x"), dict(end_date="2025-02-30")):
            with self.assertRaises(ValueError):
                PaperQuery(**(dict(keywords=("x",), start_date="2025-01-01", end_date="2025-12-31") | kw))

    def test_license_allowlist(self):
        for value in ("cc by", "CC-BY 4.0", "https://creativecommons.org/licenses/by/4.0/"):
            self.assertEqual(license_code(value), "cc-by")
        self.assertEqual(license_code("CC0 1.0"), "cc0")
        for value in (None, "cc by nc", "cc-by-nd", "cc-by-sa", "open access", "other"):
            self.assertIsNone(license_code(value))

    def test_metadata_not_training_authorization(self):
        self.assertEqual(paper_from_record(row()).eligibility, "pending_fulltext_license")
        for kw in (dict(isOpenAccess="N"), dict(pmcid=None), dict(license=None), dict(license="cc by nc")):
            self.assertEqual(paper_from_record(row(**kw)).eligibility, "blocked_metadata")
        self.assertNotIn("abstractText", paper_from_record(row(abstractText="private")).__dict__)

    def test_doi_normalization(self):
        self.assertEqual(normalize_doi("https://doi.org/10.1234/AbC"), "10.1234/abc")
        self.assertIsNone(normalize_doi("https://example.org/abc"))

    def test_persistent_alias_dedup(self):
        self.assertEqual(self.catalog.ingest(paper_from_record(row())), "inserted")
        self.assertEqual(self.catalog.ingest(paper_from_record(row(source="PMC", id="456", doi=None))), "duplicate")
        self.assertEqual(len(PaperCatalog(self.db).list()), 1)

    def test_conflicting_ids_and_license(self):
        self.catalog.ingest(paper_from_record(row()))
        self.assertEqual(self.catalog.ingest(paper_from_record(row(doi="10.1234/other"))), "conflict")
        self.assertEqual(self.catalog.ingest(paper_from_record(row(license="cc by nc"))), "duplicate")
        self.assertEqual(self.catalog.list()[0]["eligibility"], "blocked_metadata")

    def test_bounded_pagination(self):
        fetch = Mock(side_effect=[
            {"resultList":{"result":[row(), row(id="456", source="PMC")]}, "nextCursorMark":"next"},
            {"resultList":{"result":[row(id="789", doi="10.1234/other", pmcid="PMC789")]},
             "nextCursorMark":"next2"}])
        sleep = Mock()
        stats = discover(self.query, self.catalog, fetch=fetch, sleep=sleep)
        self.assertEqual(stats["inspected"], 3)
        self.assertEqual(stats["inserted"], 2)
        self.assertEqual(stats["duplicate"], 1)
        self.assertEqual(fetch.call_args_list[1].args[0]["cursorMark"], "next")
        sleep.assert_called_once_with(1)

    def test_cursor_loop_and_out_of_range(self):
        fetch = Mock(return_value={"resultList":{"result":[row(firstPublicationDate="2024-01-01")]},
                                  "nextCursorMark":"*"})
        stats = discover(self.query, self.catalog, fetch=fetch, sleep=Mock())
        self.assertEqual(stats["invalid"], 1)
        self.assertEqual(stats["pages"], 1)
        self.assertEqual(self.catalog.list(), [])


class NetworkRetryTests(unittest.TestCase):
    def error(self, status, retry_after=None):
        from urllib.error import HTTPError
        from email.message import Message
        headers = Message()
        if retry_after is not None:
            headers["Retry-After"] = retry_after
        return HTTPError("https://example.invalid", status, "test", headers, None)

    def test_transient_503_then_success(self):
        from io import BytesIO
        from rpdistill.papers import fetch_page
        opener = Mock(side_effect=[self.error(503), BytesIO(b'{"resultList":{}}')])
        sleep = Mock()
        self.assertEqual(fetch_page({}, opener=opener, sleep=sleep), {"resultList":{}})
        self.assertEqual(opener.call_count, 2)
        sleep.assert_called_once_with(2)

    def test_rate_limit_retry_after(self):
        from io import BytesIO
        from rpdistill.papers import fetch_page
        opener = Mock(side_effect=[self.error(429, "5"), BytesIO(b'{}')])
        sleep = Mock()
        self.assertEqual(fetch_page({}, opener=opener, sleep=sleep), {})
        sleep.assert_called_once_with(5)

    def test_permanent_error_no_retry(self):
        from urllib.error import HTTPError
        from rpdistill.papers import fetch_page
        opener = Mock(side_effect=self.error(400))
        sleep = Mock()
        with self.assertRaises(HTTPError):
            fetch_page({}, opener=opener, sleep=sleep)
        opener.assert_called_once()
        sleep.assert_not_called()

    def test_exhausted_retries_propagate(self):
        from urllib.error import HTTPError
        from rpdistill.papers import fetch_page
        opener = Mock(side_effect=[self.error(503) for _ in range(4)])
        sleep = Mock()
        with self.assertRaises(HTTPError):
            fetch_page({}, opener=opener, sleep=sleep)
        self.assertEqual(opener.call_count, 4)
        self.assertEqual([x.args[0] for x in sleep.call_args_list], [2,4,8])

    def test_long_retry_after_stops(self):
        from urllib.error import HTTPError
        from rpdistill.papers import fetch_page
        opener = Mock(side_effect=self.error(429, "120"))
        sleep = Mock()
        with self.assertRaises(HTTPError):
            fetch_page({}, opener=opener, sleep=sleep)
        opener.assert_called_once()
        sleep.assert_not_called()
