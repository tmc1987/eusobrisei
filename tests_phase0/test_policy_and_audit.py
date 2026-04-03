import json
import os
import sqlite3
import tempfile
import threading
import time
import unittest
from http.client import HTTPConnection
from pathlib import Path
import sys

sys.path.insert(0, str(Path("server")))
from app.app import RequestHandler, ThreadingHTTPServer  # noqa: E402


def bootstrap(port):
    conn = HTTPConnection("127.0.0.1", port, timeout=3)
    payload = json.dumps({"activation_token": "dev-bootstrap-token", "hostname": "h", "os_version": "w", "agent_version": "0.1.0"})
    conn.request("POST", "/v1/agents/bootstrap", body=payload, headers={"Content-Type": "application/json"})
    resp = conn.getresponse()
    body = json.loads(resp.read().decode())
    conn.close()
    assert resp.status == 201
    return body


class PolicyAuditTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db = str(Path(self.tmp.name) / "dev.db")
        os.environ["SERVER_DB_PATH"] = self.db
        os.environ["SERVER_BOOTSTRAP_TOKEN"] = "dev-bootstrap-token"
        self.httpd = ThreadingHTTPServer(("127.0.0.1", 0), RequestHandler)
        self.port = self.httpd.server_address[1]
        self.thread = threading.Thread(target=self.httpd.serve_forever, daemon=True)
        self.thread.start()
        time.sleep(0.05)
        self.boot = bootstrap(self.port)

    def tearDown(self):
        self.httpd.shutdown()
        self.httpd.server_close()
        self.tmp.cleanup()

    def _auth_headers(self, req_id="r1", idem="i1"):
        return {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.boot['access_token']}",
            "X-Agent-Id": self.boot["agent_id"],
            "X-Request-Id": req_id,
            "Idempotency-Key": idem,
        }

    def test_policy_precedence_device_over_tenant(self):
        tenant_policy = {
            "policy_id": "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa",
            "version": "tenant-v1",
            "scope": {"tenant_id": self.boot["tenant_id"]},
            "thresholds": {"cpu_percent": 90, "ram_percent": 90, "disk_percent": 95, "temperature_c": 90},
            "actions": {"enabled": True, "safe_mode": True, "allowed_actions": ["thermal_protect"], "require_approval_actions": [], "rate_limit": {"max_actions_per_hour": 10}},
            "signature": {"algorithm": "RS256", "value": "dev"},
        }
        device_policy = {
            "policy_id": "bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb",
            "version": "device-v1",
            "scope": {"tenant_id": self.boot["tenant_id"], "device_id": self.boot["device_id"]},
            "thresholds": {"cpu_percent": 70, "ram_percent": 88, "disk_percent": 90, "temperature_c": 80},
            "actions": {"enabled": True, "safe_mode": True, "allowed_actions": ["throttle_top_cpu_process"], "require_approval_actions": [], "rate_limit": {"max_actions_per_hour": 5}},
            "signature": {"algorithm": "RS256", "value": "dev"},
        }
        conn = HTTPConnection("127.0.0.1", self.port, timeout=3)
        conn.request("POST", "/v1/dev/policies", body=json.dumps(tenant_policy), headers={"Content-Type": "application/json"})
        self.assertEqual(conn.getresponse().status, 201)
        conn.close()

        conn2 = HTTPConnection("127.0.0.1", self.port, timeout=3)
        conn2.request("POST", "/v1/dev/policies", body=json.dumps(device_policy), headers={"Content-Type": "application/json"})
        self.assertEqual(conn2.getresponse().status, 201)
        conn2.close()

        conn3 = HTTPConnection("127.0.0.1", self.port, timeout=3)
        headers = self._auth_headers(req_id="pol-1")
        headers.pop("Idempotency-Key")
        conn3.request("GET", "/v1/policies/resolved", headers=headers)
        resp = conn3.getresponse()
        body = json.loads(resp.read().decode())
        conn3.close()
        self.assertEqual(resp.status, 200)
        self.assertEqual(body["version"], "device-v1")
        self.assertEqual(body["thresholds"]["cpu_percent"], 70)
        self.assertEqual(body["actions"]["rate_limit"]["max_actions_per_hour"], 5)

    def test_nested_actions_merge_preserves_unspecified_tenant_values(self):
        tenant_policy = {
            "policy_id": "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaa01",
            "version": "tenant-v1",
            "scope": {"tenant_id": self.boot["tenant_id"]},
            "thresholds": {"cpu_percent": 90, "ram_percent": 90, "disk_percent": 95, "temperature_c": 90},
            "actions": {
                "enabled": True,
                "safe_mode": True,
                "allowed_actions": ["thermal_protect"],
                "require_approval_actions": [],
                "rate_limit": {"max_actions_per_hour": 10, "burst": 3},
            },
            "signature": {"algorithm": "RS256", "value": "dev"},
        }
        device_policy = {
            "policy_id": "bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbb01",
            "version": "device-v1",
            "scope": {"tenant_id": self.boot["tenant_id"], "device_id": self.boot["device_id"]},
            "thresholds": {"cpu_percent": 70, "ram_percent": 88, "disk_percent": 90, "temperature_c": 80},
            "actions": {"rate_limit": {"max_actions_per_hour": 5}},
            "signature": {"algorithm": "RS256", "value": "dev"},
        }
        conn = HTTPConnection("127.0.0.1", self.port, timeout=3)
        conn.request("POST", "/v1/dev/policies", body=json.dumps(tenant_policy), headers={"Content-Type": "application/json"})
        self.assertEqual(conn.getresponse().status, 201)
        conn.close()
        conn2 = HTTPConnection("127.0.0.1", self.port, timeout=3)
        conn2.request("POST", "/v1/dev/policies", body=json.dumps(device_policy), headers={"Content-Type": "application/json"})
        self.assertEqual(conn2.getresponse().status, 201)
        conn2.close()

        conn3 = HTTPConnection("127.0.0.1", self.port, timeout=3)
        headers = self._auth_headers(req_id="pol-2")
        headers.pop("Idempotency-Key")
        conn3.request("GET", "/v1/policies/resolved", headers=headers)
        resp = conn3.getresponse()
        body = json.loads(resp.read().decode())
        conn3.close()
        self.assertEqual(resp.status, 200)
        self.assertEqual(body["actions"]["rate_limit"]["max_actions_per_hour"], 5)
        self.assertEqual(body["actions"]["rate_limit"]["burst"], 3)

    def test_audit_persisted(self):
        payload = {
            "batch_id": "99999999-9999-9999-9999-999999999999",
            "actions": [
                {
                    "action_id": "88888888-8888-8888-8888-888888888888",
                    "trigger_event_id": "77777777-7777-7777-7777-777777777777",
                    "action_name": "thermal_protect",
                    "reason": "temp alta",
                    "risk_level": "medium",
                    "pre_state": {},
                    "post_state": {},
                    "rollback_possible": False,
                    "rollback_executed": False,
                    "execution_status": "success",
                    "error_message": "",
                    "occurred_at": "2026-01-01T00:00:00Z",
                    "policy_version": "device-v1"
                }
            ]
        }
        conn = HTTPConnection("127.0.0.1", self.port, timeout=3)
        conn.request("POST", "/v1/audit/actions:batch", body=json.dumps(payload), headers=self._auth_headers(idem="audit-1"))
        resp = conn.getresponse()
        self.assertEqual(resp.status, 202)
        conn.close()

        with sqlite3.connect(self.db) as db:
            row = db.execute("SELECT COUNT(*) FROM action_audit WHERE action_id=?", ("88888888-8888-8888-8888-888888888888",)).fetchone()
            self.assertEqual(row[0], 1)

    def test_bootstrap_concurrency_creates_single_active_tenant_default_policy(self):
        results = []
        errors = []

        def _worker(i: int):
            try:
                conn = HTTPConnection("127.0.0.1", self.port, timeout=5)
                payload = json.dumps(
                    {
                        "activation_token": "dev-bootstrap-token",
                        "hostname": f"h-{i}",
                        "os_version": "w",
                        "agent_version": "0.1.0",
                    }
                )
                conn.request("POST", "/v1/agents/bootstrap", body=payload, headers={"Content-Type": "application/json"})
                resp = conn.getresponse()
                body = json.loads(resp.read().decode())
                conn.close()
                if resp.status != 201:
                    errors.append((resp.status, body))
                else:
                    results.append(body["agent_id"])
            except Exception as exc:  # pragma: no cover - defensive test instrumentation
                errors.append(str(exc))

        threads = [threading.Thread(target=_worker, args=(i,), daemon=True) for i in range(8)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        self.assertEqual(len(errors), 0, msg=f"errors: {errors}")
        self.assertEqual(len(results), 8)

        with sqlite3.connect(self.db) as db:
            row = db.execute(
                "SELECT COUNT(*) FROM policies WHERE tenant_id=? AND group_id IS NULL AND device_id IS NULL AND is_active=1",
                ("00000000-0000-0000-0000-000000000001",),
            ).fetchone()
            self.assertEqual(row[0], 1)

    def test_policy_management_endpoints_create_edit_disable_and_audit(self):
        create_payload = {
            "version": "dev-v1",
            "scope": {"tenant_id": self.boot["tenant_id"], "group_id": "11111111-1111-1111-1111-111111111111"},
            "thresholds": {"cpu_percent": 86, "ram_percent": 87, "disk_percent": 91, "temperature_c": 84},
            "actions": {
                "enabled": True,
                "safe_mode": True,
                "allowed_actions": ["thermal_protect"],
                "require_approval_actions": [],
                "rate_limit": {"max_actions_per_hour": 11},
            },
            "signature": {"algorithm": "RS256", "value": "dev"},
        }
        conn = HTTPConnection("127.0.0.1", self.port, timeout=3)
        conn.request(
            "POST",
            "/v1/policies",
            body=json.dumps(create_payload),
            headers={"Content-Type": "application/json", "X-Dev-Actor": "web-console"},
        )
        created_resp = conn.getresponse()
        created = json.loads(created_resp.read().decode())
        conn.close()
        self.assertEqual(created_resp.status, 201)
        policy_id = created["policy_id"]

        conn2 = HTTPConnection("127.0.0.1", self.port, timeout=3)
        conn2.request("GET", f"/v1/policies/{policy_id}")
        resp2 = conn2.getresponse()
        detail = json.loads(resp2.read().decode())
        conn2.close()
        self.assertEqual(resp2.status, 200)
        self.assertEqual(detail["meta"]["is_active"], True)

        update_payload = {"actions": {"rate_limit": {"max_actions_per_hour": 7}}}
        conn3 = HTTPConnection("127.0.0.1", self.port, timeout=3)
        conn3.request("PUT", f"/v1/policies/{policy_id}", body=json.dumps(update_payload), headers={"Content-Type": "application/json"})
        self.assertEqual(conn3.getresponse().status, 200)
        conn3.close()

        conn4 = HTTPConnection("127.0.0.1", self.port, timeout=3)
        conn4.request("GET", f"/v1/policies/{policy_id}")
        edited = json.loads(conn4.getresponse().read().decode())
        conn4.close()
        self.assertEqual(edited["actions"]["rate_limit"]["max_actions_per_hour"], 7)
        self.assertEqual(edited["meta"]["version_no"], 2)

        conn5 = HTTPConnection("127.0.0.1", self.port, timeout=3)
        conn5.request("POST", f"/v1/policies/{policy_id}/disable", body=b"{}", headers={"Content-Type": "application/json"})
        self.assertEqual(conn5.getresponse().status, 200)
        conn5.close()

        conn6 = HTTPConnection("127.0.0.1", self.port, timeout=3)
        conn6.request("GET", "/v1/policies?status=disabled")
        lst = json.loads(conn6.getresponse().read().decode())
        conn6.close()
        self.assertTrue(any(x["policy_id"] == policy_id for x in lst["items"]))

        conn7 = HTTPConnection("127.0.0.1", self.port, timeout=3)
        conn7.request("GET", f"/v1/policies/audit?policy_id={policy_id}")
        audit = json.loads(conn7.getresponse().read().decode())
        conn7.close()
        actions = [x["action"] for x in audit["items"]]
        self.assertIn("create", actions)
        self.assertIn("update", actions)
        self.assertIn("disable", actions)

    def test_policy_effective_for_device_endpoint(self):
        conn = HTTPConnection("127.0.0.1", self.port, timeout=3)
        conn.request("GET", f"/v1/policies/effective/device/{self.boot['device_id']}")
        resp = conn.getresponse()
        body = json.loads(resp.read().decode())
        conn.close()
        self.assertEqual(resp.status, 200)
        self.assertEqual(body["scope"]["device_id"], self.boot["device_id"])

    def test_cors_preflight_allows_web_console_policy_headers(self):
        conn = HTTPConnection("127.0.0.1", self.port, timeout=3)
        conn.request(
            "OPTIONS",
            "/v1/policies",
            headers={
                "Origin": "http://127.0.0.1:5500",
                "Access-Control-Request-Method": "POST",
                "Access-Control-Request-Headers": "content-type,x-dev-actor",
            },
        )
        resp = conn.getresponse()
        _ = resp.read()
        allow_headers = resp.getheader("Access-Control-Allow-Headers", "")
        allow_methods = resp.getheader("Access-Control-Allow-Methods", "")
        conn.close()
        self.assertEqual(resp.status, 204)
        self.assertIn("X-Dev-Actor", allow_headers)
        self.assertIn("POST", allow_methods)
        self.assertIn("PUT", allow_methods)

    def test_create_policy_rejects_incomplete_scope(self):
        payload = {
            "policy_id": "99999999-9999-9999-9999-999999999999",
            "version": "dev-v1",
            "scope": {},
            "thresholds": {"cpu_percent": 86, "ram_percent": 87, "disk_percent": 91, "temperature_c": 84},
            "actions": {
                "enabled": True,
                "safe_mode": True,
                "allowed_actions": ["thermal_protect"],
                "require_approval_actions": [],
                "rate_limit": {"max_actions_per_hour": 11},
            },
            "signature": {"algorithm": "RS256", "value": "dev"},
        }
        conn = HTTPConnection("127.0.0.1", self.port, timeout=3)
        conn.request("POST", "/v1/policies", body=json.dumps(payload), headers={"Content-Type": "application/json", "X-Dev-Actor": "web-console"})
        resp = conn.getresponse()
        body = json.loads(resp.read().decode())
        conn.close()
        self.assertEqual(resp.status, 400)
        self.assertIn("schema_error", body.get("error", ""))


if __name__ == "__main__":
    unittest.main()
