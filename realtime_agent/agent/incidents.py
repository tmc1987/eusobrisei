from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Dict
from uuid import uuid4


@dataclass
class IncidentRecord:
    incident_id: str
    state: str
    opened_at: float
    last_seen_at: float
    recurrence_count: int = 1
    failed_actions: int = 0
    attempts_used: int = 0
    action_budget: int = 3


class IncidentStateMachine:
    """
    Estado operacional por incidente para evitar tratamento isolado por ciclo.
    Estados: open -> mitigating -> stabilized | escalated
    """

    def __init__(self, escalation_after_failures: int = 3, action_budget_per_incident: int = 3):
        self._records: Dict[str, IncidentRecord] = {}
        self._escalation_after_failures = max(1, int(escalation_after_failures))
        self._action_budget_per_incident = max(1, int(action_budget_per_incident))

    def observe(self, signature: str) -> Dict:
        now = time.time()
        rec = self._records.get(signature)
        if not rec:
            rec = IncidentRecord(
                incident_id=str(uuid4()),
                state="open",
                opened_at=now,
                last_seen_at=now,
                recurrence_count=1,
                action_budget=self._action_budget_per_incident,
            )
            self._records[signature] = rec
        else:
            rec.last_seen_at = now
            rec.recurrence_count += 1
            if rec.state == "stabilized":
                rec.state = "open"

        return {
            "incident_id": rec.incident_id,
            "incident_state": rec.state,
            "incident_recurrence_count": rec.recurrence_count,
            "incident_open_for_seconds": round(now - rec.opened_at, 1),
            "incident_attempts_used": rec.attempts_used,
            "incident_action_budget": rec.action_budget,
            "incident_budget_remaining": max(rec.action_budget - rec.attempts_used, 0),
        }

    def apply_action_result(self, signature: str, execution_status: str) -> Dict:
        now = time.time()
        rec = self._records.get(signature)
        if not rec:
            rec = IncidentRecord(
                incident_id=str(uuid4()),
                state="open",
                opened_at=now,
                last_seen_at=now,
                action_budget=self._action_budget_per_incident,
            )
            self._records[signature] = rec

        rec.last_seen_at = now
        rec.attempts_used += 1
        status = (execution_status or "").lower()
        if status == "success":
            rec.state = "stabilized"
            rec.failed_actions = 0
        elif status == "partial":
            rec.state = "mitigating"
        else:
            rec.failed_actions += 1
            budget_exhausted = rec.attempts_used >= rec.action_budget
            rec.state = "escalated" if (rec.failed_actions >= self._escalation_after_failures or budget_exhausted) else "mitigating"

        return {
            "incident_id": rec.incident_id,
            "incident_state": rec.state,
            "incident_recurrence_count": rec.recurrence_count,
            "incident_failed_actions": rec.failed_actions,
            "incident_open_for_seconds": round(now - rec.opened_at, 1),
            "incident_attempts_used": rec.attempts_used,
            "incident_action_budget": rec.action_budget,
            "incident_budget_remaining": max(rec.action_budget - rec.attempts_used, 0),
        }
