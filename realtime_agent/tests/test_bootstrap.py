import os
import tempfile
import threading
import time
import unittest
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "server"))
from app.app import RequestHandler, ThreadingHTTPServer  # noqa: E402

from agent.bootstrap import bootstrap_if_needed, load_identity  # noqa: E402


class _Logger:
    def info(self, *args, **kwargs):
        pass


class BootstrapTests(unittest.TestCase):
    def test_bootstrap_and_store_identity(self):
        with tempfile.TemporaryDirectory() as tmp:
            os.environ["SERVER_DB_PATH"] = str(Path(tmp) / "server.db")
            os.environ["SERVER_BOOTSTRAP_TOKEN"] = "dev-bootstrap-token"
            httpd = ThreadingHTTPServer(("127.0.0.1", 0), RequestHandler)
            port = httpd.server_address[1]
            t = threading.Thread(target=httpd.serve_forever, daemon=True)
            t.start()
            time.sleep(0.05)
            try:
                cfg = {
                    "server": {"url": f"http://127.0.0.1:{port}", "timeout_seconds": 2},
                    "bootstrap": {
                        "activation_token": "dev-bootstrap-token",
                        "identity_store_path": str(Path(tmp) / "identity.json"),
                        "hostname": "test-host",
                        "os_version": "Windows-dev",
                    },
                    "identity": {"agent_version": "0.1.0"},
                }
                identity = bootstrap_if_needed(cfg, _Logger())
                self.assertIn("agent_id", identity)
                self.assertIn("token", identity)
                stored = load_identity(cfg["bootstrap"]["identity_store_path"])
                self.assertEqual(identity["agent_id"], stored["agent_id"])
            finally:
                httpd.shutdown()
                httpd.server_close()


if __name__ == "__main__":
    unittest.main()
