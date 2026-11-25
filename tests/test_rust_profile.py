import unittest
from rpdistill.rust_profile import parse_profile

def fixture(*,early_eos_lengths=()):
    rows=["rpdistill-profile-v1","load\t1\t2\t3\t4\t5\t6"]
    for length,n in ((16,8),(64,16)):
        ended=length in early_eos_lengths
        ids="65000,0" if ended else "65000,"+",".join(["4"]*n)
        flag="true" if ended else "false"
        for repeat in (1,2,3):
            rows.append(f"case\t{length}\t{n}\t{repeat}\t10\t20\t{100*repeat}\t{50*repeat}\t{flag}\t{ids}")
    return ("\n".join(rows+["rss\t123456"])+"\n").encode("ascii")

class RustProfileTests(unittest.TestCase):
    def test_medians_and_scope(self):
        r=parse_profile(fixture())
        self.assertEqual(r["rust_process_peak_rss_bytes"],123456)
        self.assertEqual(r["cases"][0]["median_ns"]["full_generation"],200)
        self.assertEqual(r["cases"][0]["cached_speedup_ratio"],2)
        self.assertEqual(r["cases"][1]["actual_generated_tokens"],16)

    def test_bad_protocol_and_repeat(self):
        raw=fixture()
        for bad in (raw+b"x",raw.replace(b"case\t16\t8\t2",b"case\t16\t8\t1"),
                    raw.replace(b"\t100\t50\t",b"\t0\t50\t"),
                    raw.replace(b"65000,4,4",b"65000,0,4",1),
                    raw.replace(b"65000,4,4",b"65000,3,4",1)):
            with self.assertRaises(ValueError):
                parse_profile(bad)

    def test_early_eos(self):
        for lengths in ((16,),(64,),(16,64)):
            with self.subTest(early_eos_lengths=lengths):
                r=parse_profile(fixture(early_eos_lengths=lengths))
                for case in r["cases"]:
                    ended=case["source_tokens"] in lengths
                    self.assertEqual(case["ended"],ended)
                    self.assertEqual(case["actual_generated_tokens"],1 if ended else case["max_new_tokens"])
                    if ended:
                        self.assertEqual(case["greedy_ids"],[65000,0])

    def test_eos_with_trailing_tokens_rejected(self):
        raw=fixture(early_eos_lengths=(16,))
        bad=raw.replace(b"true\t65000,0\n",b"true\t65000,0,4\n",1)
        with self.assertRaisesRegex(ValueError,"invalid generated IDs"):
            parse_profile(bad)
