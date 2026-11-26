import tempfile
from pathlib import Path
from contextlib import closing
import unittest
from unittest.mock import patch
from rpdistill.studio_reviews import run_review,recover_review
from rpdistill.studio_evaluation import connect
from rpdistill.studio import snapshot

class StudioReviewTests(unittest.TestCase):
    def test_approval_and_blind_record(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp); db=root/"db"
            inp=root/"baseline.jsonl"; inp.write_text("{}\n",encoding="utf-8")
            with self.assertRaises(ValueError):
                run_review(db,"a"*32,"blind",root/"eval",root/"artifact",root/"review",input_path=inp)
            self.assertFalse((root/"review").exists())
            with patch("rpdistill.studio_reviews.source",return_value=({},None,{},{})),patch(
                "rpdistill.studio_reviews.evaluate",return_value={"report_id":"b"*64}),patch(
                "rpdistill.studio_reviews.create_blind_review",return_value=({"packet_id":"c"*64,"cases":[{}]},{"key_id":"d"*64})):
                result=run_review(db,"a"*32,"blind",root/"eval",root/"artifact",root/"review",input_path=inp,approved=True)
            self.assertFalse(result["release_ready"])
            dest=root/"review"/result["id"]
            self.assertTrue((dest/"packet.json").is_file())
            self.assertTrue((dest/"private"/"key.json").is_file())
            row=snapshot(db)["rows"]["reviews"][0]
            self.assertEqual(row["packet_id"],"c"*64)
            self.assertNotIn("key_id",row)
            with closing(connect(db)) as c,c:
                c.execute("UPDATE studio_reviews SET state='running' WHERE id=?",(result["id"],))
            with self.assertRaises(ValueError):
                recover_review(db,result["id"])
            recover_review(db,result["id"],worker_stopped=True)
            self.assertEqual(snapshot(db)["counts"]["review_active"],0)

    def test_receipt_check_uses_registered_pins(self):
        from rpdistill.studio_reviews import initialize
        from rpdistill.studio_artifacts import initialize as init_artifacts
        import json
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp); db=root/"db"; reviews=root/"review"
            aid,rid="a"*32,"b"*32
            package,receipt="c"*64,"d"*64
            with closing(connect(db)) as c,c:
                initialize(c); init_artifacts(c)
                c.execute("INSERT INTO studio_artifacts VALUES (?,?,?,'complete',?,NULL,?,?)",
                          (aid,"e"*32,"export",json.dumps({"artifact_id":package}),"2026-01-01","2026-01-01"))
                c.execute("INSERT INTO studio_reviews VALUES (?,?,?,'complete',?,NULL,?,?)",
                          (rid,"f"*32,"integration",json.dumps({"artifact_id":aid,"package_id":package,"receipt_id":receipt}),"2026-01-01","2026-01-01"))
            (reviews/rid).mkdir(parents=True)
            (reviews/rid/"receipt.json").write_text("{}",encoding="utf-8")
            with patch("rpdistill.studio_reviews.check_integration_receipt",return_value={"handoff_integrity_verified":True,"release_ready":False}) as check:
                result=run_review(db,rid,"receipt-check",root/"eval",root/"artifact",reviews,approved=True)
                check.assert_called_once_with(root/"artifact"/aid/"candidate",{},expected_package_id=package,expected_receipt_id=receipt)
            self.assertFalse(result["release_ready"])
            row=next(r for r in snapshot(db)["rows"]["reviews"] if r["id"]==result["id"])
            self.assertEqual(row["integrity_verified"],1)
            self.assertIsNone(row["integration_passed"])
    def test_reject_mismatched_integration_sources(self):
        from rpdistill.studio_reviews import initialize
        from rpdistill.studio_artifacts import initialize as init_artifacts
        import json
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp); db=root/"db"
            with closing(connect(db)) as c,c:
                initialize(c); init_artifacts(c)
                c.execute("INSERT INTO studio_reviews VALUES (?,?,?,'complete',?,NULL,?,?)",
                    ("a"*32,"b"*32,"collect",json.dumps({"candidate_gate_passed":True}),"2026-01-01","2026-01-01"))
                c.execute("INSERT INTO studio_reviews VALUES (?,?,?,'complete',?,NULL,?,?)",
                    ("b"*32,"c"*32,"blind","{}","2026-01-01","2026-01-01"))
                c.execute("INSERT INTO studio_artifacts VALUES (?,?,?,'complete',?,NULL,?,?)",
                    ("d"*32,"e"*32,"export","{}","2026-01-01","2026-01-01"))
            with self.assertRaisesRegex(ValueError,"share exact evaluation"):
                run_review(db,"a"*32,"integration",root/"eval",root/"artifact",root/"review",artifact_id="d"*32,approved=True)
            self.assertFalse((root/"review").exists())
