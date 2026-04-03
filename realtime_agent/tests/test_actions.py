import unittest
from unittest.mock import patch

from agent import actions
from agent.actions import ActionExecutor
from agent.rules import ActionRequest, RuleEngine
from agent.models import Alert


class ActionExecutorTests(unittest.TestCase):
    def test_suppresses_repeated_ineffective_action(self):
        cfg = {
            "actions": {"cooldown_seconds": 0},
            "processes": {"critical_names": [], "restart_allowlist": ["notepad.exe"], "restart_commands": {}},
        }
        ex = ActionExecutor(cfg)
        req = ActionRequest(
            action="restart_process",
            reason="hung",
            params={"name": "notepad.exe", "pid": 1},
            severity="high",
            recurrence_count=3,
            human_recommendation="investigar manualmente",
        )

        r1 = ex.execute([req], {"processes": []})[0]
        r2 = ex.execute([req], {"processes": []})[0]
        r3 = ex.execute([req], {"processes": []})[0]

        self.assertFalse(r1.success)
        self.assertFalse(r2.success)
        self.assertFalse(r3.success)
        self.assertIn("suprimida", r3.message.lower())

    def test_rule_engine_adds_recurrence_and_recommendation(self):
        engine = RuleEngine({"actions": {"allowed_priority_adjustments": True, "safe_mode": True}})
        alerts = [Alert("HIGH_CPU", "high", "cpu alta", {})]
        req1 = engine.evaluate(alerts, snapshot={"processes": []})[0]
        req2 = engine.evaluate(alerts, snapshot={"processes": []})[0]
        self.assertEqual(req1.recurrence_count, 1)
        self.assertEqual(req2.recurrence_count, 2)
        self.assertTrue(req2.human_recommendation)

    def test_throttle_skips_blocked_process_and_uses_next_candidate(self):
        class P:
            def __init__(self, pid):
                self.pid = pid

            def nice(self, value=None):
                return 10 if value is None else None

        class PsutilStub:
            BELOW_NORMAL_PRIORITY_CLASS = 10
            NoSuchProcess = RuntimeError
            AccessDenied = PermissionError

            @staticmethod
            def Process(pid):
                return P(pid)

        cfg = {
            "actions": {"cooldown_seconds": 0, "allowed_actions": ["throttle_top_cpu_process"]},
            "processes": {"critical_names": [], "non_throttle_names": ["SystemSettings.exe"], "restart_allowlist": [], "restart_commands": {}},
        }
        ex = ActionExecutor(cfg)
        req = ActionRequest(action="throttle_top_cpu_process", reason="cpu alta", params={"target_name": "SystemSettings.exe"}, severity="high")
        snapshot = {
            "processes": [
                type("Proc", (), {"pid": 10, "name": "SystemSettings.exe", "cpu_percent": 80, "memory_percent": 5, "io_read_bytes": 0, "io_write_bytes": 0}),
                type("Proc", (), {"pid": 11, "name": "chrome.exe", "cpu_percent": 40, "memory_percent": 10, "io_read_bytes": 0, "io_write_bytes": 0}),
            ]
        }
        with patch.object(actions, "psutil", PsutilStub()):
            result = ex.execute([req], snapshot)[0]
        self.assertTrue(result.success)
        self.assertIn("chrome.exe", result.message.lower())

    def test_throttle_failure_uses_thermal_fallback_when_enabled(self):
        cfg = {
            "actions": {"cooldown_seconds": 0, "allowed_actions": ["throttle_top_cpu_process", "thermal_protect"]},
            "processes": {"critical_names": ["chrome.exe"], "restart_allowlist": [], "restart_commands": {}},
        }
        ex = ActionExecutor(cfg)
        req = ActionRequest(action="throttle_top_cpu_process", reason="cpu alta", params={"target_name": "chrome.exe"}, severity="high")
        snapshot = {
            "processes": [
                type("Proc", (), {"pid": 11, "name": "chrome.exe", "cpu_percent": 40, "memory_percent": 10, "io_read_bytes": 0, "io_write_bytes": 0}),
            ]
        }
        with patch.object(ActionExecutor, "_thermal_protect", return_value=actions.ActionResult("thermal_protect", True, "ok", outcome="mitigated")):
            result = ex.execute([req], snapshot)[0]
        self.assertTrue(result.success)
        self.assertEqual(result.action, "thermal_protect")
        self.assertIn("fallback", result.message.lower())

    def test_failure_contains_structured_error_category(self):
        cfg = {
            "actions": {"cooldown_seconds": 0},
            "processes": {"critical_names": [], "restart_allowlist": ["notepad.exe"], "restart_commands": {}},
        }
        ex = ActionExecutor(cfg)
        req = ActionRequest(action="restart_process", reason="hung", params={"name": "chrome.exe", "pid": 1}, severity="high")
        result = ex.execute([req], {"processes": []})[0]
        self.assertFalse(result.success)
        self.assertEqual((result.evidence or {}).get("error_category"), "policy_blocked")
        self.assertIn("allowlist", (result.evidence or {}).get("block_reason", "").lower())

    def test_throttle_failure_can_escalate_to_restart_on_recurrence(self):
        cfg = {
            "actions": {
                "cooldown_seconds": 0,
                "allowed_actions": ["throttle_top_cpu_process", "restart_process"],
                "auto_restart_on_recurrence": True,
            },
            "processes": {"critical_names": [], "restart_allowlist": ["chrome.exe"], "restart_commands": {"chrome.exe": "start chrome.exe"}},
        }
        ex = ActionExecutor(cfg)
        req = ActionRequest(
            action="throttle_top_cpu_process",
            reason="cpu alta",
            params={"target_name": "chrome.exe", "target_pid": 123},
            severity="high",
            recurrence_count=3,
        )
        snapshot = {"processes": []}
        with patch.object(ActionExecutor, "_throttle_top_cpu_process", return_value=actions.ActionResult("throttle_top_cpu_process", False, "falhou", outcome="failed")), patch.object(
            ActionExecutor, "_restart_process", return_value=actions.ActionResult("restart_process", True, "reiniciado", outcome="resolved")
        ):
            result = ex.execute([req], snapshot)[0]
        self.assertTrue(result.success)
        self.assertEqual(result.action, "restart_process")
        self.assertIn("fallback de recorrência", result.message.lower())


if __name__ == "__main__":
    unittest.main()
