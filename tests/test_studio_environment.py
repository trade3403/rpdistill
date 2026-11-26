import tempfile
from pathlib import Path
import unittest
from unittest.mock import patch
from rpdistill.studio_environment import deploy, recheck, PROFILES, child_env

class StudioEnvironmentTests(unittest.TestCase):
    def test_no_approval_no_write(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)/"env"
            with self.assertRaises(ValueError):
                deploy("python.exe","rpdistill.whl",root,"cpu")
            self.assertFalse(root.exists())
    def test_fixed_sources_and_clean_environment(self):
        self.assertEqual(set(PROFILES),{"cpu","cu128"})
        with patch.dict("os.environ",{"PIP_INDEX_URL":"https://invalid.example","PYTHONPATH":"unsafe"}):
            env=child_env()
            self.assertNotIn("PIP_INDEX_URL",env)
            self.assertNotIn("PYTHONPATH",env)

    def test_recheck_rejects_unapproved_and_invalid_id(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            with self.assertRaises(ValueError):
                recheck(root/"wheel",root,"a"*32)
            with patch("rpdistill.studio_environment.sys.platform","win32"):
                with self.assertRaises(ValueError):
                    recheck(root/"wheel",root,"../bad",approved=True)
            self.assertEqual(list(root.iterdir()),[])
