import unittest
from unittest.mock import Mock,patch
import time
from rpdistill.export_review import review_integration,review_rights,check_replay
from rpdistill.evaluation import hash_json

ID="a"*64
CK="b"*64
DATA="c"*64
BENCH={"training_dataset":DATA,"benchmark_id":"d"*64,"cases":[{"id":"1","source":"Text"}]}
MANIFEST={"origin":{"training_dataset":DATA,"checkpoint_id":CK},"rights":{"operator_declared_model_license":"internal"},
          "files":{"weights.safetensors":{"sha256":"e"*64}}}
STUDENT={"checkpoint_id":CK,"report_id":"f"*64,"generation_config":{},"generation":[{"id":"1","finish_reason":"eos","generated_tokens":1}]}
BASELINE={"report_id":"1"*64}
KW={"expected_package_id":ID,"reviewed_dataset":DATA,"reviewed_teacher_license":"apache-2.0",
    "reviewed_model_license":"internal","rights_note":"Local review","reviewer":"reviewer","executable":"unused"}

class ExportReviewTests(unittest.TestCase):
    def call(self,**kw):
        return review_integration("db","root","checkpoint",BENCH,STUDENT,BASELINE,{}, {}, [],
            **(KW|kw))

    def test_ack_and_budget(self):
        with self.assertRaisesRegex(ValueError,"acknowledgment"):
            self.call()
        with self.assertRaisesRegex(ValueError,"case budget"):
            self.call(acknowledge_local_candidate_only=True,max_cases=0)

    def test_quality_failure_stops_before_replay_or_rust(self):
        with patch("rpdistill.export_review.validate_benchmark",return_value=BENCH), \
             patch("rpdistill.export_review.verify_package",return_value=MANIFEST), \
             patch("rpdistill.export_review.collect_review",return_value={"candidate_gate_passed":False,"failures":["case_coverage"]}), \
             patch("rpdistill.export_review.verify_source_weights") as source, \
             patch("rpdistill.export_review.rust_parity") as parity:
            with self.assertRaisesRegex(ValueError,"quality review gate"):
                self.call(acknowledge_local_candidate_only=True)
            source.assert_not_called()
            parity.assert_not_called()

    def test_wrong_dataset_and_changed_training_provenance(self):
        with patch("rpdistill.export_review.prepare_reviewed_snapshot",return_value=([{}],{"new":True})):
            args=dict(reviewed_dataset=DATA,reviewed_teacher_license="apache-2.0",
                      reviewed_model_license="internal",rights_note="review",reviewer="r",training_limit=1)
            with self.assertRaisesRegex(ValueError,"provenance"):
                review_rights("db","root",{"provenance":{}},MANIFEST,**args)
            with self.assertRaisesRegex(ValueError,"exact dataset"):
                review_rights("db","root",{"provenance":{}},MANIFEST,**(args|{"reviewed_dataset":ID}))

    def test_output_replay_rejects_changed_translation(self):
        with patch("rpdistill.export_review.report_outputs",return_value=[{"id":"1","hypothesis":"文本"}]), \
             patch("rpdistill.export_review.generate_one",return_value={"hypothesis":"错误","finish_reason":"eos","generated_tokens":1}):
            with self.assertRaisesRegex(ValueError,"actual model output"):
                check_replay(None,None,BENCH,STUDENT,deadline=time.monotonic()+10)

    def test_successful_local_receipt_never_authorizes_release(self):
        from rpdistill.rust_parity import D_REFERENCE
        with patch("rpdistill.export_review.validate_benchmark",return_value=BENCH), \
             patch("rpdistill.export_review.verify_package",return_value=MANIFEST), \
             patch("rpdistill.export_review.collect_review",return_value={"candidate_gate_passed":True}), \
             patch("rpdistill.export_review.verify_source_weights",return_value=(Mock(),{})), \
             patch("rpdistill.export_review.review_rights",return_value={"operator_rights_asserted":True}), \
             patch("rpdistill.export_review.StudentCodec.from_assets"), \
             patch("rpdistill.export_review.check_replay",return_value={"actual_output_replay":True}), \
             patch("rpdistill.export_review.rust_parity",return_value={"package_id":ID,"weights_sha256":"e"*64,
                 "d_reference":D_REFERENCE,"diagnostic_passed":True}):
            result=self.call(acknowledge_local_candidate_only=True)
            self.assertTrue(result["candidate_integration_gate_passed"])
            for key in ("release_ready","distribution_authorized","production_loader_verified","reviewer_identity_verified"):
                self.assertFalse(result[key])
            self.assertEqual(result["receipt_id"],hash_json({k:v for k,v in result.items() if k!="receipt_id"}))

    def test_resumable_training_token_hash_mismatch(self):
        from rpdistill.resumable import SCHEMA
        provenance={"teacher":{},"selected":{},"training_pair_ids_sha256":"a"*64}
        with patch("rpdistill.export_review.prepare_reviewed_snapshot",return_value=([{}],provenance)):
            with self.assertRaisesRegex(ValueError,"token data"):
                review_rights("db","root",{"schema":SCHEMA,"provenance":provenance,"data_sha256":"0"*64},
                    MANIFEST,reviewed_dataset=DATA,reviewed_teacher_license="apache-2.0",
                    reviewed_model_license="internal",rights_note="review",reviewer="r",training_limit=1)

    def test_dual_pin_handoff(self):
        from dataclasses import asdict
        from rpdistill.export_review import check_integration_receipt,SCHEMA
        from rpdistill.quality_review import ReviewGate
        from rpdistill.rust_parity import D_REFERENCE
        # This is an explicitly synthetic receipt fixture, not an actual approval.
        quality={"schema":"rpdistill-quality-review-v1","benchmark_id":BENCH["benchmark_id"],
            "training_dataset":DATA,"checkpoint_id":CK,"student_report":STUDENT["report_id"],
            "baseline_report":BASELINE["report_id"],"candidate_gate_passed":True,"failures":[],
            "review_gate":asdict(ReviewGate()),"case_count":100,"release_ready":False}
        quality["review_id"]=hash_json(quality)
        parity={"schema":"rpdistill-rust-parity-v1","package_id":ID,"weights_sha256":"e"*64,
            "d_reference":D_REFERENCE,"diagnostic_passed":True,"production_loader_verified":False,
            "release_ready":False}
        parity["report_id"]=hash_json(parity)
        receipt={"schema":SCHEMA,"package_id":ID,"weights_sha256":"e"*64,"checkpoint_id":CK,
            "training_dataset":DATA,"benchmark_id":BENCH["benchmark_id"],"student_report":STUDENT["report_id"],
            "baseline_report":BASELINE["report_id"],"quality_review":quality,
            "rights_review":{"dataset":DATA,"model_license":"internal","operator_rights_asserted":True,
                "legal_rights_verified_by_software":False,"distribution_authorized":False},
            "output_replay":{"actual_output_replay":True,"cases":100,"hypotheses_sha256":"3"*64},
            "rust_diagnostics":parity,"candidate_integration_gate_passed":True,
            "production_loader_verified":False,"reviewer_identity_verified":False,"baseline_identity_verified":False,
            "distribution_authorized":False,"release_ready":False}
        receipt["receipt_id"]=hash_json(receipt)
        with patch("rpdistill.export_review.verify_package",return_value=MANIFEST):
            result=check_integration_receipt("root",receipt,expected_package_id=ID,expected_receipt_id=receipt["receipt_id"])
            self.assertTrue(result["handoff_integrity_verified"])
            self.assertFalse(result["current_rights_revalidated"])
            self.assertFalse(result["release_ready"])
            with self.assertRaises(ValueError):
                check_integration_receipt("root",receipt,expected_package_id=ID,expected_receipt_id="0"*64)
            with self.assertRaises(ValueError):
                check_integration_receipt("root",receipt|{"release_ready":True},
                    expected_package_id=ID,expected_receipt_id=receipt["receipt_id"])
            altered={k:v for k,v in receipt.items() if k!="receipt_id"}
            altered["rust_diagnostics"]=parity|{"weights_sha256":"0"*64}
            altered["receipt_id"]=hash_json(altered)
            with self.assertRaisesRegex(ValueError,"nested"):
                check_integration_receipt("root",altered,expected_package_id=ID,expected_receipt_id=altered["receipt_id"])
