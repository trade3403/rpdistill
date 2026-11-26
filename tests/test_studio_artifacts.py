import tempfile
from pathlib import Path
from contextlib import closing
import unittest
from unittest.mock import patch
from rpdistill.studio_artifacts import run_artifact,recover_artifact,initialize
from rpdistill.studio_evaluation import connect
from rpdistill.studio import snapshot

class StudioArtifactTests(unittest.TestCase):
    def test_approval_budget_and_recovery(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp); db=root/"db"
            with closing(connect(db)) as c,c:
                initialize(c)
                c.execute("INSERT INTO studio_artifacts VALUES (?,?,?,'running',NULL,NULL,?,?)",
                          ("a"*32,"b"*32,"int8","2026-01-01","2026-01-01"))
            for approved,amount in ((False,2**30),(True,1)):
                with self.assertRaises(ValueError):
                    run_artifact(db,"b"*32,"int8",root/"eval",root/"out",max_bytes=amount,approved=approved)
            self.assertFalse((root/"out").exists())
            self.assertEqual(snapshot(db)["counts"]["artifact_active"],1)
            with self.assertRaises(ValueError):
                recover_artifact(db,"a"*32)
            recover_artifact(db,"a"*32,worker_stopped=True)
            self.assertEqual(snapshot(db)["rows"]["artifacts"][0]["state"],"interrupted")
    def test_comparison_record_not_release(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp); db=root/"db"
            job={"checkpoint_id":"c"*64,"spec":{"version":"d"*64,"assets":str(root/"assets")}}
            benchmark={"benchmark_id":"e"*64}
            report={"generation_config":{"max_new_tokens":128,"max_logits":16777216}}
            row={"candidate_id":"f"*64,"mode":"int8","source_conversion_verified":True,"artifact_bytes":1024,
                 "weights_bytes":1000,
                 "score":{"total_generation_seconds":2.5,"generated_tokens_per_second":4.0,
                          "median_case_seconds":1.25,"p95_case_seconds":1.5},
                 "regression":{"metric_delta":{"bleu":-2.0,"chrf":-1.0},"failures":["bleu_drop"],
                               "changed_fraction":0.5,"new_case_errors":[{"id":"a"}]}}
            comparison={"source_checkpoint_id":job["checkpoint_id"],"benchmark_id":benchmark["benchmark_id"],"release_ready":False,
                        "source":{"total_generation_seconds":2.0,"generated_tokens_per_second":5.0,
                                  "median_case_seconds":1.0,"p95_case_seconds":1.2},
                        "compute_dtype":"float32","native_low_precision_inference":False,
                        "candidates":[row],"selected":None,"review_id":"1"*64}
            with patch("rpdistill.studio_artifacts.source",return_value=(job,root/"checkpoint",benchmark,report)),patch(
                "rpdistill.studio_artifacts.create_candidate",return_value={"candidate_id":row["candidate_id"]}),patch(
                "rpdistill.studio_artifacts.compare_candidates",return_value=comparison):
                result=run_artifact(db,"b"*32,"int8",root/"eval",root/"out",max_bytes=2**30,approved=True)
            self.assertFalse(result["release_ready"])
            r=snapshot(db)["rows"]["artifacts"][0]
            self.assertEqual(r["regression_passed"],0)
            self.assertEqual(r["bleu_delta"],-2.0)
            self.assertEqual(r["source_seconds"],2.0)
            self.assertEqual(r["candidate_seconds"],2.5)
            self.assertEqual(r["source_tokens_per_second"],5.0)
            self.assertEqual(r["candidate_tokens_per_second"],4.0)
            self.assertEqual(r["candidate_p95"],1.5)
            self.assertEqual(r["native_low_precision_inference"],0)
            self.assertEqual(r["new_case_error_count"],1)
            self.assertTrue((root/"out"/result["id"]/"comparison.json").is_file())
