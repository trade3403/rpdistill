import json
import subprocess
import sys
import unittest

from rpdistill import __version__
from rpdistill.config import TrainingConfig
from rpdistill.__main__ import runtime_info


class BootstrapTests(unittest.TestCase):
    def test_version(self):
        self.assertEqual(__version__, "0.1.0")

    def test_runtime_info(self):
        self.assertEqual(runtime_info()["stage"], "E3.3a")

    def test_cli(self):
        result = subprocess.run(
            [sys.executable, "-m", "rpdistill"],
            capture_output=True, text=True, check=True,
        )
        self.assertEqual(json.loads(result.stdout)["application"], "RPDistill")

    def test_valid_config(self):
        config = TrainingConfig("teacher", "student")
        self.assertEqual(config.batch_size, 8)

    def test_invalid_config(self):
        for kwargs in (
            {"teacher": ""}, {"student": " "}, {"batch_size": 0},
            {"batch_size": True}, {"epochs": -1}, {"epochs": 1.5},
            {"learning_rate": float("nan")}, {"learning_rate": float("inf")},
            {"learning_rate": 0}, {"seed": -1}, {"seed": 2**32},
        ):
            with self.subTest(kwargs=kwargs), self.assertRaises(ValueError):
                TrainingConfig(**({"teacher": "teacher", "student": "student"} | kwargs))


if __name__ == "__main__":
    unittest.main()
