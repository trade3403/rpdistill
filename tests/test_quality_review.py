import unittest
from unittest.mock import patch
from rpdistill.quality_review import leakage_audit,ReviewGate,create_blind_review,collect_review,seal

B={"benchmark_id":"a"*64,"training_dataset":"b"*64,"cases":[
    {"id":"case","source":"The temperature of the sample was measured under controlled laboratory conditions.",
     "reference":"在受控实验室条件下测量样品温度。"}]}

class QualityReviewTests(unittest.TestCase):
    def test_lexical_near_duplicate_and_budget(self):
        train="The temperature of the sample was measured under controlled laboratory conditions yesterday."
        with patch("rpdistill.quality_review.validate_benchmark",return_value=B),patch(
                "rpdistill.quality_review.training_identity",return_value=({train},set())):
            result=leakage_audit("db",B)
            self.assertFalse(result["passed"])
            self.assertGreaterEqual(result["matches"][0]["containment"],0.9)
            with self.assertRaises(ValueError):
                leakage_audit("db",B,max_postings=1)
    def test_distinct_and_internal_duplicate(self):
        with patch("rpdistill.quality_review.validate_benchmark",return_value=B),patch(
                "rpdistill.quality_review.training_identity",return_value=({"Different subject entirely."},set())):
            self.assertTrue(leakage_audit("db",B)["passed"])
        duplicate=B|{"cases":B["cases"]+[B["cases"][0]|{"id":"other"}]}
        with patch("rpdistill.quality_review.validate_benchmark",return_value=duplicate),patch(
                "rpdistill.quality_review.training_identity",return_value=(set(),set())):
            self.assertFalse(leakage_audit("db",duplicate)["passed"])
    def test_blind_packet_review_and_binding(self):
        student={"report_id":"c"*64,"checkpoint_id":"d"*64,"generation":[{"id":"case","finish_reason":"eos"}]}
        baseline={"report_id":"e"*64}
        outputs=([{"id":"case","hypothesis":"甲"}],[{"id":"case","hypothesis":"乙"}])
        with patch("rpdistill.quality_review.checked_reports",return_value=outputs),patch(
                "rpdistill.quality_review.leakage_audit",return_value={"passed":True}),patch(
                "rpdistill.quality_review.evaluate",return_value={"automatic_gate_passed":True,"report_id":"f"*64}):
            packet,key=create_blind_review("db",B,student,baseline)
            self.assertNotIn("student",str(packet))
            row=packet["cases"][0]
            side=key["mappings"][0]["student_side"]
            good={"adequacy":4,"fluency":4,"critical_error":False}
            bad={"adequacy":2,"fluency":2,"critical_error":True}
            score={"id":row["id"],"A":good if side=="A" else bad,"B":good if side=="B" else bad,"preference":side}
            reviews=[{"reviewer":name,"packet_id":packet["packet_id"],"independent_review_asserted":True,"scores":[score]} for name in ("r1","r2")]
            result=collect_review("db",B,student,baseline,packet,key,reviews,gate=ReviewGate(min_cases=1))
            self.assertTrue(result["candidate_gate_passed"])
            self.assertFalse(result["release_ready"])
            self.assertEqual(result["metrics"]["student_adequacy"],4)
            with self.assertRaises(ValueError):
                collect_review("db",B,student,baseline,packet,key,[reviews[0],reviews[0]])
            tampered=seal({k:v for k,v in key.items() if k!="key_id"}|{"student_report":"0"*64},"key_id")
            with self.assertRaises(ValueError):
                collect_review("db",B,student,baseline,packet,tampered,reviews)
            rejected=collect_review("db",B,student,baseline,packet,key,reviews)
            self.assertIn("case_coverage",rejected["failures"])
