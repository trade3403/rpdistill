from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock
from urllib.error import HTTPError

from rpdistill.papers import PaperCatalog, PaperQuery
from rpdistill.ncbi_papers import expression, discover_ncbi, discover_with_source


def summary(uid="123", **changes):
    return dict(uid=uid, title="Article", epubdate="2025 Apr 01",
                articleids=[{"idtype":"pmcid","value":"PMC"+uid},
                            {"idtype":"doi","value":"10.1234/abc"}],
                authors=[{"name":"Example A"}], fulljournalname="Journal") | changes


def results():
    return [{"esearchresult":{"idlist":["123"]}},
            {"result":{"uids":["123"],"123":summary()}}]


class NCBITests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.catalog = PaperCatalog(Path(tmp.name)/"db")
        self.query = PaperQuery(("battery",), "2025-01-01", "2025-12-31", limit=3)

    def test_query_filters(self):
        expr = expression(self.query)
        self.assertIn('2025/01/01:2025/12/31[dp]', expr)
        self.assertIn('eng[la]', expr)
        self.assertIn('"cc by license"[filter]', expr)
        self.assertIn('"cc0 license"[filter]', expr)

    def test_discovery_and_license_not_certified(self):
        fetch = Mock(side_effect=results())
        stats = discover_ncbi(self.query, self.catalog, fetch=fetch, sleep=Mock())
        self.assertEqual(stats["inserted"], 1)
        row = self.catalog.list()[0]
        self.assertEqual(row["pmcid"], "PMC123")
        self.assertEqual(row["eligibility"], "pending_fulltext_license")
        self.assertIsNone(row["license_hint"])
        self.assertEqual(row["provider_id"], "NCBI-PMC:123")

    def test_503_fallback(self):
        error = HTTPError("https://example.invalid", 503, "unavailable", {}, None)
        fetch = Mock(side_effect=error)
        result = discover_with_source(self.query, self.catalog, epmc_fetch=fetch,
                                      ncbi_fetch=Mock(side_effect=results()), sleep=Mock())
        self.assertEqual(result["provider"], "ncbi-pmc")
        self.assertEqual(result["fallback_reason"], "HTTP 503")

    def test_permanent_error_does_not_fallback(self):
        error = HTTPError("https://example.invalid", 400, "bad request", {}, None)
        ncbi = Mock()
        with self.assertRaises(HTTPError):
            discover_with_source(self.query, self.catalog, epmc_fetch=Mock(side_effect=error),
                                 ncbi_fetch=ncbi, sleep=Mock())
        ncbi.assert_not_called()

    def test_partial_search_does_not_reset_budget(self):
        error = HTTPError("https://example.invalid", 503, "unavailable", {}, None)
        first = {"resultList":{"result":[{"source":"MED","id":"1","title":"x"}]},
                 "nextCursorMark":"next"}
        ncbi = Mock()
        with self.assertRaises(HTTPError):
            discover_with_source(self.query, self.catalog,
                epmc_fetch=Mock(side_effect=[first,error]), ncbi_fetch=ncbi, sleep=Mock())
        ncbi.assert_not_called()
        self.assertEqual(len(self.catalog.list()), 1)

    def test_bad_identity_rejected(self):
        payload = results()
        payload[1]["result"]["123"]["uid"] = "999"
        stats = discover_ncbi(self.query, self.catalog, fetch=Mock(side_effect=payload), sleep=Mock())
        self.assertEqual(stats["invalid"], 1)
        self.assertEqual(self.catalog.list(), [])

    def test_invalid_search_error(self):
        with self.assertRaises(ValueError):
            discover_ncbi(self.query, self.catalog, fetch=Mock(return_value={
                "esearchresult":{"idlist":["123"],"errorlist":{"fieldsnotfound":["x"]}}}),
                sleep=Mock())
