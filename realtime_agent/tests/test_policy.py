import unittest

from agent.policy import apply_effective_policy


class PolicyTests(unittest.TestCase):
    def test_apply_effective_policy(self):
        base = {
            "thresholds": {"cpu_percent": 85, "ram_percent": 85, "disk_percent": 90, "temperature_c": 85},
            "actions": {"enabled": True, "safe_mode": True},
            "processes": {},
            "server": {},
        }
        policy = {
            "version": "device-v1",
            "thresholds": {"cpu_percent": 70},
            "actions": {
                "enabled": False,
                "safe_mode": False,
                "cooldown_seconds": 30,
                "restart_allowlist": ["notepad.exe"],
                "rate_limit": {"max_actions_per_hour": 10},
            },
        }
        merged = apply_effective_policy(base, policy)
        self.assertEqual(merged["thresholds"]["cpu_percent"], 70)
        self.assertFalse(merged["actions"]["enabled"])
        self.assertEqual(merged["actions"]["cooldown_seconds"], 30)
        self.assertEqual(merged["processes"]["restart_allowlist"], ["notepad.exe"])

    def test_fallback_when_remote_unavailable(self):
        base = {"thresholds": {"cpu_percent": 85}, "actions": {"enabled": True}, "processes": {}, "server": {}}
        merged = apply_effective_policy(base, None)
        self.assertEqual(merged["thresholds"]["cpu_percent"], 85)
        self.assertTrue(merged["actions"]["enabled"])


if __name__ == "__main__":
    unittest.main()
