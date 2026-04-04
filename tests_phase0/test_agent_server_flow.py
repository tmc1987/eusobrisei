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

sys.path.insert(0, str(Path("realtime_agent")))
from agent.outbox import Outbox  # noqa: E402
from agent.transport import Transport  # noqa: E402


class AgentServerFlowTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db_path = os.path.join(self.tmp.name, "outbox.db")
        self.server_db = os.path.join(self.tmp.name, "server.db")
        os.environ["SERVER_DB_PATH"] = self.server_db
        os.environ["SERVER_BOOTSTRAP_TOKEN"] = "dev-bootstrap-token"

    def tearDown(self):
        self.tmp.cleanup()

    def _start_server(self):
        httpd = ThreadingHTTPServer(("127.0.0.1", 0), RequestHandler)
        port = httpd.server_address[1]
        thread = threading.Thread(target=httpd.serve_forever, daemon=True)
        thread.start()
        time.sleep(0.05)
        return httpd, port

    def _bootstrap(self, port):
        conn = HTTPConnection("127.0.0.1", port, timeout=3)
        payload = json.dumps({"activation_token": "dev-bootstrap-token", "hostname": "test-host", "os_version": "Windows-dev", "agent_version": "0.1.0"})
        conn.request("POST", "/v1/agents/bootstrap", body=payload, headers={"Content-Type": "application/json"})
        resp = conn.getresponse()
        data = json.loads(resp.read().decode())
        conn.close()
        self.assertEqual(resp.status, 201)
        return data

    def test_agent_send_e2e_heartbeat_and_events(self):
        httpd, port = self._start_server()
        try:
            boot = self._bootstrap(port)
            outbox = Outbox(self.db_path)
            transport = Transport({"url": f"http://127.0.0.1:{port}", "token": boot["access_token"], "agent_id": boot["agent_id"], "timeout_seconds": 3, "retry": {"base_seconds": 0.01, "max_seconds": 0.1, "jitter_ratio": 0.0}}, outbox)
            transport.send_heartbeat({"schema_version": "1.0", "tenant_id": boot["tenant_id"], "device_id": boot["device_id"], "agent_id": boot["agent_id"], "occurred_at": "2026-01-01T00:00:00Z", "agent_version": "0.1.0"})
            transport.send_events_batch({"batch_id": "11111111-1111-1111-1111-111111111111", "events": [{"event_id": "22222222-2222-2222-2222-222222222222", "event_type": "ALERT", "severity": "S2", "occurred_at": "2026-01-01T00:00:00Z", "context": {}}]})
            transport.flush(logger=_DummyLogger())
            self.assertEqual(len(outbox.due_items(100)), 0)
        finally:
            httpd.shutdown()
            httpd.server_close()

    def test_retry_when_server_unavailable(self):
        outbox = Outbox(self.db_path)
        transport = Transport({"url": "http://127.0.0.1:65500", "token": "dev-token", "agent_id": "a", "timeout_seconds": 0.2, "retry": {"base_seconds": 0.01, "max_seconds": 0.1, "jitter_ratio": 0.0}}, outbox)
        transport.send_events_batch({"batch_id": "33333333-3333-3333-3333-333333333333", "events": [{"event_id": "44444444-4444-4444-4444-444444444444", "event_type": "ALERT", "severity": "S2", "occurred_at": "2026-01-01T00:00:00Z", "context": {}}]})
        transport.flush(logger=_DummyLogger())
        time.sleep(0.03)
        items = outbox.due_items(10)
        self.assertEqual(len(items), 1)
        self.assertGreaterEqual(items[0].attempt_count, 1)

    def test_server_idempotency_persisted(self):
        httpd, port = self._start_server()
        try:
            boot = self._bootstrap(port)
            payload = json.dumps({"batch_id": "55555555-5555-5555-5555-555555555555", "events": [{"event_id": "66666666-6666-6666-6666-666666666666", "event_type": "ALERT", "severity": "S2", "occurred_at": "2026-01-01T00:00:00Z", "context": {}}]})
            headers = {"Content-Type": "application/json", "Authorization": f"Bearer {boot['access_token']}", "X-Agent-Id": boot["agent_id"], "X-Request-Id": "req-1", "Idempotency-Key": "idem-dup"}
            conn = HTTPConnection("127.0.0.1", port, timeout=3)
            conn.request("POST", "/v1/ingestion/events:batch", body=payload, headers=headers)
            r1 = json.loads(conn.getresponse().read().decode())
            conn.close()

            conn2 = HTTPConnection("127.0.0.1", port, timeout=3)
            headers["X-Request-Id"] = "req-2"
            conn2.request("POST", "/v1/ingestion/events:batch", body=payload, headers=headers)
            r2 = json.loads(conn2.getresponse().read().decode())
            conn2.close()
            self.assertEqual(r1, r2)

            with sqlite3.connect(self.server_db) as db:
                row = db.execute("SELECT COUNT(*) FROM idempotency_keys WHERE agent_id=? AND idempotency_key=?", (boot["agent_id"], "idem-dup")).fetchone()
                self.assertEqual(row[0], 1)
        finally:
            httpd.shutdown()
            httpd.server_close()

    def test_invalid_payload_rejected(self):
        httpd, port = self._start_server()
        try:
            boot = self._bootstrap(port)
            payload = json.dumps({"batch_id": "x", "events": [{"event_id": "1"}]})
            headers = {"Content-Type": "application/json", "Authorization": f"Bearer {boot['access_token']}", "X-Agent-Id": boot["agent_id"], "X-Request-Id": "req-3", "Idempotency-Key": "idem-bad"}
            conn = HTTPConnection("127.0.0.1", port, timeout=3)
            conn.request("POST", "/v1/ingestion/events:batch", body=payload, headers=headers)
            resp = conn.getresponse()
            self.assertEqual(resp.status, 400)
            conn.close()
        finally:
            httpd.shutdown()
            httpd.server_close()


class _DummyLogger:
    def info(self, *args, **kwargs):
        pass

    def warning(self, *args, **kwargs):
        pass


if __name__ == "__main__":
    unittest.main()
