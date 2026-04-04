from __future__ import annotations

from datetime import datetime, timezone
from typing import Dict, List
from uuid import uuid4


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def build_action_audit_batch(identity: Dict, audits: List[Dict]) -> Dict:
    actions = []
    for item in audits:
        actions.append(
            {
                "action_id": item.get("action_id", str(uuid4())),
                "trigger_event_id": item.get("trigger_event_id", str(uuid4())),
                "action_name": item["action_name"],
                "reason": item.get("reason", ""),
                "risk_level": item.get("risk_level", "medium"),
                "pre_state": item.get("pre_state", {}),
                "post_state": item.get("post_state", {}),
                "rollback_possible": item.get("rollback_possible", False),
                "rollback_executed": item.get("rollback_executed", False),
                "execution_status": item.get("execution_status", "success"),
                "error_message": item.get("error_message", ""),
                "occurred_at": item.get("occurred_at", now_iso()),
                "policy_version": item.get("policy_version", "local-fallback"),
            }
        )

    return {"batch_id": str(uuid4()), "actions": actions}
