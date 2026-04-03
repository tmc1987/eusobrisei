import unittest
from unittest.mock import patch

from agent import collector as collector_module
from agent.collector import Collector


class CollectorTests(unittest.TestCase):
    def test_normalizes_process_cpu_to_task_manager_scale(self):
        class P:
            def __init__(self, info):
                self.info = info

            def io_counters(self):
                return None

            def cpu_percent(self, interval=None):
                return self.info.get("cpu_percent", 0.0)

            def as_dict(self, attrs=None):
                return {k: self.info.get(k) for k in (attrs or self.info.keys())}

            def memory_info(self):
                return type("mi", (), {"rss": self.info.get("rss", 0)})

        class PsutilStub:
            NoSuchProcess = RuntimeError
            AccessDenied = PermissionError

            @staticmethod
            def cpu_count(logical=True):
                return 8

            @staticmethod
            def cpu_percent(interval=None):
                return 25.0

            @staticmethod
            def virtual_memory():
                return type("vm", (), {"percent": 50.0, "total": 8_000_000_000})

            @staticmethod
            def disk_usage(path):
                return type("du", (), {"percent": 60.0})

            @staticmethod
            def process_iter(attrs):
                return iter(
                    [
                        P(
                            {
                                "pid": 10,
                                "name": "chrome.exe",
                                "cpu_percent": 240.0,
                                "rss": 2_000_000_000,
                                "status": "running",
                                "create_time": 1.0,
                            }
                        )
                    ]
                )

            @staticmethod
            def sensors_temperatures():
                return {}

        with patch.object(collector_module, "psutil", PsutilStub()), patch("agent.collector.time.sleep", return_value=None):
            c = Collector()
            snap = c.collect()
        self.assertEqual(len(snap["processes"]), 1)
        self.assertAlmostEqual(snap["processes"][0].cpu_percent, 30.0, places=2)
        self.assertAlmostEqual(snap["processes"][0].memory_percent, 25.0, places=2)

    def test_hung_detection_prefers_windows_api(self):
        c = Collector.__new__(Collector)
        with patch("agent.collector.platform.system", return_value="Windows"), patch.object(
            Collector, "_get_hung_processes_windows_api", return_value=[100, 200]
        ):
            result = Collector._get_hung_processes_windows(c)
        self.assertEqual(result, [100, 200])

    def test_hung_detection_falls_back_to_powershell_when_api_unavailable(self):
        c = Collector.__new__(Collector)
        fake = type("res", (), {"stdout": "2604\n3000\n"})
        with patch("agent.collector.platform.system", return_value="Windows"), patch.object(
            Collector, "_get_hung_processes_windows_api", return_value=None
        ), patch("agent.collector.subprocess.run", return_value=fake):
            result = Collector._get_hung_processes_windows(c)
        self.assertEqual(result, [2604, 3000])


if __name__ == "__main__":
    unittest.main()
