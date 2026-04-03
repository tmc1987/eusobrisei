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
                return type("vm", (), {"percent": 50.0})

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
                                "memory_percent": 20.0,
                                "status": "running",
                                "create_time": 1.0,
                            }
                        )
                    ]
                )

            @staticmethod
            def sensors_temperatures():
                return {}

        with patch.object(collector_module, "psutil", PsutilStub()):
            c = Collector()
            snap = c.collect()
        self.assertEqual(len(snap["processes"]), 1)
        self.assertAlmostEqual(snap["processes"][0].cpu_percent, 30.0, places=2)


if __name__ == "__main__":
    unittest.main()
