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
            Alert("HIGH_TEMP", "critical", "Temp alta", {}),
            Alert("HUNG_PROCESS", "high", "Travou", {"pid": 10, "name": "notepad.exe"}),
        ]

        reqs = engine.evaluate(alerts)
        actions = {r.action for r in reqs}

        self.assertIn("throttle_top_cpu_process", actions)
        self.assertIn("thermal_protect", actions)
        self.assertIn("restart_process", actions)


if __name__ == "__main__":
    unittest.main()
