import unittest
from unittest.mock import patch
from rpdistill.evaluation import QualityGate,freeze_benchmark,validate_benchmark,screen_case,clean_case

VERSION="a"*64
ROW={"id":"case1","paper_id":"paper1","pmcid":"PMC123","source":"The confidence interval is 95%. [12] x=2",
     "reference":"置信区间为95%。 [12] x=2","terms":[{"source":"confidence interval","targets":["置信区间"]}],
     "protected":["x=2"],"rights_note":"Synthetic authored fixture."}


class EvaluationTests(unittest.TestCase):
    def test_frozen_identity(self):
        with patch("rpdistill.evaluation.training_identity",return_value=(set(),set())):
            b=freeze_benchmark("unused",VERSION,[ROW],review_note="Human reviewed fixture")
            self.assertEqual(validate_benchmark("unused",b),b)
            b["cases"][0]["reference"]="错误译文95%。 [12] x=2"
            with self.assertRaises(ValueError):
                validate_benchmark("unused",b)

    def test_training_overlap(self):
        for sources,papers in (({ROW["source"].casefold()},set()),(set(),{"pmc:PMC123"})):
            with patch("rpdistill.evaluation.training_identity",return_value=(sources,papers)):
                with self.assertRaisesRegex(ValueError,"overlap"):
                    freeze_benchmark("unused",VERSION,[ROW],review_note="Fixture")

    def test_numeric_citation_term_formula_flags(self):
        c=clean_case(ROW)
        good=screen_case(c,ROW["reference"])
        self.assertTrue(good["numeric_exact"] and good["citation_exact"])
        self.assertEqual(good["term_hits"],1)
        self.assertEqual(good["protected_hits"],1)
        bad=screen_case(c,"错误90%。 [13] x=3")
        self.assertFalse(bad["numeric_exact"] or bad["citation_exact"])
        self.assertEqual(bad["term_hits"]+bad["protected_hits"],0)
        self.assertIn("empty",screen_case(c,"")["suspicious_flags"])

    def test_invalid_reference_and_gate(self):
        with self.assertRaises(ValueError):
            clean_case(ROW|{"reference":"置信区间为90%。 [12] x=2"})
        for kw in (dict(min_cases=0),dict(min_chrf=101),dict(min_numeric=float("nan"))):
            with self.assertRaises(ValueError):
                QualityGate(**kw)
