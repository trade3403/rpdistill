import unittest
from unittest.mock import patch
from rpdistill.distill import DistillConfig,train_reviewed_snapshot

class DistillTests(unittest.TestCase):
    def test_defaults(self):
        self.assertEqual(DistillConfig().steps,20)
    def test_invalid_parameters(self):
        for kw in (dict(steps=0),dict(batch_size=True),dict(learning_rate=float("nan")),
                   dict(seed=-1),dict(max_grad_norm=0),dict(max_logits=134217729)):
            with self.assertRaises(ValueError):
                DistillConfig(**kw)
    def test_review_gate_before_model_load(self):
        with patch("rpdistill.distill.build_student") as build:
            with self.assertRaises(ValueError):
                train_reviewed_snapshot("unused","a"*64,"unused","unused",
                    reviewed_dataset="b"*64,reviewed_teacher_license="mit")
            build.assert_not_called()
