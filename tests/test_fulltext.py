import hashlib
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock
from io import BytesIO

from rpdistill.papers import PaperCatalog, paper_from_record
from rpdistill.fulltext import FulltextLibrary, inspect_record, fetch_record, Budget, Blocked, BudgetExceeded


def xml(pmcid="PMC123", license="https://creativecommons.org/licenses/by/4.0/", body=True,
        stamp="2025-01-01", doi="10.1234/test"):
    return (f'<OAI-PMH xmlns="http://www.openarchives.org/OAI/2.0/"><GetRecord><record>'
            f'<header><identifier>oai:pubmedcentral.nih.gov:{pmcid[3:]}</identifier>'
            f'<datestamp>{stamp}</datestamp></header><metadata><article xmlns="">'
            f'<front><article-meta><article-id pub-id-type="pmc">{pmcid[3:]}</article-id>'
            f'<article-id pub-id-type="doi">{doi}</article-id>'
            f'<permissions><license xmlns:xlink="http://www.w3.org/1999/xlink" xlink:href="{license}">'
            f'<license-p>Open license</license-p></license></permissions></article-meta></front>'
            + ('<body><p>Example</p></body>' if body else '') +
            '</article></metadata></record></GetRecord></OAI-PMH>').encode()


class FulltextTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        root = Path(tmp.name)
        self.catalog = PaperCatalog(root/"db")
        self.catalog.ingest(paper_from_record(dict(source="MED", id="123", title="test",
            doi="10.1234/test", pmcid="PMC123", isOpenAccess="Y", license="cc by")))
        self.lib = FulltextLibrary(root/"db", root/"xml")

    def fetch(self, records):
        it = iter(records)
        def run(pmcid, prefix, budget):
            raw = next(it)
            budget.consume(len(raw))
            return raw
        return Mock(side_effect=run)

    def download(self, fetch, budget=100000):
        return self.lib.download(self.catalog.list(), max_bytes=budget,
                                 fetch=fetch, sleep=Mock())

    def test_license_and_identity(self):
        result = inspect_record(xml(), "PMC123", full=True, expected_doi="10.1234/test")
        self.assertEqual(result["license"], "cc-by")
        for raw in (xml(pmcid="PMC999"), xml(license="https://creativecommons.org/licenses/by-nc/4.0/"),
                    xml(body=False), xml(doi="10.1234/wrong"), b'<!DOCTYPE x><x/>'):
            with self.assertRaises(Blocked):
                inspect_record(raw, "PMC123", full=True, expected_doi="10.1234/test")

    def test_download_hash_and_cache(self):
        raw = xml()
        fetch = self.fetch([xml(body=False), raw])
        stats = self.download(fetch)
        self.assertEqual(stats["saved"], 1)
        rec = self.lib.list()[0]
        self.assertEqual(rec["sha256"], hashlib.sha256(raw).hexdigest())
        self.assertEqual(rec["status"], "downloaded_pending_content_review")
        self.assertEqual(Path(rec["path"]).read_bytes(), raw)
        self.assertEqual(self.download(Mock())["cached"], 1)

    def test_restricted_metadata_no_fulltext(self):
        fetch = self.fetch([xml(license="https://creativecommons.org/licenses/by-nd/4.0/")])
        self.assertEqual(self.download(fetch)["blocked"], 1)
        fetch.assert_called_once()
        self.assertFalse(self.lib.path_for("PMC123").exists())

    def test_license_change_rejected(self):
        fetch = self.fetch([xml(), xml(license="https://creativecommons.org/publicdomain/zero/1.0/")])
        self.assertEqual(self.download(fetch)["blocked"], 1)
        self.assertFalse(self.lib.path_for("PMC123").exists())

    def test_revision_change_rejected(self):
        self.assertEqual(self.download(self.fetch([xml(),xml(stamp="2025-01-02")]))["blocked"],1)

    def test_budget_exhaustion(self):
        self.assertTrue(self.download(self.fetch([xml()]), budget=10)["budget_exhausted"])
        self.assertFalse(self.lib.path_for("PMC123").exists())

    def test_network_byte_cap(self):
        with self.assertRaises(BudgetExceeded):
            fetch_record("PMC123","pmc_fm",Budget(5),opener=Mock(return_value=BytesIO(b"123456")),
                         sleep=Mock())

    def test_cached_file_corruption_refetch(self):
        self.download(self.fetch([xml(),xml()]))
        self.lib.path_for("PMC123").write_bytes(b"corrupt")
        self.assertEqual(self.download(self.fetch([xml(),xml()]))["saved"],1)

    def test_repeated_publisher_ids_not_identity_conflict(self):
        raw = xml().replace(b'<permissions>', b'<article-id pub-id-type="publisher-id" assigning-authority="a">1</article-id><article-id pub-id-type="publisher-id" assigning-authority="b">2</article-id><permissions>')
        self.assertEqual(inspect_record(raw,"PMC123",full=True)["license"],"cc-by")

    def test_duplicate_normalized_doi_and_pmc(self):
        raw = xml().replace(b'<permissions>', b'<article-id pub-id-type="pmcid">PMC123</article-id><article-id pub-id-type="doi">https://doi.org/10.1234/TEST</article-id><permissions>')
        self.assertEqual(inspect_record(raw,"PMC123",full=True)["doi"],"10.1234/test")
        with self.assertRaises(Blocked):
            inspect_record(raw.replace(b'10.1234/TEST',b'10.1234/other'),"PMC123",full=True)

    def test_nested_license_uri(self):
        raw = xml().replace(b' xlink:href="https://creativecommons.org/licenses/by/4.0/"',b'').replace(b'Open license',b'<ext-link ext-link-type="uri" xlink:href="http://creativecommons.org/licenses/by/4.0">CC BY</ext-link>')
        self.assertEqual(inspect_record(raw,"PMC123",full=True)["license_uri"],
                         "https://creativecommons.org/licenses/by/4.0/")

    def test_nested_conflicting_or_restricted_license(self):
        raw = xml().replace(b'Open license',b'<ext-link xlink:href="https://creativecommons.org/licenses/by-nc/4.0/">Restricted</ext-link>')
        with self.assertRaises(Blocked):
            inspect_record(raw,"PMC123",full=True)
        raw = xml().replace(b' xlink:href="https://creativecommons.org/licenses/by/4.0/"',b'')
        with self.assertRaises(Blocked):
            inspect_record(raw,"PMC123",full=True)
