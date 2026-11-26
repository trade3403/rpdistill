from dataclasses import asdict
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock

from rpdistill.corpus import CorpusStore, extract, quality, stable_split
from rpdistill.fulltext import FulltextLibrary, Blocked
from rpdistill.inference import TeacherTranslator, TranslationOptions
from rpdistill.papers import PaperCatalog, paper_from_record
from test_fulltext import xml

PROSE = "The sample was heated to 300 K under controlled laboratory conditions."


class CorpusTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        self.db = self.root/"db"
        self.catalog = PaperCatalog(self.db)
        self.catalog.ingest(paper_from_record(dict(source="MED",id="123",title="Article",
            authorString="Example Author",doi="10.1234/test",pmcid="PMC123",
            isOpenAccess="Y",license="cc by")))
        self.library = FulltextLibrary(self.db,self.root/"xml")
        self.raw = xml().replace(b"<p>Example</p>",("<p>"+PROSE+"</p>").encode())
        self.register(self.raw)
        self.store = CorpusStore(self.db)

    def register(self, raw):
        self.library.path_for("PMC123").write_bytes(raw)
        import sqlite3
        from contextlib import closing
        with closing(sqlite3.connect(self.db)) as db,db:
            self.library.save(db,dict(pmcid="PMC123",doi="10.1234/test",
                status="downloaded_pending_content_review",path=str(self.library.path_for("PMC123")),
                size=len(raw),sha256=hashlib.sha256(raw).hexdigest(),
                license_uri="https://creativecommons.org/licenses/by/4.0/",datestamp="2025-01-01"))

    def translator(self, translation="样品在受控实验室条件下加热至300 K。"):
        backend=Mock()
        backend.generate.side_effect=lambda messages,options:[
            dict(translation=translation,finish_reason="eos",generated_tokens=10) for _ in messages]
        return TeacherTranslator(dict(model_id="test/model",revision="a"*40),
                                 TranslationOptions(),backend=backend)

    def test_extract_and_idempotence(self):
        self.assertEqual(self.store.parse(self.library.root)["segments"],1)
        row=self.store.list_segments()[0]
        self.assertEqual(row["source_text"],PROSE)
        self.assertEqual(row["attribution"]["authors"],"Example Author")
        self.assertEqual(row["split"],stable_split("PMC123"))
        self.assertEqual(self.store.parse(self.library.root)["cached"],1)

    def test_unsafe_markup_and_rights_excluded(self):
        raw=self.raw.replace(b"</body>",b"<p>Reproduced with permission from another publisher and not available here.</p><p>This formula <inline-formula>x</inline-formula> is not supported by this parser.</p><fig><p>External figure caption is not prose for this scientific translation.</p></fig></body>")
        self.register(raw)
        self.assertEqual(self.store.parse(self.library.root)["segments"],1)

    def test_tamper_invalidates_cached_segments(self):
        self.store.parse(self.library.root)
        self.library.path_for("PMC123").write_bytes(b"bad")
        self.assertEqual(self.store.parse(self.library.root)["blocked"],1)
        self.assertEqual(self.store.list_segments(),[])

    def test_translation_persistence_and_export(self):
        self.store.parse(self.library.root)
        translator=self.translator()
        self.assertEqual(self.store.translate(translator)["screened"],1)
        self.assertEqual(self.store.translate(translator)["cached"],1)
        path=self.root/"candidates.jsonl"
        result=self.store.export_candidates(path)
        self.assertFalse(result["training_ready"])
        row=json.loads(path.read_text(encoding="utf-8"))
        self.assertEqual(row["source_text"],PROSE)
        self.assertEqual(row["status"],"screened_candidate")
        with self.assertRaises(ValueError):
            self.store.export_candidates(path)

    def test_numeric_mismatch_rejected(self):
        self.store.parse(self.library.root)
        self.assertEqual(self.store.translate(self.translator("样品在受控实验室条件下加热至400 K。"))["rejected"],1)
        self.assertEqual(self.store.export_candidates(self.root/"bad.jsonl")["count"],0)

    def test_metadata_revocation_excludes_export(self):
        self.store.parse(self.library.root)
        self.store.translate(self.translator())
        self.catalog.ingest(paper_from_record(dict(source="MED",id="123",title="Article",
            doi="10.1234/test",pmcid="PMC123",isOpenAccess="Y",license="cc by nc")))
        self.assertEqual(self.store.export_candidates(self.root/"blocked.jsonl")["count"],0)
        self.assertEqual(self.store.parse(self.library.root)["blocked"],1)

    def test_long_sentence_not_truncated(self):
        self.register(self.raw.replace(PROSE.encode(),("word "*100+"end.").encode()))
        self.assertEqual(self.store.parse(self.library.root,max_chars=128)["segments"],0)

    def test_paper_split_stable(self):
        self.assertEqual(stable_split("PMC123"),stable_split("PMC123"))
        self.assertIn(stable_split("PMC123"),("train","validation","test"))

    def test_bounded_translation_spreads_across_papers(self):
        # An earlier paper with multiple segments must not consume the whole budget.
        raw=self.raw.replace(b"</body>",b"<p>A second independent laboratory observation was recorded with a calibrated instrument.</p></body>")
        self.register(raw)
        doi="10.1234/second"
        self.catalog.ingest(paper_from_record(dict(source="MED",id="999",title="Second article",
            authorString="Example Author",doi=doi,pmcid="PMC999",isOpenAccess="Y",license="cc by")))
        other=xml(pmcid="PMC999",doi=doi).replace(b"<p>Example</p>",b"<p>A different experimental observation was recorded using a calibrated instrument.</p>")
        import sqlite3
        from contextlib import closing
        dest=self.library.path_for("PMC999")
        dest.write_bytes(other)
        with closing(sqlite3.connect(self.db)) as db,db:
            self.library.save(db,dict(pmcid="PMC999",doi=doi,status="downloaded_pending_content_review",
                path=str(dest),size=len(other),sha256=hashlib.sha256(other).hexdigest(),
                license_uri="https://creativecommons.org/licenses/by/4.0/",datestamp="2025-01-01"))
        self.assertEqual(self.store.parse(self.library.root)["segments"],3)
        stats=self.store.translate(self.translator(),limit=2)
        self.assertEqual(stats["generated"],2)
        with closing(self.store.connect()) as db:
            papers={json.loads(row[0])["pmcid"] for row in db.execute("SELECT record FROM corpus_pairs")}
        self.assertEqual(papers,{"PMC123","PMC999"})
