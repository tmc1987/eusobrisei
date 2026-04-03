from __future__ import annotations

import json
import sqlite3
import time
from http import HTTPStatus
from typing import Dict, Tuple

from .config import get_settings
from .db import get_db


def _connect():
    return sqlite3.connect(get_settings().db_path)


def _status(last_seen: float | None, has_critical_recent: bool, has_failed_action_recent: bool) -> str:
    if not last_seen:
        return "offline"
    age = time.time() - last_seen
    if age <= 90:
        base = "online"
    elif age <= 300:
        base = "warning"
    else:
        base = "offline"
    if base != "offline" and (has_critical_recent or has_failed_action_recent):
        return "degraded"
    return base


def overview(_: bytes, __: Dict[str, str], ___: Dict[str, str]) -> Tuple[int, Dict]:
    with _connect() as db:
        total_tenants = db.execute("SELECT COUNT(DISTINCT tenant_id) FROM agents").fetchone()[0]
        total_groups = db.execute("SELECT COUNT(DISTINCT COALESCE(group_id,'')) FROM devices").fetchone()[0]
        total_devices = db.execute("SELECT COUNT(*) FROM devices").fetchone()[0]
        total_agents = db.execute("SELECT COUNT(*) FROM agents").fetchone()[0]

        agents = db.execute(
            "SELECT a.agent_id, MAX(h.received_at) as last_seen FROM agents a LEFT JOIN heartbeats h ON h.agent_id=a.agent_id GROUP BY a.agent_id"
        ).fetchall()

        statuses = {"online": 0, "offline": 0, "warning": 0, "degraded": 0}
        for agent_id, last_seen in agents:
            critical = db.execute(
                "SELECT COUNT(*) FROM event_batches WHERE agent_id=? AND received_at>? AND payload LIKE '%\"severity\": \"S4\"%'",
                (agent_id, time.time() - 900),
            ).fetchone()[0] > 0
            failed_action = db.execute(
                "SELECT COUNT(*) FROM action_audit WHERE agent_id=? AND received_at>? AND payload LIKE '%\"execution_status\": \"failed\"%'",
                (agent_id, time.time() - 900),
            ).fetchone()[0] > 0
            statuses[_status(last_seen, critical, failed_action)] += 1

        severities = {"S1": 0, "S2": 0, "S3": 0, "S4": 0}
        rows = db.execute("SELECT payload FROM event_batches WHERE received_at>?", (time.time() - 3600,)).fetchall()
        probable_causes = {}
        process_hits = {}
        for (p,) in rows:
            data = json.loads(p)
            for ev in data.get("events", []):
                sev = ev.get("severity")
                if sev in severities:
                    severities[sev] += 1
                ctx = ev.get("context", {})
                cause = ctx.get("probable_cause")
                if cause:
                    probable_causes[cause] = probable_causes.get(cause, 0) + 1
                for proc in (ctx.get("top_ram_processes") or [])[:2]:
                    n = proc.get("name")
                    if n:
                        process_hits[n] = process_hits.get(n, 0) + 1
                for proc in (ctx.get("top_cpu_processes") or [])[:2]:
                    n = proc.get("name")
                    if n:
                        process_hits[n] = process_hits.get(n, 0) + 1
                for proc in (ctx.get("top_disk_processes") or [])[:2]:
                    n = proc.get("name")
                    if n:
                        process_hits[n] = process_hits.get(n, 0) + 1

        recent_actions = db.execute("SELECT COUNT(*) FROM action_audit WHERE received_at>?", (time.time() - 3600,)).fetchone()[0]
        action_rows = db.execute("SELECT payload FROM action_audit WHERE received_at>?", (time.time() - 3600,)).fetchall()
        outcomes = {"resolved": 0, "mitigated": 0, "failed": 0}
        for (p,) in action_rows:
            payload = json.loads(p)
            outcome = (payload.get("post_state") or {}).get("outcome")
            if outcome in outcomes:
                outcomes[outcome] += 1
            elif payload.get("execution_status") == "failed":
                outcomes["failed"] += 1

    return HTTPStatus.OK, {
        "totals": {
            "tenants": total_tenants,
            "groups": total_groups,
            "devices": total_devices,
            "agents": total_agents,
        },
        "agents_status": statuses,
        "active_alerts_by_severity": severities,
        "recent_auto_actions": recent_actions,
        "action_outcomes": outcomes,
        "top_probable_causes": sorted([{"cause": k, "count": v} for k, v in probable_causes.items()], key=lambda x: x["count"], reverse=True)[:5],
        "top_involved_processes": sorted([{"name": k, "count": v} for k, v in process_hits.items()], key=lambda x: x["count"], reverse=True)[:5],
        "classification_rules": {
            "online_seconds": 90,
            "warning_seconds": 300,
            "degraded_if": "S4 recente ou ação falha recente",
        },
    }


def devices_list(_: bytes, __: Dict[str, str], query: Dict[str, str]) -> Tuple[int, Dict]:
    page = int(query.get("page", "1"))
    page_size = int(query.get("page_size", "20"))
    offset = (page - 1) * page_size
    with _connect() as db:
        rows = db.execute(
            """
            SELECT d.device_id,d.tenant_id,d.group_id,d.hostname,d.os_version,
                   a.agent_id,a.agent_version,
                   MAX(h.received_at) as last_seen
            FROM devices d
            LEFT JOIN agents a ON a.device_id=d.device_id
            LEFT JOIN heartbeats h ON h.agent_id=a.agent_id
            GROUP BY d.device_id,a.agent_id
            ORDER BY d.hostname ASC
            LIMIT ? OFFSET ?
            """,
            (page_size, offset),
        ).fetchall()

        items = []
        for r in rows:
            critical = db.execute("SELECT COUNT(*) FROM event_batches WHERE agent_id=? AND received_at>? AND payload LIKE '%\"severity\": \"S4\"%'", (r[5], time.time() - 900)).fetchone()[0] > 0
            failed = db.execute("SELECT COUNT(*) FROM action_audit WHERE agent_id=? AND received_at>? AND payload LIKE '%\"execution_status\": \"failed\"%'", (r[5], time.time() - 900)).fetchone()[0] > 0
            items.append(
                {
                    "device_id": r[0],
                    "tenant_id": r[1],
                    "group_id": r[2],
                    "hostname": r[3],
                    "os_version": r[4],
                    "agent_id": r[5],
                    "agent_version": r[6],
                    "last_seen": r[7],
                    "status": _status(r[7], critical, failed),
                }
            )
    return HTTPStatus.OK, {"page": page, "page_size": page_size, "items": items}


def device_detail(device_id: str) -> Tuple[int, Dict]:
    with _connect() as db:
        d = db.execute("SELECT device_id,tenant_id,group_id,hostname,os_version FROM devices WHERE device_id=?", (device_id,)).fetchone()
        if not d:
            return HTTPStatus.NOT_FOUND, {"error": "device_not_found"}
        a = db.execute("SELECT agent_id,agent_version FROM agents WHERE device_id=? ORDER BY created_at DESC LIMIT 1", (device_id,)).fetchone()
        agent_id = a[0] if a else None
        hb = db.execute("SELECT payload,received_at FROM heartbeats WHERE agent_id=? ORDER BY received_at DESC LIMIT 1", (agent_id,)).fetchone() if agent_id else None
        ev = db.execute("SELECT payload,received_at FROM event_batches WHERE agent_id=? ORDER BY received_at DESC LIMIT 5", (agent_id,)).fetchall() if agent_id else []
        au = db.execute("SELECT payload,received_at FROM action_audit WHERE agent_id=? ORDER BY received_at DESC LIMIT 10", (agent_id,)).fetchall() if agent_id else []
        pol = get_db(get_settings().db_path).resolve_policy_for_agent(agent_id) if agent_id else None

    return HTTPStatus.OK, {
        "device": {"device_id": d[0], "tenant_id": d[1], "group_id": d[2], "hostname": d[3], "os_version": d[4]},
        "agent": {"agent_id": agent_id, "agent_version": a[1] if a else None},
        "last_heartbeat": {"received_at": hb[1], "payload": json.loads(hb[0])} if hb else None,
        "recent_events": [{"received_at": x[1], "payload": json.loads(x[0])} for x in ev],
        "recent_audit": [{"received_at": x[1], "payload": json.loads(x[0])} for x in au],
        "effective_policy": pol,
    }


def alerts_active(_: bytes, __: Dict[str, str], ___: Dict[str, str]) -> Tuple[int, Dict]:
    items = []
    with _connect() as db:
        rows = db.execute("SELECT agent_id,payload,received_at FROM event_batches WHERE received_at>? ORDER BY received_at DESC", (time.time() - 1800,)).fetchall()
        for agent_id, payload, ts in rows:
            data = json.loads(payload)
            for ev in data.get("events", []):
                if ev.get("severity") in {"S3", "S4"}:
                    ctx = ev.get("context", {})
                    items.append(
                        {
                            "agent_id": agent_id,
                            "severity": ev.get("severity"),
                            "timestamp": ev.get("occurred_at", ts),
                            "cause": ctx.get("message", ""),
                            "event_id": ev.get("event_id"),
                            "probable_cause": ctx.get("probable_cause", ""),
                            "top_processes": ctx.get("top_ram_processes") or ctx.get("top_cpu_processes") or [],
                        }
                    )
    return HTTPStatus.OK, {"items": items}


def audit_actions(_: bytes, __: Dict[str, str], query: Dict[str, str]) -> Tuple[int, Dict]:
    tenant = query.get("tenant_id")
    agent = query.get("agent_id")
    sql = "SELECT a.agent_id,aa.payload,aa.received_at FROM action_audit aa JOIN agents a ON a.agent_id=aa.agent_id WHERE 1=1"
    params = []
    if tenant:
        sql += " AND a.tenant_id=?"
        params.append(tenant)
    if agent:
        sql += " AND a.agent_id=?"
        params.append(agent)
    sql += " ORDER BY aa.received_at DESC LIMIT 100"
    with _connect() as db:
        rows = db.execute(sql, tuple(params)).fetchall()
    return HTTPStatus.OK, {"items": [{"agent_id": r[0], "received_at": r[2], "payload": json.loads(r[1])} for r in rows]}


def policy_effective(agent_id: str) -> Tuple[int, Dict]:
    try:
        doc = get_db(get_settings().db_path).resolve_policy_for_agent(agent_id)
        return HTTPStatus.OK, doc
    except Exception:
        return HTTPStatus.NOT_FOUND, {"error": "agent_not_found"}


def policy_effective_for_device(device_id: str) -> Tuple[int, Dict]:
    with _connect() as db:
        row = db.execute("SELECT agent_id FROM agents WHERE device_id=? ORDER BY created_at DESC LIMIT 1", (device_id,)).fetchone()
        if not row:
            return HTTPStatus.NOT_FOUND, {"error": "device_or_agent_not_found"}
    return policy_effective(row[0])


def health_tenant(tenant_id: str) -> Tuple[int, Dict]:
    with _connect() as db:
        devices = db.execute("SELECT device_id FROM devices WHERE tenant_id=?", (tenant_id,)).fetchall()
        total = len(devices)
        online = 0
        for (device_id,) in devices:
            a = db.execute("SELECT agent_id FROM agents WHERE device_id=? ORDER BY created_at DESC LIMIT 1", (device_id,)).fetchone()
            if not a:
                continue
            last = db.execute("SELECT MAX(received_at) FROM heartbeats WHERE agent_id=?", (a[0],)).fetchone()[0]
            if last and time.time() - last <= 90:
                online += 1
    return HTTPStatus.OK, {"tenant_id": tenant_id, "devices": total, "online": online, "offline": max(total - online, 0)}
