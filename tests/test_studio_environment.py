import tempfile
from pathlib import Path
import unittest
from unittest.mock import patch
from rpdistill.studio_environment import deploy, PROFILES, child_env

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
