import tempfile
from pathlib import Path
import unittest
from unittest.mock import Mock

from rpdistill.student import StudentProfile,FIXED,expected_shapes,contract,StudentCodec,checked_assets

class StudentTests(unittest.TestCase):
    def test_fixed_audited_contract(self):
        c=contract()
        self.assertEqual(c["canonical_tensors"],256)
        self.assertEqual(c["fp32_payload_bytes"],312033188)
        self.assertEqual(expected_shapes()["model.shared.weight"],(65001,512))
        self.assertFalse(c["rust_deployable"])

    def test_bad_profile(self):
        for kw in (dict(hidden=511),dict(heads=3),dict(vocab=10),dict(positions=1)):
            with self.assertRaises(ValueError):
                StudentProfile(**kw)

    def test_codec_network_ids_and_prefix(self):
        p=StudentProfile(vocab=8,hidden=8,heads=2,ffn=16,encoder_layers=1,
                         decoder_layers=1,positions=5,pad=7)
        vocab={"</s>":0,"<unk>":1,">>cmn_Hans<<":2,"▁test":3,"学":4,"x":5,"y":6,"<pad>":7}
        src=Mock();tgt=Mock()
        src.encode.return_value=["▁test"]
        tgt.encode.return_value=["学"]
        codec=StudentCodec(vocab,src,tgt,p)
        self.assertEqual(codec.encode("test"),[2,3,0])
        self.assertEqual(codec.encode("学",target=True),[4,0])
        for text in ("",">>cmn_Hans<< test","<unk>"):
            with self.assertRaises(ValueError):
                codec.encode(text)
        src.encode.return_value=["missing"]
        with self.assertRaises(ValueError):
            codec.encode("unknown")
        src.encode.return_value=["▁test"]*4
        with self.assertRaises(ValueError):
            codec.encode("too long")

    def test_invalid_asset_and_vocab(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(ValueError):
                checked_assets(Path(tmp))
        with self.assertRaises(ValueError):
            StudentCodec({},Mock(),Mock())
