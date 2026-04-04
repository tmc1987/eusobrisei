import unittest
from unittest.mock import patch

from agent.analyzer import Analyzer
from agent.models import ProcessSample


class AnalyzerTests(unittest.TestCase):
    def test_threshold_alerts(self):
        analyzer = Analyzer(
            {
                "cpu_percent": 80,
                "ram_percent": 80,
                "disk_percent": 90,
                "temperature_c": 75,
                "hung_process_seconds": 60,
            }
        )

        snapshot = {
            "cpu_percent": 90,
            "ram_percent": 85,
            "disk_percent": 91,
            "temperature_c": 80,
            "hung_processes": [123],
            "processes": [
                ProcessSample(123, "app.exe", 1.0, 1.0, "running", 0.0),
            ],
        }

        alerts = analyzer.analyze(snapshot)
        codes = {a.code for a in alerts}

        self.assertIn("HIGH_CPU", codes)
        self.assertIn("HIGH_RAM", codes)
        self.assertIn("HIGH_DISK", codes)
        self.assertIn("HIGH_TEMP", codes)
        self.assertIn("HUNG_PROCESS", codes)

    def test_high_ram_contains_top_process_context(self):
        analyzer = Analyzer({"cpu_percent": 95, "ram_percent": 70, "disk_percent": 99, "temperature_c": 120})
        snapshot = {
            "cpu_percent": 20,
            "ram_percent": 82,
            "disk_percent": 10,
            "temperature_c": 30,
            "hung_processes": [],
            "processes": [
                ProcessSample(1, "chrome.exe", 10.0, 22.0, "running", 0.0),
                ProcessSample(2, "editor.exe", 5.0, 18.0, "running", 0.0),
            ],
        }
        alerts = analyzer.analyze(snapshot)
        ram = [a for a in alerts if a.code == "HIGH_RAM"][0]
        self.assertIn("top_ram_processes", ram.context)
        self.assertEqual(ram.context["top_ram_processes"][0]["name"], "chrome.exe")

    def test_high_disk_contains_top_io_process_context(self):
        analyzer = Analyzer({"cpu_percent": 95, "ram_percent": 95, "disk_percent": 70, "temperature_c": 120})
        snapshot = {
            "cpu_percent": 10,
            "ram_percent": 20,
            "disk_percent": 82,
            "temperature_c": 30,
            "hung_processes": [],
            "processes": [
                ProcessSample(1, "backup.exe", 1.0, 2.0, "running", 0.0, io_read_bytes=1000, io_write_bytes=9_000_000),
                ProcessSample(2, "chrome.exe", 2.0, 8.0, "running", 0.0, io_read_bytes=500, io_write_bytes=2000),
            ],
        }
        alerts = analyzer.analyze(snapshot)
        disk = [a for a in alerts if a.code == "HIGH_DISK"][0]
        self.assertIn("top_disk_processes", disk.context)
        self.assertEqual(disk.context["top_disk_processes"][0]["name"], "backup.exe")

    def test_hung_process_alert_uses_adaptive_backoff_to_avoid_infinite_loop_noise(self):
        analyzer = Analyzer(
            {
                "cpu_percent": 95,
                "ram_percent": 95,
                "disk_percent": 95,
                "temperature_c": 120,
                "hung_emit_interval_seconds": 60,
                "hung_emit_backoff_factor": 2.0,
                "hung_emit_max_interval_seconds": 300,
            }
        )
        snapshot = {
            "cpu_percent": 10,
            "ram_percent": 20,
            "disk_percent": 10,
            "temperature_c": 30,
            "hung_processes": [2604],
            "processes": [ProcessSample(2604, "SystemSettings.exe", 0.5, 1.0, "running", 0.0)],
        }
        with patch("agent.analyzer.time.time", side_effect=[100.0, 110.0, 170.0, 230.0]):
            first = analyzer.analyze(snapshot)
            second = analyzer.analyze(snapshot)
            third = analyzer.analyze(snapshot)
            fourth = analyzer.analyze(snapshot)
        self.assertEqual(len([a for a in first if a.code == "HUNG_PROCESS"]), 1)
        self.assertEqual(len([a for a in second if a.code == "HUNG_PROCESS"]), 0)
        self.assertEqual(len([a for a in third if a.code == "HUNG_PROCESS"]), 0)
        self.assertEqual(len([a for a in fourth if a.code == "HUNG_PROCESS"]), 1)
        emitted = [a for a in fourth if a.code == "HUNG_PROCESS"][0]
        self.assertGreaterEqual(emitted.context.get("next_emit_in_seconds", 0), 120)


if __name__ == "__main__":
    unittest.main()
