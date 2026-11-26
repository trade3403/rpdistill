import subprocess
import unittest
from unittest.mock import patch

from rpdistill.devices import device_report, nvidia_info


class DeviceTests(unittest.TestCase):
    @patch("rpdistill.devices.shutil.which", return_value=None)
    def test_cpu_only(self, _):
        report = device_report()
        self.assertEqual(report["nvidia"]["status"], "unavailable")
        self.assertGreater(report["disk"]["total_bytes"], 0)

    @patch("rpdistill.devices.shutil.which", return_value="nvidia-smi")
    @patch("rpdistill.devices.subprocess.run")
    def test_parse_gpu(self, run, _):
        run.return_value.stdout = "0, GPU test, 8192, 4096\n"
        self.assertEqual(nvidia_info()["devices"][0]["free_mib"], 4096)
        self.assertEqual(run.call_args.kwargs["timeout"], 5)

    @patch("rpdistill.devices.shutil.which", return_value="nvidia-smi")
    @patch("rpdistill.devices.subprocess.run", side_effect=subprocess.TimeoutExpired("nvidia-smi", 5))
    def test_probe_timeout(self, *_):
        self.assertEqual(nvidia_info()["status"], "probe_failed")

    @patch("rpdistill.devices.shutil.which", return_value="nvidia-smi")
    @patch("rpdistill.devices.subprocess.run")
    def test_malformed_gpu(self, run, _):
        run.return_value.stdout = "bad output"
        self.assertEqual(nvidia_info()["status"], "probe_failed")

    @patch("rpdistill.devices.shutil.which", return_value="nvidia-smi")
    @patch("rpdistill.devices.subprocess.run")
    def test_optional_gpu_metrics(self,run,_):
        run.return_value.stdout="0, GPU test, 8192, 4096, 72, 61, 140.5\n1, GPU old, 4096, 3000, N/A, [Not Supported], NaN\n"
        a,b=nvidia_info()["devices"]
        self.assertEqual((a["utilization_percent"],a["temperature_c"],a["power_w"]),(72,61,140.5))
        self.assertIsNone(b["utilization_percent"])
        self.assertIsNone(b["temperature_c"])
        self.assertIsNone(b["power_w"])
