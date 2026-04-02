import unittest

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


if __name__ == "__main__":
    unittest.main()
