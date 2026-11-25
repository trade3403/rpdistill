import unittest
from rpdistill.compression import plan,layout
from rpdistill.student import FIXED

class CompressionTests(unittest.TestCase):
    def test_fixed_size_and_order(self):
        a,b,c=[plan(m) for m in ("fp32","fp16","int8")]
        self.assertEqual(a["payload_bytes"],312033188)
        self.assertLess(c["payload_bytes"],b["payload_bytes"])
        self.assertLess(b["payload_bytes"],a["payload_bytes"])
        self.assertFalse(c["rust_deployable"])
        self.assertFalse(c["native_low_precision_inference"])
        self.assertEqual(c["canonical_tensors"],256)

    def test_preserved_weights_and_scales(self):
        s=layout("int8")
        self.assertEqual(s["model.shared.weight"],{"shape":[65001,512],"dtype":"int8"})
        self.assertEqual(s["model.shared.weight.row_scale"],{"shape":[65001],"dtype":"fp32"})
        self.assertEqual(s["model.encoder.embed_positions.weight"]["dtype"],"fp32")
        self.assertEqual(s["final_logits_bias"]["dtype"],"fp32")
        self.assertEqual(s["model.encoder.layers.0.final_layer_norm.weight"]["dtype"],"fp32")
        self.assertNotIn("lm_head.weight",s)

    def test_unknown_mode(self):
        with self.assertRaises(ValueError):
            plan("int4")
