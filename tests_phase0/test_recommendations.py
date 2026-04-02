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


class RecommendationTests(unittest.TestCase):
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
        self._seed_data()

    def tearDown(self):
        self.httpd.shutdown()
        self.httpd.server_close()
        self.tmp.cleanup()

    def _bootstrap(self):
        conn = HTTPConnection("127.0.0.1", self.port, timeout=3)
        payload = json.dumps({"activation_token": "dev-bootstrap-token", "hostname": "devbox", "os_version": "Windows", "agent_version": "0.1.0"})
        conn.request("POST", "/v1/agents/bootstrap", body=payload, headers={"Content-Type": "application/json"})
        body = json.loads(conn.getresponse().read().decode())
        conn.close()
        return body

    def _headers(self, idem="i1"):
        return {"Content-Type": "application/json", "Authorization": f"Bearer {self.agent['access_token']}", "X-Agent-Id": self.agent["agent_id"], "X-Request-Id": "r1", "Idempotency-Key": idem}

    def _seed_data(self):
        # send repeated events to trigger recommendations
        msgs = ["RAM alta recorrente", "RAM alta recorrente", "RAM alta recorrente", "Temperatura alta", "Temperatura alta", "Disco alto", "Disco alto", "Disco alto"]
        events = []
        for i, m in enumerate(msgs):
            events.append({"event_id": f"00000000-0000-0000-0000-0000000000{i:02d}", "event_type": "ALERT", "severity": "S3", "occurred_at": "2026-01-01T00:00:00Z", "context": {"message": m}})
        conn = HTTPConnection("127.0.0.1", self.port, timeout=3)
        conn.request("POST", "/v1/ingestion/events:batch", body=json.dumps({"batch_id": "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa", "events": events}), headers=self._headers("ev1"))
        conn.getresponse().read(); conn.close()

        audit = {"batch_id": "bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb", "actions": [{"action_id": "cccccccc-cccc-cccc-cccc-cccccccccccc", "trigger_event_id": "dddddddd-dddd-dddd-dddd-dddddddddddd", "action_name": "thermal_protect", "reason": "temp", "risk_level": "medium", "pre_state": {}, "post_state": {}, "rollback_possible": False, "rollback_executed": False, "execution_status": "failed", "error_message": "x", "occurred_at": "2026-01-01T00:00:00Z", "policy_version": "dev"}]}
        conn2 = HTTPConnection("127.0.0.1", self.port, timeout=3)
        conn2.request("POST", "/v1/audit/actions:batch", body=json.dumps(audit), headers=self._headers("au1"))
        conn2.getresponse().read(); conn2.close()

    def test_recommendations_endpoints(self):
        conn = HTTPConnection("127.0.0.1", self.port, timeout=3)
        conn.request("GET", "/v1/recommendations")
        recs = json.loads(conn.getresponse().read().decode())
        conn.close()
        self.assertGreaterEqual(len(recs["items"]), 1)
        first = recs["items"][0]
        for k in ["type", "summary", "evidences", "impact", "confidence", "severity", "timestamp", "status"]:
            self.assertIn(k, first)

        conn2 = HTTPConnection("127.0.0.1", self.port, timeout=3)
        conn2.request("GET", f"/v1/recommendations/devices/{self.agent['device_id']}")
        drec = json.loads(conn2.getresponse().read().decode())
        conn2.close()
        self.assertGreaterEqual(len(drec["items"]), 1)

        conn3 = HTTPConnection("127.0.0.1", self.port, timeout=3)
        conn3.request("GET", f"/v1/recommendations/tenants/{self.agent['tenant_id']}")
        trec = json.loads(conn3.getresponse().read().decode())
        conn3.close()
        self.assertGreaterEqual(len(trec["items"]), 1)


if __name__ == "__main__":
    unittest.main()
