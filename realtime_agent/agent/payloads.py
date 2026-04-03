from __future__ import annotations

from datetime import datetime, timezone
from typing import Dict, List
from uuid import uuid4

from .models import Alert


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def build_heartbeat(identity: Dict, queue_depth: int) -> Dict:
    return {
        "schema_version": "1.0",
        "tenant_id": identity["tenant_id"],
        "device_id": identity["device_id"],
        "agent_id": identity["agent_id"],
        "occurred_at": now_iso(),
        "agent_version": identity.get("agent_version", "0.1.0"),
        "queue_depth": queue_depth,
        "health": "ok",
    }


def build_events_batch(alerts: List[Alert]) -> Dict:
    severity_map = {"low": "S1", "medium": "S2", "high": "S3", "critical": "S4"}
    events = []
    for alert in alerts:
        events.append(
            {
                "event_id": str(uuid4()),
                "event_type": "ALERT",
                "severity": severity_map.get(alert.severity, "S2"),
                "occurred_at": now_iso(),
                "context": {"message": alert.message, **alert.context},
            }
        )
    return {"batch_id": str(uuid4()), "events": events}
