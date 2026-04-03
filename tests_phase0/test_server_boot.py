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


class ServerBootTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        os.environ["SERVER_DB_PATH"] = str(Path(self.tmp.name) / "dev.db")
        os.environ["SERVER_BOOTSTRAP_TOKEN"] = "dev-bootstrap-token"
        self.httpd = ThreadingHTTPServer(("127.0.0.1", 0), RequestHandler)
        self.port = self.httpd.server_address[1]
        self.thread = threading.Thread(target=self.httpd.serve_forever, daemon=True)
        self.thread.start()
        time.sleep(0.05)
        self.agent_id, self.token = self._bootstrap()

    def tearDown(self):
        self.httpd.shutdown()
        self.httpd.server_close()
        self.tmp.cleanup()

    def _bootstrap(self):
        conn = HTTPConnection("127.0.0.1", self.port, timeout=3)
        payload = json.dumps(
            {
                "activation_token": "dev-bootstrap-token",
                "hostname": "test-host",
                "os_version": "Windows-dev",
                "agent_version": "0.1.0",
            }
        )
        conn.request("POST", "/v1/agents/bootstrap", body=payload, headers={"Content-Type": "application/json"})
        resp = conn.getresponse()
        body = json.loads(resp.read().decode())
        conn.close()
        self.assertEqual(resp.status, 201)
        return body["agent_id"], body["access_token"]

    def _headers(self, req_id="req-1", idem=None):
        h = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.token}",
            "X-Agent-Id": self.agent_id,
            "X-Request-Id": req_id,
        }
        if idem:
            h["Idempotency-Key"] = idem
        return h

    def test_healthcheck(self):
        conn = HTTPConnection("127.0.0.1", self.port, timeout=3)
        conn.request("GET", "/healthz")
        resp = conn.getresponse()
        self.assertEqual(resp.status, 200)
        conn.close()

    def test_events_batch_ingest(self):
        conn = HTTPConnection("127.0.0.1", self.port, timeout=3)
        payload = json.dumps({"batch_id": "11111111-1111-1111-1111-111111111111", "events": [{"event_id": "22222222-2222-2222-2222-222222222222", "event_type": "ALERT", "severity": "S2", "occurred_at": "2026-01-01T00:00:00Z", "context": {"k": "v"}}]})
        conn.request("POST", "/v1/ingestion/events:batch", body=payload, headers=self._headers(idem="idem-1"))
        resp = conn.getresponse()
        body = json.loads(resp.read().decode())
        self.assertEqual(resp.status, 202)
        self.assertEqual(body["accepted"], 1)
        conn.close()

    def test_heartbeat_ingest(self):
        conn = HTTPConnection("127.0.0.1", self.port, timeout=3)
        payload = json.dumps({"schema_version": "1.0", "tenant_id": "00000000-0000-0000-0000-000000000001", "device_id": "00000000-0000-0000-0000-000000000002", "agent_id": self.agent_id, "occurred_at": "2026-01-01T00:00:00Z", "agent_version": "0.1.0"})
        conn.request("POST", "/v1/agents/heartbeat", body=payload, headers=self._headers())
        resp = conn.getresponse()
        self.assertEqual(resp.status, 202)
        conn.close()


if __name__ == "__main__":
    unittest.main()
