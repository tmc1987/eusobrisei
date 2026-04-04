from __future__ import annotations

import unittest

from agent.incidents import IncidentStateMachine


class IncidentStateMachineTests(unittest.TestCase):
    def test_recurrence_keeps_same_incident_id(self):
        sm = IncidentStateMachine(escalation_after_failures=2)
        first = sm.observe("HIGH_RAM|pid=10")
        second = sm.observe("HIGH_RAM|pid=10")

        self.assertEqual(first["incident_id"], second["incident_id"])
        self.assertEqual(second["incident_recurrence_count"], 2)
        self.assertEqual(second["incident_state"], "open")

    def test_failures_escalate_after_threshold(self):
        sm = IncidentStateMachine(escalation_after_failures=2)
        sm.observe("HIGH_CPU|name=python")

        first_fail = sm.apply_action_result("HIGH_CPU|name=python", "failed")
        second_fail = sm.apply_action_result("HIGH_CPU|name=python", "failed")

        self.assertEqual(first_fail["incident_state"], "mitigating")
        self.assertEqual(second_fail["incident_state"], "escalated")
        self.assertEqual(second_fail["incident_failed_actions"], 2)

    def test_success_stabilizes_and_resets_failures(self):
        sm = IncidentStateMachine(escalation_after_failures=2)
        sm.observe("HIGH_DISK|resource=disk")
        sm.apply_action_result("HIGH_DISK|resource=disk", "failed")
        stabilized = sm.apply_action_result("HIGH_DISK|resource=disk", "success")

        self.assertEqual(stabilized["incident_state"], "stabilized")
        self.assertEqual(stabilized["incident_failed_actions"], 0)

    def test_budget_exhaustion_escalates_incident(self):
        sm = IncidentStateMachine(escalation_after_failures=10, action_budget_per_incident=2)
        sm.observe("HIGH_CPU|name=python")
        first = sm.apply_action_result("HIGH_CPU|name=python", "failed")
        second = sm.apply_action_result("HIGH_CPU|name=python", "failed")

        self.assertEqual(first["incident_state"], "mitigating")
        self.assertEqual(second["incident_state"], "escalated")
        self.assertEqual(second["incident_attempts_used"], 2)
        self.assertEqual(second["incident_action_budget"], 2)
        self.assertEqual(second["incident_budget_remaining"], 0)


if __name__ == "__main__":
    unittest.main()
