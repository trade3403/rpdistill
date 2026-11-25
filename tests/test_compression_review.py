import unittest
from copy import deepcopy
from rpdistill.compression_review import RegressionGate,regression,choose

def scored():
    return {"generation_complete":True,"evaluation":{"benchmark_id":"b","training_dataset":"d",
        "gate":{},"metric_versions":{},"coverage":{"cases":1},"automatic_gate_passed":True,
        "metrics":{"bleu":80.0,"chrf":90.0,"numeric":1.0},
        "details":[{"id":"a","hypothesis":"译文","numeric_exact":True,"citation_exact":True,
                    "term_hits":1,"protected_hits":1,"suspicious_flags":[]}]}}

class CompressionReviewTests(unittest.TestCase):
    def test_identical_pass_and_new_case_failure(self):
        a=scored()
        b=deepcopy(a)
        self.assertTrue(regression(a,b)["passed"])
        b["evaluation"]["details"][0]["numeric_exact"]=False
        self.assertIn("new_case_errors",regression(a,b)["failures"])
    def test_absolute_and_relative_failures(self):
        a=scored()
        b=deepcopy(a)
        b["generation_complete"]=False
        b["evaluation"]["metrics"]["bleu"]=78
        b["evaluation"]["details"][0]["hypothesis"]="不同"
        self.assertEqual(set(regression(a,b)["failures"]),{"candidate_absolute_quality","bleu_drop","changed_fraction"})
        a["evaluation"]["automatic_gate_passed"]=False
        self.assertIn("source_absolute_quality",regression(a,a)["failures"])
    def test_selection_uses_actual_bytes_and_audit(self):
        rows=[{"candidate_id":"a","mode":"int8","artifact_bytes":30,"regression":{"passed":False}},
              {"candidate_id":"b","mode":"fp16","artifact_bytes":60,"regression":{"passed":True}},
              {"candidate_id":"c","mode":"fp32","artifact_bytes":100,"regression":{"passed":True}}]
        self.assertEqual(choose(rows,audit_passed=True)["mode"],"fp16")
        self.assertIsNone(choose(rows,audit_passed=False))
        self.assertIsNone(choose(rows[:1],audit_passed=True))
    def test_invalid_gate_and_incomparable(self):
        with self.assertRaises(ValueError):
            RegressionGate(max_chrf_drop=float("nan"))
        a=scored()
        b=deepcopy(a)
        b["evaluation"]["benchmark_id"]="other"
        with self.assertRaises(ValueError):
            regression(a,b)
