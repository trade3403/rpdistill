import tempfile
from pathlib import Path
import unittest
from rpdistill.model_export import export_plan,export_candidate,valid_id,REQUIRED_BYTES

class ModelExportTests(unittest.TestCase):
    def test_fixed_contract_not_official(self):
        p=export_plan()
        self.assertEqual(p["payload_bytes"],312033188)
        self.assertEqual(p["canonical_tensors"],256)
        self.assertFalse(p["official_rpmodel_v1"])
        self.assertFalse(p["rust_deployable"])
        self.assertFalse(p["release_ready"])
        self.assertGreater(REQUIRED_BYTES,p["payload_bytes"]+p["asset_bytes"])
    def test_identity(self):
        self.assertTrue(valid_id("a"*64))
        for value in ("A"*64,"a"*63,None,"../weights",True):
            self.assertFalse(valid_id(value))
    def test_acknowledgment_and_budget_before_model_loading(self):
        # Torch is optional: inject its import to exercise early argument checks.
        from unittest.mock import patch,MagicMock
        import sys
        with tempfile.TemporaryDirectory() as tmp,patch.dict(sys.modules,{"safetensors":MagicMock(),"safetensors.torch":MagicMock()}):
            dest=Path(tmp)/"output"
            kwargs=dict(dataset_version="a"*64,license_label="internal-test-only",
                        rights_note="synthetic",max_bytes=REQUIRED_BYTES)
            with self.assertRaisesRegex(ValueError,"acknowledgment"):
                export_candidate("missing","missing",dest,**kwargs)
            kwargs["max_bytes"]=REQUIRED_BYTES-1
            with self.assertRaisesRegex(ValueError,"budget"):
                export_candidate("missing","missing",dest,acknowledge_candidate_only=True,**kwargs)
            self.assertFalse(dest.exists())
