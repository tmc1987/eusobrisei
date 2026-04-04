import unittest

from agent.slo import RemediationSLOTracker


class RemediationSLOTrackerTests(unittest.TestCase):
    def test_stabilized_without_human_updates_metrics(self):
        slo = RemediationSLOTracker()
        metrics = slo.observe(
            {"incident_id": "i1", "incident_state": "stabilized", "incident_open_for_seconds": 30},
            {"human_intervention_required": False, "evidence_complete": True},
        )
        self.assertEqual(metrics["stabilized_without_human_percent"], 100.0)
        self.assertEqual(metrics["mean_time_to_stabilize_seconds"], 30.0)

    def test_escalated_with_evidence_updates_metrics(self):
        slo = RemediationSLOTracker()
        metrics = slo.observe(
            {"incident_id": "i2", "incident_state": "escalated", "incident_open_for_seconds": 90},
            {"human_intervention_required": True, "evidence_complete": True},
        )
        self.assertEqual(metrics["escalated_with_complete_evidence_percent"], 100.0)
        self.assertEqual(metrics["escalated_incidents"], 1)


if __name__ == "__main__":
    unittest.main()
