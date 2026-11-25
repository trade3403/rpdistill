import hashlib
from pathlib import Path
import tempfile
import unittest

from rpdistill.inference import TranslationOptions, TeacherTranslator, checked_snapshot
from rpdistill.teachers import Teacher, TeacherRegistry

REV = "a"*40


class FakeBackend:
    def __init__(self, result=None):
        self.batches = []
        self.result = result

    def generate(self, messages, options):
        self.batches.append(messages)
        return [self.result or {"translation":"译文", "finish_reason":"eos",
                                "generated_tokens":2} for _ in messages]


class InferenceTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        self.path = self.root / "snapshot"
        self.path.mkdir()
        manifest = []
        for name, data in (("config.json", b"{}"), ("model.safetensors", b"synthetic")):
            (self.path / name).write_bytes(data)
            manifest.append({"name":name,"size":len(data),"sha256":hashlib.sha256(data).hexdigest()})
        self.registry = TeacherRegistry(self.root / "db")
        self.record = self.registry.put(Teacher("test/model", REV, "mit", False, False, None),
                                        self.path, manifest)

    def test_registry_exact_revision(self):
        self.assertEqual(self.registry.get("test/model", REV), self.record)
        with self.assertRaises(KeyError):
            self.registry.get("test/model", "b"*40)

    def test_snapshot_hash_and_extra_file(self):
        self.assertEqual(checked_snapshot(self.record), self.path.resolve())
        extra = self.path / "pytorch_model.bin"
        extra.write_bytes(b"bad")
        with self.assertRaisesRegex(ValueError, "unregistered"):
            checked_snapshot(self.record)
        extra.unlink()
        (self.path / "model.safetensors").write_bytes(b"x"*9)
        with self.assertRaisesRegex(ValueError, "hash mismatch"):
            checked_snapshot(self.record)

    def test_batch_order_and_provenance(self):
        backend = FakeBackend()
        results = TeacherTranslator(self.record, TranslationOptions(batch_size=2),
                                    backend=backend).translate(["a","b","c"])
        self.assertEqual([r["source_text"] for r in results], ["a","b","c"])
        self.assertEqual([len(b) for b in backend.batches], [2,1])
        self.assertEqual(results[0]["teacher"]["revision"], REV)
        self.assertEqual(results[0]["status"], "candidate")
        self.assertIn("Preserve", backend.batches[0][0][0]["content"])

    def test_review_incomplete_outputs(self):
        for result in ({"translation":"", "finish_reason":"eos", "generated_tokens":0},
                       {"translation":"partial", "finish_reason":"length", "generated_tokens":2},
                       {"translation":"<think>reason</think>", "finish_reason":"eos", "generated_tokens":2}):
            rows = TeacherTranslator(self.record, TranslationOptions(),
                backend=FakeBackend(result)).translate(["source"])
            self.assertEqual(rows[0]["status"], "needs_review")

    def test_options_validation(self):
        for kw in ({"batch_size":0}, {"max_new_tokens":True}, {"device":"mps"},
                   {"dtype":"float16"}, {"target_language":"English"},
                   {"max_input_tokens":40000}):
            with self.assertRaises(ValueError):
                TranslationOptions(**kw)

    def test_invalid_input_and_batch_mismatch(self):
        translator = TeacherTranslator(self.record, TranslationOptions(), backend=FakeBackend())
        for texts in ("text", [], [""]):
            with self.assertRaises(ValueError):
                translator.translate(texts)
        backend = FakeBackend()
        backend.generate = lambda *args: []
        with self.assertRaisesRegex(ValueError, "batch size"):
            TeacherTranslator(self.record, TranslationOptions(), backend=backend).translate(["x"])
