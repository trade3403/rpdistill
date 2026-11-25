import hashlib
from pathlib import Path
from types import SimpleNamespace as NS
import tempfile
import unittest
from unittest.mock import Mock

from rpdistill.teachers import (
    TeacherRegistry, download_teacher, plan_files, search_teachers,
    validate_id, validate_revision,
)

REV = "a" * 40
MODEL = "Qwen/test"
PAYLOAD = {"config.json": b"{}", "tokenizer.json": b"{}",
           "model.safetensors": b"synthetic-not-a-real-model"}


def info(**changes):
    files = [NS(rfilename=name, size=len(data),
                lfs=NS(sha256=hashlib.sha256(data).hexdigest()))
             for name, data in PAYLOAD.items()]
    files.append(NS(rfilename="modeling.py", size=200, lfs=None))
    return NS(**(dict(id=MODEL, sha=REV, tags=["license:apache-2.0"],
                      gated=False, private=False, pipeline_tag="text-generation",
                      siblings=files) | changes))


class TeacherTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        self.registry = TeacherRegistry(self.root / "registry.db")
        self.api = Mock()
        self.api.model_info.return_value = info()
        self.download = Mock(side_effect=self.fake_download)

    def fake_download(self, **kwargs):
        path = kwargs["cache_dir"] / "snapshot"
        path.mkdir(exist_ok=True)
        for name, content in PAYLOAD.items():
            (path / name).write_bytes(content)
        return path

    def fetch(self, **changes):
        options = dict(reviewed_license="apache-2.0", max_bytes=1024,
                       cache_dir=self.root / "cache", registry=self.registry,
                       api=self.api, downloader=self.download)
        return download_teacher(MODEL, REV, **(options | changes))

    def test_search_pinned_and_bounded(self):
        self.api.list_models.return_value = [info(), info(sha=None), info(id="other/model")]
        result = search_teachers("Qwen", 2, api=self.api)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0].revision, REV)
        self.api.list_models.assert_called_once_with(search="Qwen", limit=2, full=True, token=False)

    def test_invalid_inputs(self):
        for bad in ("../x", "a/b/c", "a\\b", ""):
            with self.assertRaises(ValueError):
                validate_id(bad)
        with self.assertRaises(ValueError):
            validate_revision("main")
        with self.assertRaises(ValueError):
            search_teachers("Qwen", 101, api=self.api)

    def test_download_and_register(self):
        result = self.fetch()
        self.assertEqual(result["revision"], REV)
        self.assertEqual(len(result["manifest"]), 3)
        self.assertTrue(all(f["upstream_sha256_verified"] for f in result["manifest"]))
        self.assertEqual(TeacherRegistry(self.root / "registry.db").list(), [result])
        self.assertNotIn("modeling.py", self.download.call_args.kwargs["allow_patterns"])
        self.assertFalse(self.download.call_args.kwargs["token"])

    def test_license_and_restricted_models(self):
        for model, license_id in ((info(gated="manual"), "apache-2.0"),
                                  (info(private=True), "apache-2.0"),
                                  (info(tags=[]), "apache-2.0"),
                                  (info(), "mit")):
            self.api.model_info.return_value = model
            with self.assertRaises(ValueError):
                self.fetch(reviewed_license=license_id)
        self.download.assert_not_called()
        self.assertEqual(self.registry.list(), [])

    def test_revision_mismatch(self):
        self.api.model_info.return_value = info(sha="b"*40)
        with self.assertRaises(ValueError):
            self.fetch()
        self.download.assert_not_called()

    def test_budget_and_unknown_size(self):
        with self.assertRaises(ValueError):
            self.fetch(max_bytes=1)
        model = info()
        model.siblings[0].size = None
        self.api.model_info.return_value = model
        with self.assertRaises(ValueError):
            self.fetch()
        self.download.assert_not_called()

    def test_unsafe_paths(self):
        for name in ("../config.json", "/config.json", "CON.json", "a\\b.json", "a/*.json"):
            model = info()
            model.siblings.append(NS(rfilename=name, size=1, lfs=None))
            with self.assertRaises(ValueError):
                plan_files(model, 1024)

    def test_corruption_never_registered(self):
        def corrupt(**kwargs):
            path = self.fake_download(**kwargs)
            (path / "model.safetensors").write_bytes(b"x" * len(PAYLOAD["model.safetensors"]))
            return path
        with self.assertRaisesRegex(ValueError, "hash mismatch"):
            self.fetch(downloader=corrupt)
        self.assertEqual(self.registry.list(), [])
