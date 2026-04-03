from __future__ import annotations

from typing import Dict


class RemediationSLOTracker:
    """Métricas locais de SLO para remediação automática por incidente."""

    def __init__(self) -> None:
        self._incident_state: Dict[str, str] = {}
        self._closed_incidents = 0
        self._stabilized_without_human = 0
        self._escalated_incidents = 0
        self._escalated_with_complete_evidence = 0
        self._stabilized_count = 0
        self._sum_seconds_to_stabilize = 0.0

    def observe(self, incident: Dict, execution_context: Dict) -> Dict:
        incident_id = str(incident.get("incident_id", ""))
        state = str(incident.get("incident_state", "open"))
        open_for = float(incident.get("incident_open_for_seconds", 0.0) or 0.0)

        previous = self._incident_state.get(incident_id)
        if incident_id:
            self._incident_state[incident_id] = state

        if state == "stabilized" and previous != "stabilized":
            self._closed_incidents += 1
            self._stabilized_count += 1
            self._sum_seconds_to_stabilize += open_for
            if not execution_context.get("human_intervention_required", False):
                self._stabilized_without_human += 1

        if state == "escalated" and previous != "escalated":
            self._closed_incidents += 1
            self._escalated_incidents += 1
            if execution_context.get("evidence_complete", False):
                self._escalated_with_complete_evidence += 1

        return self.snapshot()

    def snapshot(self) -> Dict:
        stabilized_pct = (100.0 * self._stabilized_without_human / self._closed_incidents) if self._closed_incidents else 0.0
        mean_seconds = (self._sum_seconds_to_stabilize / self._stabilized_count) if self._stabilized_count else 0.0
        escalated_pct = (
            100.0 * self._escalated_with_complete_evidence / self._escalated_incidents
            if self._escalated_incidents
            else 0.0
        )
        return {
            "stabilized_without_human_percent": round(stabilized_pct, 2),
            "mean_time_to_stabilize_seconds": round(mean_seconds, 2),
            "escalated_with_complete_evidence_percent": round(escalated_pct, 2),
            "closed_incidents": self._closed_incidents,
            "stabilized_incidents": self._stabilized_count,
            "escalated_incidents": self._escalated_incidents,
        }
