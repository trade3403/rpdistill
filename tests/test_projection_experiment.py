import unittest
from copy import deepcopy
from rpdistill.projection_experiment import compare_profiles
from rpdistill.rust_profile import SCHEMA

def profile(exe,ns):
    return {"schema":SCHEMA,"package_id":"p","weights_sha256":"w","d_reference":"d",
        "host":{},"kernel":"Auto","compute_dtype":"float32","executable_sha256":exe,
        "cases":[{"source_tokens":s,"max_new_tokens":n,"actual_generated_tokens":n,
                  "greedy_ids":[65000]+[4]*n,"ended":False,"warmup_repeats":1,"measured_repeats":3,
                  "full_cached_token_match":True,"median_ns":{k:ns for k in
                      ("encoder","full_generation","cached_generation")}} for s,n in ((16,8),(64,16))]}

class ProjectionExperimentTests(unittest.TestCase):
    def test_compare_speedup_without_threshold(self):
        a,b=profile("a",100),profile("b",150)
        rows=compare_profiles(a,b)
        self.assertAlmostEqual(rows[0]["measurements"]["cached_generation"]["speedup_ratio"],2/3)
        self.assertEqual(len(rows),2)
    def test_identity_and_generation_mismatch(self):
        a,b=profile("a",100),profile("b",50)
        for field in ("host","weights_sha256","executable_sha256"):
            bad=deepcopy(b)
            bad[field]=a[field] if field=="executable_sha256" else "different"
            with self.assertRaises(ValueError):
                compare_profiles(a,bad)
        b["cases"][0]["greedy_ids"][-1]=5
        with self.assertRaises(ValueError):
            compare_profiles(a,b)
    def test_bad_timing(self):
        a,b=profile("a",100),profile("b",50)
        b["cases"][1]["median_ns"]["full_generation"]=0
        with self.assertRaises(ValueError):
            compare_profiles(a,b)
