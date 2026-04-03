from __future__ import annotations

import json
from datetime import datetime, timezone
from http import HTTPStatus
from typing import Dict, Tuple
from uuid import uuid4

from .config import get_settings
from .db import get_db
from .validator import (
    validate_action_audit_batch,
    validate_bootstrap,
    validate_events_batch,
    validate_headers,
    validate_heartbeat,
    validate_policy_document,
)


def _parse_json(body: bytes):
    try:
        return json.loads(body.decode("utf-8")) if body else {}
    except json.JSONDecodeError:
        return None


def _is_authorized(headers: Dict[str, str]) -> bool:
    agent_id = headers.get("X-Agent-Id", "")
    auth = headers.get("Authorization", "")
    if not auth.startswith("Bearer "):
        return False
    token = auth.replace("Bearer ", "", 1).strip()
    expected = get_db(get_settings().db_path).get_agent_token(agent_id)
    return bool(expected and token == expected)


def healthcheck(_: bytes, __: Dict[str, str]) -> Tuple[int, Dict]:
    return HTTPStatus.OK, {"status": "ok", "service": "server-scaffold", "phase": "3", "db": get_settings().db_path}


def bootstrap_agent(body: bytes, headers: Dict[str, str]) -> Tuple[int, Dict]:
    payload = _parse_json(body)
    if payload is None:
        return HTTPStatus.BAD_REQUEST, {"error": "invalid_json"}

    ok, reason = validate_bootstrap(payload)
    if not ok:
        return HTTPStatus.BAD_REQUEST, {"error": reason}

    if payload.get("activation_token") != get_settings().bootstrap_token:
        return HTTPStatus.UNAUTHORIZED, {"error": "invalid_activation_token"}

    tenant_id = "00000000-0000-0000-0000-000000000001"
    device_id = str(uuid4())
    created = get_db(get_settings().db_path).bootstrap_agent(
        tenant_id=tenant_id,
        device_id=device_id,
        hostname=payload.get("hostname", "unknown"),
        os_version=payload.get("os_version", "unknown"),
        agent_version=payload.get("agent_version", "0.1.0"),
    )
    expires_at = datetime.fromtimestamp(created["expires_at"], tz=timezone.utc).isoformat()
    return (
        HTTPStatus.CREATED,
        {
            "agent_id": created["agent_id"],
            "device_id": device_id,
            "tenant_id": tenant_id,
            "access_token": created["access_token"],
            "expires_at": expires_at,
            "mtls": {"required": False},
        },
    )


def resolve_policy(_: bytes, headers: Dict[str, str]) -> Tuple[int, Dict]:
    ok, reason = validate_headers(headers, require_idempotency=False)
    if not ok:
        return HTTPStatus.BAD_REQUEST, {"error": reason}
    if not _is_authorized(headers):
        return HTTPStatus.UNAUTHORIZED, {"error": "unauthorized"}

    try:
        doc = get_db(get_settings().db_path).resolve_policy_for_agent(headers["X-Agent-Id"])
    except ValueError:
        return HTTPStatus.NOT_FOUND, {"error": "agent_not_found"}

    return HTTPStatus.OK, doc


def dev_upsert_policy(body: bytes, headers: Dict[str, str]) -> Tuple[int, Dict]:
    """Endpoint provisório de desenvolvimento para cadastrar política sem painel."""
    payload = _parse_json(body)
    if payload is None:
        return HTTPStatus.BAD_REQUEST, {"error": "invalid_json"}

    ok, reason = validate_policy_document(payload)
    if not ok:
        return HTTPStatus.BAD_REQUEST, {"error": reason}

    get_db(get_settings().db_path).upsert_policy(payload)
    return HTTPStatus.CREATED, {"status": "stored", "policy_id": payload.get("policy_id"), "version": payload.get("version")}


def policies_list(_: bytes, __: Dict[str, str], query: Dict[str, str]) -> Tuple[int, Dict]:
    tenant_id = query.get("tenant_id")
    group_id = query.get("group_id")
    device_id = query.get("device_id")
    status = query.get("status", "").lower()
    rows = get_db(get_settings().db_path).list_policies()
    items = []
    for p in rows:
        scope = p.get("scope", {})
        meta = p.get("meta", {})
        if tenant_id and scope.get("tenant_id") != tenant_id:
            continue
        if group_id and scope.get("group_id") != group_id:
            continue
        if device_id and scope.get("device_id") != device_id:
            continue
        is_active = bool(meta.get("is_active"))
        if status == "active" and not is_active:
            continue
        if status == "disabled" and is_active:
            continue
        items.append(
            {
                "policy_id": p.get("policy_id"),
                "version": p.get("version"),
                "version_no": meta.get("version_no"),
                "updated_at": meta.get("updated_at"),
                "scope": scope,
                "status": "active" if is_active else "disabled",
            }
        )
    return HTTPStatus.OK, {"items": items}


def policy_detail(policy_id: str) -> Tuple[int, Dict]:
    item = get_db(get_settings().db_path).get_policy(policy_id)
    if not item:
        return HTTPStatus.NOT_FOUND, {"error": "policy_not_found"}
    return HTTPStatus.OK, item


def policy_create(body: bytes, headers: Dict[str, str]) -> Tuple[int, Dict]:
    payload = _parse_json(body)
    if payload is None:
        return HTTPStatus.BAD_REQUEST, {"error": "invalid_json"}
    if "policy_id" not in payload:
        payload["policy_id"] = str(uuid4())
    ok, reason = validate_policy_document(payload)
    if not ok:
        return HTTPStatus.BAD_REQUEST, {"error": reason}
    actor = headers.get("X-Dev-Actor", "web-console")
    created = get_db(get_settings().db_path).create_policy(payload, actor=actor, reason="web-console-create")
    return HTTPStatus.CREATED, {"status": "created", "policy_id": created.get("policy_id"), "version": created.get("version")}


def policy_update(policy_id: str, body: bytes, headers: Dict[str, str]) -> Tuple[int, Dict]:
    payload = _parse_json(body)
    if payload is None:
        return HTTPStatus.BAD_REQUEST, {"error": "invalid_json"}
    current = get_db(get_settings().db_path).get_policy(policy_id)
    if not current:
        return HTTPStatus.NOT_FOUND, {"error": "policy_not_found"}
    merged = json.loads(json.dumps(current))
    merged.pop("meta", None)
    merged.update(payload)
    merged["policy_id"] = policy_id
    ok, reason = validate_policy_document(merged)
    if not ok:
        return HTTPStatus.BAD_REQUEST, {"error": reason}
    actor = headers.get("X-Dev-Actor", "web-console")
    updated = get_db(get_settings().db_path).update_policy(policy_id, payload, actor=actor, reason="web-console-edit")
    if not updated:
        return HTTPStatus.NOT_FOUND, {"error": "policy_not_found"}
    return HTTPStatus.OK, {"status": "updated", "policy_id": updated.get("policy_id"), "version": updated.get("version")}


def policy_disable(policy_id: str, headers: Dict[str, str]) -> Tuple[int, Dict]:
    actor = headers.get("X-Dev-Actor", "web-console")
    ok = get_db(get_settings().db_path).disable_policy(policy_id, actor=actor, reason="web-console-disable")
    if not ok:
        return HTTPStatus.NOT_FOUND, {"error": "policy_not_found"}
    return HTTPStatus.OK, {"status": "disabled", "policy_id": policy_id}


def policy_audit_list(_: bytes, __: Dict[str, str], query: Dict[str, str]) -> Tuple[int, Dict]:
    policy_id = query.get("policy_id")
    rows = get_db(get_settings().db_path).list_policy_audit(policy_id)
    items = []
    for r in rows:
        items.append(
            {
                "id": r.get("id"),
                "policy_id": r.get("policy_id"),
                "actor": r.get("actor"),
                "action": r.get("action"),
                "reason": r.get("reason"),
                "scope": json.loads(r["scope"]) if r.get("scope") else {},
                "created_at": r.get("created_at"),
            }
        )
    return HTTPStatus.OK, {"items": items}


def heartbeat_ingest(body: bytes, headers: Dict[str, str]) -> Tuple[int, Dict]:
    ok, reason = validate_headers(headers, require_idempotency=False)
    if not ok:
        return HTTPStatus.BAD_REQUEST, {"error": reason}
    if not _is_authorized(headers):
        return HTTPStatus.UNAUTHORIZED, {"error": "unauthorized"}

    payload = _parse_json(body)
    if payload is None:
        return HTTPStatus.BAD_REQUEST, {"error": "invalid_json"}

    ok, reason = validate_heartbeat(payload)
    if not ok:
        return HTTPStatus.BAD_REQUEST, {"error": reason}

    get_db(get_settings().db_path).save_heartbeat(headers["X-Agent-Id"], payload)
    return HTTPStatus.ACCEPTED, {"status": "accepted"}


def events_batch_ingest(body: bytes, headers: Dict[str, str]) -> Tuple[int, Dict]:
    ok, reason = validate_headers(headers, require_idempotency=True)
    if not ok:
        return HTTPStatus.BAD_REQUEST, {"error": reason}
    if not _is_authorized(headers):
        return HTTPStatus.UNAUTHORIZED, {"error": "unauthorized"}

    payload = _parse_json(body)
    if payload is None:
        return HTTPStatus.BAD_REQUEST, {"error": "invalid_json"}

    agent_id = headers["X-Agent-Id"]
    idempotency_key = headers["Idempotency-Key"]
    cached = get_db(get_settings().db_path).get_idempotent_response(agent_id, idempotency_key)
    if cached:
        return HTTPStatus.ACCEPTED, cached

    ok, reason, rejected = validate_events_batch(payload)
    if not ok:
        return HTTPStatus.BAD_REQUEST, {"error": reason, "rejected": rejected}

    accepted = len(payload.get("events", [])) - len(rejected)
    response = {"batch_id": payload.get("batch_id"), "accepted": accepted, "rejected": rejected}
    get_db(get_settings().db_path).save_event_batch(payload.get("batch_id"), agent_id, payload, accepted, len(rejected))
    get_db(get_settings().db_path).save_idempotent_response(agent_id, idempotency_key, response)
    return HTTPStatus.ACCEPTED, response


def action_audit_batch_ingest(body: bytes, headers: Dict[str, str]) -> Tuple[int, Dict]:
    ok, reason = validate_headers(headers, require_idempotency=True)
    if not ok:
        return HTTPStatus.BAD_REQUEST, {"error": reason}
    if not _is_authorized(headers):
        return HTTPStatus.UNAUTHORIZED, {"error": "unauthorized"}

    payload = _parse_json(body)
    if payload is None:
        return HTTPStatus.BAD_REQUEST, {"error": "invalid_json"}

    ok, reason = validate_action_audit_batch(payload)
    if not ok:
        return HTTPStatus.BAD_REQUEST, {"error": reason}

    for action in payload.get("actions", []):
        get_db(get_settings().db_path).save_action_audit(action.get("action_id"), headers["X-Agent-Id"], action)

    return HTTPStatus.ACCEPTED, {"batch_id": payload.get("batch_id"), "accepted": len(payload.get("actions", []))}
