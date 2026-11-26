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
