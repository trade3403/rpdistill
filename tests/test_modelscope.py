import hashlib
from pathlib import Path
from types import SimpleNamespace as NS
import tempfile
import unittest
from unittest.mock import Mock

from rpdistill.modelscope_source import search_models, revisions, download_modelscope
from rpdistill.teachers import TeacherRegistry
from rpdistill.downloads import DownloadQueue
from test_teachers import MODEL, REV, PAYLOAD


class ModelScopeTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        self.api = Mock()
        self.api.get_model.return_value = dict(id=MODEL, visibility="public",
                                               license="apache-2.0", gated=False)
        self.api.list_repo_files.return_value = [
            NS(path=name, size=len(data), sha256=hashlib.sha256(data).hexdigest(),
               is_dir=False) for name, data in PAYLOAD.items()]
        self.api.download_file.side_effect = self.download
        self.registry = TeacherRegistry(self.root / "db", source="modelscope")

    def download(self, name, kind, filename, **kwargs):
        path = kwargs["local_dir"] / filename
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(PAYLOAD[filename])
        return path

    def fetch(self, **changes):
        args = dict(reviewed_license="apache-2.0", max_bytes=1024,
                    cache_dir=self.root / "cache", registry=self.registry, api=self.api)
        return download_modelscope(MODEL, REV, **(args | changes))

    def test_search(self):
        self.api.list_repos.return_value = NS(items=[NS(repo_id=MODEL, license="apache-2.0")])
        row = search_models("Qwen", 5, api=self.api)[0]
        self.assertEqual(row["source"], "modelscope")
        self.assertIsNone(row["revision"])
        self.api.list_repos.assert_called_once_with("model", search="Qwen", page_size=5)

    def test_revisions(self):
        self.api.list_repo_revisions.return_value = [{"name":"master","sha":REV}]
        self.assertEqual(revisions(MODEL, api=self.api)[0]["sha"], REV)

    def test_download_register_and_source_isolation(self):
        progress = []
        row = self.fetch(progress=lambda d,t: progress.append((d,t)))
        self.assertEqual(row["source"], "modelscope")
        self.assertEqual(self.registry.list(), [row])
        self.assertEqual(TeacherRegistry(self.root / "db").list(), [])
        self.assertEqual(progress[-1][0], progress[-1][1])
        self.assertTrue(all(x["upstream_sha256_verified"] for x in row["manifest"]))
        self.api.list_repo_files.assert_called_once_with(MODEL,"model",revision=REV,recursive=True)

    def test_restricted_or_unknown_metadata(self):
        for change in (dict(gated=True), dict(visibility="private"), dict(visibility=None),
                       dict(license=None), dict(id="another/model")):
            self.api.get_model.return_value = dict(id=MODEL, visibility="public",
                                                   license="apache-2.0") | change
            with self.assertRaises(ValueError):
                self.fetch()
        self.api.download_file.assert_not_called()

    def test_missing_digest_and_budget(self):
        with self.assertRaises(ValueError):
            self.fetch(max_bytes=1)
        self.api.list_repo_files.return_value[0].sha256 = None
        with self.assertRaisesRegex(ValueError, "SHA-256"):
            self.fetch()
        self.api.download_file.assert_not_called()

    def test_corrupt_download(self):
        def corrupt(*args, **kwargs):
            p = self.download(*args, **kwargs)
            if p.name == "model.safetensors":
                p.write_bytes(b"x" * p.stat().st_size)
            return p
        self.api.download_file.side_effect = corrupt
        with self.assertRaisesRegex(ValueError, "hash mismatch"):
            self.fetch()
        self.assertEqual(self.registry.list(), [])

    def test_queue_source(self):
        q = DownloadQueue(self.root / "db")
        job = q.enqueue(MODEL, REV, reviewed_license="apache-2.0", max_bytes=1024,
                        cache_dir=self.root / "cache", source="modelscope")
        self.assertEqual(job["spec"]["source"], "modelscope")
        result = q.run_next(execute=lambda **kw: download_modelscope(**kw, api=self.api))
        self.assertEqual(result["state"], "succeeded")
        self.assertEqual(len(self.registry.list()), 1)
