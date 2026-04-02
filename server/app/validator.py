from __future__ import annotations

from typing import Any, Dict, List, Tuple

from .contract_validator import validate_against_schema

VALID_SEVERITY = {"S0", "S1", "S2", "S3", "S4"}
VALID_EVENT_TYPES = {"ALERT", "ERROR", "POLICY_APPLIED", "AGENT_HEARTBEAT", "ACTION_REQUESTED"}


def validate_headers(headers: Dict[str, str], require_idempotency: bool) -> Tuple[bool, str]:
    required = ["X-Agent-Id", "X-Request-Id", "Authorization"]
    if require_idempotency:
        required.append("Idempotency-Key")
    missing = [h for h in required if not headers.get(h)]
    if missing:
        return False, f"missing_headers:{','.join(missing)}"
    return True, ""


def validate_bootstrap(payload: Dict[str, Any]) -> Tuple[bool, str]:
    return validate_against_schema(payload, "agent_bootstrap_request.json")


def validate_heartbeat(payload: Dict[str, Any]) -> Tuple[bool, str]:
    return validate_against_schema(payload, "heartbeat_request.json")


def validate_events_batch(payload: Dict[str, Any]) -> Tuple[bool, str, List[dict]]:
    ok, reason = validate_against_schema(payload, "events_batch_request.json")
    if not ok:
        return False, reason, []

    events = payload.get("events") or []
    rejected: List[dict] = []
    accepted = 0
    for ev in events:
        event_id = ev.get("event_id", "unknown")
        mandatory = ["event_id", "event_type", "severity", "occurred_at", "context"]
        if any(k not in ev for k in mandatory):
            rejected.append({"event_id": event_id, "reason": "missing_event_fields"})
            continue
        if ev["severity"] not in VALID_SEVERITY:
            rejected.append({"event_id": event_id, "reason": "invalid_severity"})
            continue
        if ev["event_type"] not in VALID_EVENT_TYPES:
            rejected.append({"event_id": event_id, "reason": "invalid_event_type"})
            continue
        accepted += 1

    if accepted == 0:
        return False, "no_valid_events", rejected
    return True, "", rejected


def validate_action_audit_batch(payload: Dict[str, Any]) -> Tuple[bool, str]:
    return validate_against_schema(payload, "action_audit_batch_request.json")


def validate_policy_document(payload: Dict[str, Any]) -> Tuple[bool, str]:
    return validate_against_schema(payload, "policy_document.json")
