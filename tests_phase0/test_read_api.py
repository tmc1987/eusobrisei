import json
import os
import tempfile
import threading
import time
import unittest
from http.client import HTTPConnection
from pathlib import Path
import sys

sys.path.insert(0, str(Path("server")))
from app.app import RequestHandler, ThreadingHTTPServer  # noqa: E402


class ReadApiTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        os.environ["SERVER_DB_PATH"] = str(Path(self.tmp.name) / "dev.db")
        os.environ["SERVER_BOOTSTRAP_TOKEN"] = "dev-bootstrap-token"
        self.httpd = ThreadingHTTPServer(("127.0.0.1", 0), RequestHandler)
        self.port = self.httpd.server_address[1]
        self.thread = threading.Thread(target=self.httpd.serve_forever, daemon=True)
        self.thread.start()
        time.sleep(0.05)
        self.agent = self._bootstrap()
        self._send_heartbeat()
        self._send_event()

    def tearDown(self):
        self.httpd.shutdown()
        self.httpd.server_close()
        self.tmp.cleanup()

    def _bootstrap(self):
        conn = HTTPConnection("127.0.0.1", self.port, timeout=3)
        payload = json.dumps({"activation_token": "dev-bootstrap-token", "hostname": "devbox", "os_version": "Windows", "agent_version": "0.1.0"})
        conn.request("POST", "/v1/agents/bootstrap", body=payload, headers={"Content-Type": "application/json"})
        resp = conn.getresponse()
        data = json.loads(resp.read().decode())
        conn.close()
        return data

    def _headers(self, idem="x1"):
        return {"Content-Type": "application/json", "Authorization": f"Bearer {self.agent['access_token']}", "X-Agent-Id": self.agent["agent_id"], "X-Request-Id": "r1", "Idempotency-Key": idem}

    def _send_heartbeat(self):
        conn = HTTPConnection("127.0.0.1", self.port, timeout=3)
        hb = {"schema_version": "1.0", "tenant_id": self.agent["tenant_id"], "device_id": self.agent["device_id"], "agent_id": self.agent["agent_id"], "occurred_at": "2026-01-01T00:00:00Z", "agent_version": "0.1.0"}
        h = self._headers(); h.pop("Idempotency-Key")
        conn.request("POST", "/v1/agents/heartbeat", body=json.dumps(hb), headers=h)
        conn.getresponse().read(); conn.close()

    def _send_event(self):
        conn = HTTPConnection("127.0.0.1", self.port, timeout=3)
        ev = {"batch_id": "11111111-1111-1111-1111-111111111111", "events": [{"event_id": "22222222-2222-2222-2222-222222222222", "event_type": "ALERT", "severity": "S3", "occurred_at": "2026-01-01T00:00:00Z", "context": {"message": "cpu alto"}}]}
        conn.request("POST", "/v1/ingestion/events:batch", body=json.dumps(ev), headers=self._headers("e1"))
        conn.getresponse().read(); conn.close()

    def test_overview_and_devices(self):
        conn = HTTPConnection("127.0.0.1", self.port, timeout=3)
        conn.request("GET", "/v1/overview")
        ov = json.loads(conn.getresponse().read().decode()); conn.close()
        self.assertIn("totals", ov)
        self.assertIn("agents_status", ov)
        self.assertIn("remediation_efficiency", ov)

        conn2 = HTTPConnection("127.0.0.1", self.port, timeout=3)
        conn2.request("GET", "/v1/devices?page=1&page_size=10")
        dv = json.loads(conn2.getresponse().read().decode()); conn2.close()
        self.assertGreaterEqual(len(dv["items"]), 1)

    def test_device_detail_and_policy_endpoint(self):
        conn = HTTPConnection("127.0.0.1", self.port, timeout=3)
        conn.request("GET", f"/v1/devices/{self.agent['device_id']}")
        detail = json.loads(conn.getresponse().read().decode()); conn.close()
        self.assertIn("effective_policy", detail)

        conn2 = HTTPConnection("127.0.0.1", self.port, timeout=3)
        conn2.request("GET", f"/v1/policies/effective/{self.agent['agent_id']}")
        pol = json.loads(conn2.getresponse().read().decode()); conn2.close()
        self.assertIn("thresholds", pol)

    def test_alerts_and_tenant_health(self):
        conn = HTTPConnection("127.0.0.1", self.port, timeout=3)
        conn.request("GET", "/v1/alerts/active")
        alerts = json.loads(conn.getresponse().read().decode()); conn.close()
        self.assertGreaterEqual(len(alerts["items"]), 1)

        conn2 = HTTPConnection("127.0.0.1", self.port, timeout=3)
        conn2.request("GET", f"/v1/health/tenants/{self.agent['tenant_id']}")
        health = json.loads(conn2.getresponse().read().decode()); conn2.close()
        self.assertEqual(health["tenant_id"], self.agent["tenant_id"])


if __name__ == "__main__":
    unittest.main()
