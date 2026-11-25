import tempfile
from pathlib import Path
import unittest
from rpdistill.distill import DistillConfig
from rpdistill.resumable import ResumeConfig,epoch_groups,required_bytes,preflight
from rpdistill.student import StudentProfile

P=StudentProfile(vocab=32,hidden=16,encoder_layers=1,decoder_layers=1,heads=2,ffn=32,positions=16,pad=31)
EX=[{"source_ids":[2,i,0],"target_ids":[i+5,0]} for i in range(3,8)]

class ResumeTests(unittest.TestCase):
    def test_accumulation_validation(self):
        for v in (0,65,True):
            with self.assertRaises(ValueError):
                ResumeConfig(accumulation=v)

    def test_deterministic_epoch_groups(self):
        cfg=ResumeConfig(DistillConfig(batch_size=1),2)
        a=epoch_groups(EX,P,cfg,0)
        self.assertEqual(a,epoch_groups(EX,P,cfg,0))
        self.assertEqual([len(x) for x in a],[2,2,1])
        self.assertNotEqual(a,epoch_groups(EX,P,cfg,1))

    def test_checkpoint_budget(self):
        with tempfile.TemporaryDirectory() as tmp:
            dest=Path(tmp)/"state"
            with self.assertRaises(ValueError):
                preflight(dest,P,required_bytes(P)-1)
            self.assertEqual(preflight(dest,P,required_bytes(P)),dest.resolve())
            dest.mkdir()
            with self.assertRaises(ValueError):
                preflight(dest,P,required_bytes(P))

    def test_device_precision_budget_validation(self):
        from rpdistill.resumable import config_record
        from dataclasses import asdict
        for kw in (dict(device="cuda"),dict(device="cuda:0"),dict(precision="float16"),
                   dict(cuda_budget_bytes=1),dict(device="cuda:0",cuda_budget_bytes=-1),
                   dict(device="cuda:0",precision="int8",cuda_budget_bytes=1)):
            with self.assertRaises(ValueError):
                ResumeConfig(**kw)
        cpu=ResumeConfig()
        self.assertEqual(config_record(cpu),{"training":asdict(cpu.training),"accumulation":1})
        gpu=ResumeConfig(device="cuda:0",precision="float16",cuda_budget_bytes=2**30)
        self.assertEqual(config_record(gpu)["device"],"cuda:0")
        self.assertEqual(config_record(gpu)["precision"],"float16")
