from __future__ import annotations

import json
import sqlite3
import time
import uuid
from pathlib import Path
from typing import Dict, Optional


def _default_policy(tenant_id: str, group_id: str | None = None, device_id: str | None = None) -> Dict:
    return {
        "policy_id": str(uuid.uuid4()),
        "version": "v1",
        "scope": {k: v for k, v in {"tenant_id": tenant_id, "group_id": group_id, "device_id": device_id}.items() if v},
        "thresholds": {"cpu_percent": 85, "ram_percent": 85, "disk_percent": 90, "temperature_c": 85},
        "actions": {
            "enabled": True,
            "safe_mode": True,
            "allowed_actions": ["throttle_top_cpu_process", "thermal_protect", "restart_process"],
            "require_approval_actions": [],
            "rate_limit": {"max_actions_per_hour": 30},
            "cooldown_seconds": 60,
            "restart_allowlist": ["notepad.exe"],
        },
        "transport": {"retry": {"base_seconds": 1, "max_seconds": 20, "jitter_ratio": 0.2}},
        "policy_fetch_interval_seconds": 30,
        "signature": {"algorithm": "RS256", "value": "dev-signature"},
    }

def _parse_version_no(version: str | None) -> int:
    if not version:
        return 1
    digits = "".join(ch for ch in str(version) if ch.isdigit())
    return int(digits) if digits else 1

class DevDB:
    def __init__(self, path: str):
        self.path = path
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        self._init()

    def _connect(self):
        conn = sqlite3.connect(self.path, timeout=10.0)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL;")
        conn.execute("PRAGMA busy_timeout=10000;")
        return conn

    def _init(self) -> None:
        with self._connect() as conn:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS devices (
                    device_id TEXT PRIMARY KEY,
                    tenant_id TEXT NOT NULL,
                    group_id TEXT,
                    hostname TEXT,
                    os_version TEXT,
                    created_at REAL NOT NULL
                );
                CREATE TABLE IF NOT EXISTS agents (
                    agent_id TEXT PRIMARY KEY,
                    tenant_id TEXT NOT NULL,
                    device_id TEXT NOT NULL,
                    agent_version TEXT,
                    access_token TEXT NOT NULL,
                    expires_at REAL NOT NULL,
                    created_at REAL NOT NULL
                );
                CREATE TABLE IF NOT EXISTS policies (
                    policy_id TEXT PRIMARY KEY,
                    tenant_id TEXT NOT NULL,
                    group_id TEXT,
                    device_id TEXT,
                    version_no INTEGER NOT NULL,
                    document TEXT NOT NULL,
                    is_active INTEGER NOT NULL DEFAULT 1,
                    created_at REAL NOT NULL,
                    updated_at REAL NOT NULL
                );
                CREATE TABLE IF NOT EXISTS policy_audit (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    policy_id TEXT NOT NULL,
                    actor TEXT NOT NULL,
                    action TEXT NOT NULL,
                    before_doc TEXT,
                    after_doc TEXT,
                    reason TEXT,
                    scope TEXT,
                    created_at REAL NOT NULL
                );
                CREATE TABLE IF NOT EXISTS heartbeats (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    agent_id TEXT NOT NULL,
                    payload TEXT NOT NULL,
                    received_at REAL NOT NULL
                );
                CREATE TABLE IF NOT EXISTS event_batches (
                    batch_id TEXT PRIMARY KEY,
                    agent_id TEXT NOT NULL,
                    payload TEXT NOT NULL,
                    accepted INTEGER NOT NULL,
                    rejected INTEGER NOT NULL,
                    received_at REAL NOT NULL
                );
                CREATE TABLE IF NOT EXISTS action_audit (
                    action_id TEXT PRIMARY KEY,
                    agent_id TEXT NOT NULL,
                    payload TEXT NOT NULL,
                    received_at REAL NOT NULL
                );
                CREATE TABLE IF NOT EXISTS idempotency_keys (
                    agent_id TEXT NOT NULL,
                    idempotency_key TEXT NOT NULL,
                    response TEXT NOT NULL,
                    created_at REAL NOT NULL,
                    PRIMARY KEY (agent_id, idempotency_key)
                );
                CREATE UNIQUE INDEX IF NOT EXISTS uq_policies_active_scope
                ON policies(tenant_id, IFNULL(group_id, ''), IFNULL(device_id, ''))
                WHERE is_active = 1;
                """
            )

    def _record_policy_audit(self, conn, policy_id: str, actor: str, action: str, before_doc: Dict | None, after_doc: Dict | None, reason: str | None, scope: Dict):
        conn.execute(
            "INSERT INTO policy_audit(policy_id,actor,action,before_doc,after_doc,reason,scope,created_at) VALUES(?,?,?,?,?,?,?,?)",
            (
                policy_id,
                actor,
                action,
                json.dumps(before_doc) if before_doc else None,
                json.dumps(after_doc) if after_doc else None,
                reason,
                json.dumps(scope),
                time.time(),
            ),
        )

    def _create_policy_with_conn(self, conn, document: Dict, actor: str = "dev-user", reason: str | None = None) -> Dict:
        now = time.time()
        policy_id = document.get("policy_id") or str(uuid.uuid4())
        scope = document.get("scope", {})
        doc = json.loads(json.dumps(document))
        version_no = _parse_version_no(doc.get("version"))
        doc["policy_id"] = policy_id
        doc["version"] = doc.get("version") or f"v{version_no}"
        try:
            conn.execute(
                "INSERT INTO policies(policy_id,tenant_id,group_id,device_id,version_no,document,is_active,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?,?)",
                (
                    policy_id,
                    scope.get("tenant_id"),
                    scope.get("group_id"),
                    scope.get("device_id"),
                    version_no,
                    json.dumps(doc),
                    1,
                    now,
                    now,
                ),
            )
        except sqlite3.IntegrityError:
            existing = conn.execute(
                "SELECT policy_id,document FROM policies WHERE tenant_id=? AND IFNULL(group_id,'')=IFNULL(?, '') AND IFNULL(device_id,'')=IFNULL(?, '') AND is_active=1 LIMIT 1",
                (scope.get("tenant_id"), scope.get("group_id"), scope.get("device_id")),
            ).fetchone()
            if not existing:
                raise
            existing_doc = json.loads(existing["document"])
            return existing_doc
        self._record_policy_audit(conn, policy_id, actor, "create", None, doc, reason, scope)
        return doc

    def create_policy(self, document: Dict, actor: str = "dev-user", reason: str | None = None) -> Dict:
        with self._connect() as conn:
            return self._create_policy_with_conn(conn, document, actor=actor, reason=reason)

    def update_policy(self, policy_id: str, document: Dict, actor: str = "dev-user", reason: str | None = None) -> Optional[Dict]:
        with self._connect() as conn:
            row = conn.execute("SELECT version_no,document,tenant_id,group_id,device_id FROM policies WHERE policy_id=?", (policy_id,)).fetchone()
            if not row:
                return None
            before = json.loads(row["document"])
            version_no = int(row["version_no"]) + 1
            scope = before.get("scope", {})
            scope.update(document.get("scope", {}))
            updated = json.loads(json.dumps(before))
            updated.update(document)
            updated["policy_id"] = policy_id
            updated["scope"] = scope
            updated["version"] = f"v{version_no}"
            conn.execute(
                "UPDATE policies SET tenant_id=?,group_id=?,device_id=?,version_no=?,document=?,updated_at=? WHERE policy_id=?",
                (
                    scope.get("tenant_id"),
                    scope.get("group_id"),
                    scope.get("device_id"),
                    version_no,
                    json.dumps(updated),
                    time.time(),
                    policy_id,
                ),
            )
            self._record_policy_audit(conn, policy_id, actor, "update", before, updated, reason, scope)
            return updated

    def disable_policy(self, policy_id: str, actor: str = "dev-user", reason: str | None = None) -> bool:
        with self._connect() as conn:
            row = conn.execute("SELECT document FROM policies WHERE policy_id=?", (policy_id,)).fetchone()
            if not row:
                return False
            before = json.loads(row["document"])
            conn.execute("UPDATE policies SET is_active=0, updated_at=? WHERE policy_id=?", (time.time(), policy_id))
            self._record_policy_audit(conn, policy_id, actor, "disable", before, before, reason, before.get("scope", {}))
            return True

    def get_policy(self, policy_id: str) -> Optional[Dict]:
        with self._connect() as conn:
            row = conn.execute("SELECT document,is_active,version_no,updated_at FROM policies WHERE policy_id=?", (policy_id,)).fetchone()
            if not row:
                return None
            doc = json.loads(row["document"])
            doc["meta"] = {"is_active": bool(row["is_active"]), "version_no": row["version_no"], "updated_at": row["updated_at"]}
            return doc

    def list_policies(self) -> list[Dict]:
        with self._connect() as conn:
            rows = conn.execute("SELECT policy_id,document,is_active,version_no,updated_at FROM policies ORDER BY updated_at DESC").fetchall()
            out = []
            for r in rows:
                doc = json.loads(r["document"])
                doc["meta"] = {"is_active": bool(r["is_active"]), "version_no": r["version_no"], "updated_at": r["updated_at"]}
                out.append(doc)
            return out

    def list_policy_audit(self, policy_id: str | None = None) -> list[Dict]:
        with self._connect() as conn:
            if policy_id:
                rows = conn.execute("SELECT * FROM policy_audit WHERE policy_id=? ORDER BY created_at DESC", (policy_id,)).fetchall()
            else:
                rows = conn.execute("SELECT * FROM policy_audit ORDER BY created_at DESC LIMIT 200").fetchall()
            return [dict(r) for r in rows]

    def _get_active_policy_for_scope(self, tenant_id: str, group_id: str | None, device_id: str | None) -> Optional[sqlite3.Row]:
        with self._connect() as conn:
            return conn.execute(
                "SELECT policy_id FROM policies WHERE tenant_id=? AND IFNULL(group_id,'')=IFNULL(?, '') AND IFNULL(device_id,'')=IFNULL(?, '') AND is_active=1 LIMIT 1",
                (tenant_id, group_id, device_id),
            ).fetchone()

    def bootstrap_agent(self, tenant_id: str, device_id: str, hostname: str, os_version: str, agent_version: str):
        agent_id = str(uuid.uuid4())
        access_token = f"dev-{uuid.uuid4()}"
        now = time.time()
        expires = now + 60 * 60 * 24
        with self._connect() as conn:
            conn.execute("INSERT OR REPLACE INTO devices(device_id, tenant_id, group_id, hostname, os_version, created_at) VALUES(?,?,?,?,?,?)", (device_id, tenant_id, "default", hostname, os_version, now))
            conn.execute("INSERT INTO agents(agent_id, tenant_id, device_id, agent_version, access_token, expires_at, created_at) VALUES(?,?,?,?,?,?,?)", (agent_id, tenant_id, device_id, agent_version, access_token, expires, now))
            row = conn.execute("SELECT 1 FROM policies WHERE tenant_id=? AND group_id IS NULL AND device_id IS NULL AND is_active=1 LIMIT 1", (tenant_id,)).fetchone()
            if not row:
                doc = _default_policy(tenant_id)
                self._create_policy_with_conn(conn, doc, actor="system", reason="default-tenant-policy")
        return {"agent_id": agent_id, "access_token": access_token, "expires_at": expires}

    def get_agent(self, agent_id: str):
        with self._connect() as conn:
            return conn.execute("SELECT * FROM agents WHERE agent_id=?", (agent_id,)).fetchone()

    def get_agent_token(self, agent_id: str) -> Optional[str]:
        row = self.get_agent(agent_id)
        return row["access_token"] if row else None

    def resolve_policy_for_agent(self, agent_id: str) -> Dict:
        def _merge_dict(base: Dict, override: Dict):
            for k, v in override.items():
                if isinstance(v, dict) and isinstance(base.get(k), dict):
                    _merge_dict(base[k], v)
                else:
                    base[k] = v

        with self._connect() as conn:
            agent = conn.execute("SELECT * FROM agents WHERE agent_id=?", (agent_id,)).fetchone()
            if not agent:
                raise ValueError("agent_not_found")
            device = conn.execute("SELECT * FROM devices WHERE device_id=?", (agent["device_id"],)).fetchone()

            tenant_id = agent["tenant_id"]
            group_id = device["group_id"] if device else None
            device_id = agent["device_id"]

            docs = []
            tenant = conn.execute("SELECT document FROM policies WHERE tenant_id=? AND group_id IS NULL AND device_id IS NULL AND is_active=1 ORDER BY updated_at DESC LIMIT 1", (tenant_id,)).fetchone()
            if tenant:
                docs.append(json.loads(tenant["document"]))
            group = conn.execute("SELECT document FROM policies WHERE tenant_id=? AND group_id=? AND device_id IS NULL AND is_active=1 ORDER BY updated_at DESC LIMIT 1", (tenant_id, group_id)).fetchone() if group_id else None
            if group:
                docs.append(json.loads(group["document"]))
            dev = conn.execute("SELECT document FROM policies WHERE tenant_id=? AND device_id=? AND is_active=1 ORDER BY updated_at DESC LIMIT 1", (tenant_id, device_id)).fetchone()
            if dev:
                docs.append(json.loads(dev["document"]))

            if not docs:
                return _default_policy(tenant_id, group_id, device_id)

            resolved = json.loads(json.dumps(docs[0]))
            for d in docs[1:]:
                _merge_dict(resolved.setdefault("thresholds", {}), d.get("thresholds", {}))
                _merge_dict(resolved.setdefault("actions", {}), d.get("actions", {}))
                if "transport" in d:
                    _merge_dict(resolved.setdefault("transport", {}), d.get("transport", {}))
                if "policy_fetch_interval_seconds" in d:
                    resolved["policy_fetch_interval_seconds"] = d["policy_fetch_interval_seconds"]
                resolved["version"] = d.get("version", resolved["version"])
                resolved["policy_id"] = d.get("policy_id", resolved["policy_id"])

            resolved["scope"] = {"tenant_id": tenant_id, "group_id": group_id, "device_id": device_id}
            return resolved

    # backward compatible method used by legacy dev endpoint
    def upsert_policy(self, document: Dict):
        existing = self.get_policy(document.get("policy_id", ""))
        if existing:
            return self.update_policy(document["policy_id"], document, actor="dev-user", reason="upsert")
        scope = document.get("scope", {})
        scoped_existing = self._get_active_policy_for_scope(scope.get("tenant_id"), scope.get("group_id"), scope.get("device_id"))
        if scoped_existing:
            self.disable_policy(scoped_existing["policy_id"], actor="dev-user", reason="scope-replaced")
        return self.create_policy(document, actor="dev-user", reason="upsert")

    def save_heartbeat(self, agent_id: str, payload: Dict):
        with self._connect() as conn:
            conn.execute("INSERT INTO heartbeats(agent_id,payload,received_at) VALUES(?,?,?)", (agent_id, json.dumps(payload), time.time()))

    def get_idempotent_response(self, agent_id: str, key: str) -> Optional[Dict]:
        with self._connect() as conn:
            row = conn.execute("SELECT response FROM idempotency_keys WHERE agent_id=? AND idempotency_key=?", (agent_id, key)).fetchone()
            return json.loads(row["response"]) if row else None

    def save_idempotent_response(self, agent_id: str, key: str, response: Dict):
        with self._connect() as conn:
            conn.execute("INSERT OR REPLACE INTO idempotency_keys(agent_id,idempotency_key,response,created_at) VALUES(?,?,?,?)", (agent_id, key, json.dumps(response), time.time()))

    def save_event_batch(self, batch_id: str, agent_id: str, payload: Dict, accepted: int, rejected: int):
        with self._connect() as conn:
            conn.execute("INSERT OR REPLACE INTO event_batches(batch_id,agent_id,payload,accepted,rejected,received_at) VALUES(?,?,?,?,?,?)", (batch_id, agent_id, json.dumps(payload), accepted, rejected, time.time()))

    def save_action_audit(self, action_id: str, agent_id: str, payload: Dict):
        with self._connect() as conn:
            conn.execute("INSERT OR REPLACE INTO action_audit(action_id,agent_id,payload,received_at) VALUES(?,?,?,?)", (action_id, agent_id, json.dumps(payload), time.time()))


_DB_CACHE: dict[str, DevDB] = {}


def get_db(path: str) -> DevDB:
    if path not in _DB_CACHE:
        _DB_CACHE[path] = DevDB(path)
    return _DB_CACHE[path]
