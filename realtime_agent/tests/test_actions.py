import unittest

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


if __name__ == "__main__":
    unittest.main()
