import unittest
from unittest.mock import Mock
from rpdistill.student import StudentProfile
from rpdistill.student_evaluation import GenerationConfig,decode_generated

class StudentEvaluationTests(unittest.TestCase):
    def test_config_limits(self):
        for kw in (dict(max_new_tokens=0),dict(max_new_tokens=512),dict(max_logits=True)):
            with self.assertRaises(ValueError):
                GenerationConfig(**kw)

    def test_decode_network_ids(self):
        p=StudentProfile(vocab=8,hidden=8,heads=2,ffn=16,encoder_layers=1,decoder_layers=1,positions=8,pad=7)
        codec=Mock(profile=p,vocab={"</s>":0,"<unk>":1,">>cmn_Hans<<":2,"▁科研":3,"翻译":4,"▁x":5,"。":6,"<pad>":7})
        self.assertEqual(decode_generated([3,4,5,6],codec),"科研翻译 x。")
        for ids in ([1],[0],[7],[8],[2]):
            with self.assertRaises(ValueError):
                decode_generated(ids,codec)
