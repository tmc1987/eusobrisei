import unittest

from agent.client_ai import build_client_guidance
from agent.models import Alert


class ClientAITests(unittest.TestCase):
    def test_memory_guidance_identifies_principal_and_secondary(self):
        alert = Alert(
            "HIGH_RAM",
            "high",
            "RAM alta",
            {
                "top_ram_processes": [
                    {"name": "chrome.exe", "memory_percent": 28.4},
                    {"name": "teams.exe", "memory_percent": 12.1},
                    {"name": "explorer.exe", "memory_percent": 3.0},
                ]
            },
        )
        cfg = {"processes": {"critical_names": ["explorer.exe"], "non_throttle_names": []}}

        guidance = build_client_guidance(alert, cfg)
        self.assertIn("Principal responsável: chrome.exe", guidance["message"])
        self.assertIn("teams.exe", guidance["safe_secondary_processes"])
        self.assertNotIn("explorer.exe", guidance["safe_secondary_processes"])
        self.assertTrue(any("abas" in s.lower() for s in guidance["suggestions"]))

    def test_cpu_guidance_returns_conversational_message(self):
        alert = Alert("HIGH_CPU", "high", "CPU alta", {"top_cpu_processes": [{"name": "python.exe", "cpu_percent": 65.0}]})
        guidance = build_client_guidance(alert, {"processes": {}})
        self.assertIn("CPU alta detectada", guidance["message"])
        self.assertEqual(guidance["principal_process"], "python.exe")


if __name__ == "__main__":
    unittest.main()
