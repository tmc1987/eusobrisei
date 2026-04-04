import unittest

from agent.models import Alert
from agent.rules import RuleEngine


class RuleEngineTests(unittest.TestCase):
    def test_generates_actions(self):
        engine = RuleEngine(
            {
                "actions": {
                    "safe_mode": True,
                    "allowed_priority_adjustments": True,
                    "auto_restart_hung_process": True,
                }
            }
        )

        alerts = [
            Alert("HIGH_CPU", "high", "CPU alto", {}),
            Alert("HIGH_RAM", "high", "RAM alta", {"top_ram_processes": [{"name": "chrome.exe", "pid": 10}], "probable_cause": "process_memory_pressure"}),
            Alert("HIGH_DISK", "medium", "Disco alto", {"top_disk_processes": [{"name": "backup.exe", "pid": 20}], "probable_cause": "disk_io_process_pressure"}),
            Alert("HIGH_TEMP", "critical", "Temp alta", {}),
            Alert("HUNG_PROCESS", "high", "Travou", {"pid": 10, "name": "notepad.exe"}),
        ]

        reqs = engine.evaluate(alerts, snapshot={"processes": []})
        actions = {r.action for r in reqs}

        self.assertIn("throttle_top_cpu_process", actions)
        self.assertIn("thermal_protect", actions)
        self.assertIn("restart_process", actions)

    def test_escalates_to_restart_on_recurrent_process_pressure(self):
        engine = RuleEngine(
            {
                "actions": {
                    "safe_mode": True,
                    "allowed_priority_adjustments": True,
                    "auto_restart_on_recurrence": True,
                    "allowed_actions": ["throttle_top_cpu_process", "restart_process", "thermal_protect"],
                },
                "processes": {"restart_allowlist": ["chrome.exe"]},
            }
        )
        alert = Alert(
            "HIGH_RAM",
            "high",
            "RAM alta",
            {"top_ram_processes": [{"name": "chrome.exe", "pid": 10}], "probable_cause": "process_memory_pressure"},
        )

        first = engine.evaluate([alert], snapshot={"processes": []})[0]
        second = engine.evaluate([alert], snapshot={"processes": []})[0]
        third = engine.evaluate([alert], snapshot={"processes": []})[0]

        self.assertEqual(first.action, "throttle_top_cpu_process")
        self.assertEqual(second.action, "throttle_top_cpu_process")
        self.assertEqual(third.action, "restart_process")
        self.assertEqual(third.strategy, "recurrence_restart")

    def test_uses_structural_guardrail_for_recurring_structural_pressure(self):
        engine = RuleEngine({"actions": {"allowed_actions": ["thermal_protect"]}})
        alert = Alert(
            "HIGH_DISK",
            "medium",
            "Disco alto",
            {"probable_cause": "structural_disk_pressure", "recurrence_hint": "recurring", "top_disk_processes": []},
        )

        req = engine.evaluate([alert], snapshot={"processes": []})[0]
        self.assertEqual(req.action, "thermal_protect")
        self.assertEqual(req.strategy, "structural_guardrail")

    def test_ranking_adapts_with_local_effectiveness_history(self):
        engine = RuleEngine(
            {
                "actions": {
                    "safe_mode": True,
                    "allowed_priority_adjustments": True,
                    "auto_restart_on_recurrence": True,
                    "allowed_actions": ["throttle_top_cpu_process", "restart_process", "thermal_protect"],
                },
                "processes": {"restart_allowlist": ["chrome.exe"]},
            }
        )
        alert = Alert(
            "HIGH_RAM",
            "high",
            "RAM alta",
            {
                "top_ram_processes": [{"name": "chrome.exe", "pid": 10}],
                "probable_cause": "process_memory_pressure",
                "recurrence_hint": "recurring",
            },
        )

        first = engine.evaluate([alert], snapshot={"processes": []})[0]
        self.assertEqual(first.action, "restart_process")
        self.assertTrue(first.params.get("strategy_ranking"))

        engine.record_action_feedback(first, "failed")
        engine.record_action_feedback(first, "failed")
        engine.record_action_feedback(first, "failed")

        second = engine.evaluate([alert], snapshot={"processes": []})[0]
        self.assertEqual(second.action, "throttle_top_cpu_process")

    def test_protected_process_uses_conservative_playbook(self):
        engine = RuleEngine(
            {
                "actions": {"allowed_actions": ["throttle_top_cpu_process", "restart_process", "thermal_protect"]},
                "processes": {"non_throttle_names": ["SystemSettings.exe"]},
            }
        )
        alert = Alert(
            "HIGH_RAM",
            "high",
            "RAM alta",
            {"top_ram_processes": [{"name": "SystemSettings.exe", "pid": 10}], "probable_cause": "process_memory_pressure"},
        )
        req = engine.evaluate([alert], snapshot={"processes": []})[0]
        self.assertEqual(req.action, "thermal_protect")
        self.assertEqual(req.params.get("process_class"), "protected_process")
        self.assertEqual(req.params.get("playbook_risk"), "low")

    def test_critical_service_blocks_restart_even_on_recurrence(self):
        engine = RuleEngine(
            {
                "actions": {
                    "auto_restart_on_recurrence": True,
                    "allowed_actions": ["throttle_top_cpu_process", "restart_process", "thermal_protect"],
                },
                "processes": {"critical_names": ["sqlservr.exe"], "restart_allowlist": ["sqlservr.exe"]},
            }
        )
        alert = Alert(
            "HIGH_RAM",
            "high",
            "RAM alta",
            {
                "top_ram_processes": [{"name": "sqlservr.exe", "pid": 99}],
                "probable_cause": "process_memory_pressure",
                "recurrence_hint": "recurring",
            },
        )
        req = engine.evaluate([alert], snapshot={"processes": []})[0]
        self.assertEqual(req.action, "thermal_protect")
        self.assertEqual(req.params.get("process_class"), "critical_service")


if __name__ == "__main__":
    unittest.main()
