from __future__ import annotations

from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

from .config import get_settings
from .handlers import (
    action_audit_batch_ingest,
    bootstrap_agent,
    policies_list,
    policy_audit_list,
    policy_create,
    policy_detail,
    policy_disable,
    policy_update,
    dev_upsert_policy,
    events_batch_ingest,
    healthcheck,
    heartbeat_ingest,
    resolve_policy,
)
from .read_handlers import (
    alerts_active,
    audit_actions,
    device_detail,
    devices_list,
    health_tenant,
    overview,
    policy_effective,
    policy_effective_for_device,
)
from .recommendations import recommendations_all, recommendations_for_device, recommendations_for_tenant
from .router import Router


router = Router()
router.add("GET", "/healthz", healthcheck)
router.add("GET", "/v1/policies/resolved", resolve_policy)
router.add("POST", "/v1/agents/bootstrap", bootstrap_agent)
router.add("POST", "/v1/agents/heartbeat", heartbeat_ingest)
router.add("POST", "/v1/ingestion/events:batch", events_batch_ingest)
router.add("POST", "/v1/audit/actions:batch", action_audit_batch_ingest)
router.add("POST", "/v1/dev/policies", dev_upsert_policy)


class RequestHandler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def _headers_dict(self) -> dict[str, str]:
        return {k: v for k, v in self.headers.items()}

    def _with_cors(self, status: int, payload: bytes, content_type: str) -> None:
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(payload)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization, X-Agent-Id, X-Request-Id, Idempotency-Key")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, PUT, OPTIONS")
        self.end_headers()
        self.wfile.write(payload)

    def _handle(self) -> None:
        parsed = urlparse(self.path)
        path = parsed.path
        query = {k: v[0] for k, v in parse_qs(parsed.query).items()}
        length = int(self.headers.get("Content-Length", "0"))
        body = self.rfile.read(length) if length > 0 else b""

        # read-only operational endpoints
        if self.command == "GET" and path == "/v1/overview":
            status, data = overview(body, self._headers_dict(), query)
            payload = __import__("json").dumps(data).encode("utf-8")
            return self._with_cors(status, payload, "application/json")
        if self.command == "GET" and path == "/v1/devices":
            status, data = devices_list(body, self._headers_dict(), query)
            payload = __import__("json").dumps(data).encode("utf-8")
            return self._with_cors(status, payload, "application/json")
        if self.command == "GET" and path.startswith("/v1/devices/"):
            status, data = device_detail(path.split("/v1/devices/", 1)[1])
            payload = __import__("json").dumps(data).encode("utf-8")
            return self._with_cors(status, payload, "application/json")
        if self.command == "GET" and path == "/v1/alerts/active":
            status, data = alerts_active(body, self._headers_dict(), query)
            payload = __import__("json").dumps(data).encode("utf-8")
            return self._with_cors(status, payload, "application/json")
        if self.command == "GET" and path == "/v1/audit/actions":
            status, data = audit_actions(body, self._headers_dict(), query)
            payload = __import__("json").dumps(data).encode("utf-8")
            return self._with_cors(status, payload, "application/json")
        if self.command == "GET" and path.startswith("/v1/policies/effective/device/"):
            status, data = policy_effective_for_device(path.split("/v1/policies/effective/device/", 1)[1])
            payload = __import__("json").dumps(data).encode("utf-8")
            return self._with_cors(status, payload, "application/json")
        if self.command == "GET" and path.startswith("/v1/policies/effective/"):
            status, data = policy_effective(path.split("/v1/policies/effective/", 1)[1])
            payload = __import__("json").dumps(data).encode("utf-8")
            return self._with_cors(status, payload, "application/json")
        if self.command == "GET" and path == "/v1/policies":
            status, data = policies_list(body, self._headers_dict(), query)
            payload = __import__("json").dumps(data).encode("utf-8")
            return self._with_cors(status, payload, "application/json")
        if self.command == "POST" and path == "/v1/policies":
            status, data = policy_create(body, self._headers_dict())
            payload = __import__("json").dumps(data).encode("utf-8")
            return self._with_cors(status, payload, "application/json")
        if (
            self.command == "GET"
            and path.startswith("/v1/policies/")
            and not path.endswith("/disable")
            and not path.startswith("/v1/policies/effective/")
            and path != "/v1/policies/audit"
            and path != "/v1/policies/resolved"
        ):
            status, data = policy_detail(path.split("/v1/policies/", 1)[1])
            payload = __import__("json").dumps(data).encode("utf-8")
            return self._with_cors(status, payload, "application/json")
        if (
            self.command == "PUT"
            and path.startswith("/v1/policies/")
            and not path.endswith("/disable")
            and not path.startswith("/v1/policies/effective/")
            and path != "/v1/policies/audit"
            and path != "/v1/policies/resolved"
        ):
            status, data = policy_update(path.split("/v1/policies/", 1)[1], body, self._headers_dict())
            payload = __import__("json").dumps(data).encode("utf-8")
            return self._with_cors(status, payload, "application/json")
        if self.command == "POST" and path.startswith("/v1/policies/") and path.endswith("/disable"):
            policy_id = path.split("/v1/policies/", 1)[1].rsplit("/disable", 1)[0]
            status, data = policy_disable(policy_id, self._headers_dict())
            payload = __import__("json").dumps(data).encode("utf-8")
            return self._with_cors(status, payload, "application/json")
        if self.command == "GET" and path == "/v1/policies/audit":
            status, data = policy_audit_list(body, self._headers_dict(), query)
            payload = __import__("json").dumps(data).encode("utf-8")
            return self._with_cors(status, payload, "application/json")
        if self.command == "GET" and path.startswith("/v1/health/tenants/"):
            status, data = health_tenant(path.split("/v1/health/tenants/", 1)[1])
            payload = __import__("json").dumps(data).encode("utf-8")
            return self._with_cors(status, payload, "application/json")

        if self.command == "GET" and path == "/v1/recommendations":
            data = {"items": recommendations_all()}
            payload = __import__("json").dumps(data).encode("utf-8")
            return self._with_cors(200, payload, "application/json")
        if self.command == "GET" and path.startswith("/v1/recommendations/devices/"):
            device_id = path.split("/v1/recommendations/devices/", 1)[1]
            data = {"items": recommendations_for_device(device_id)}
            payload = __import__("json").dumps(data).encode("utf-8")
            return self._with_cors(200, payload, "application/json")
        if self.command == "GET" and path.startswith("/v1/recommendations/tenants/"):
            tenant_id = path.split("/v1/recommendations/tenants/", 1)[1]
            data = {"items": recommendations_for_tenant(tenant_id)}
            payload = __import__("json").dumps(data).encode("utf-8")
            return self._with_cors(200, payload, "application/json")

        status, payload, content_type = router.dispatch(self.command, path, body, self._headers_dict())
        self._with_cors(status, payload, content_type)

    def do_OPTIONS(self) -> None:  # noqa: N802
        self._with_cors(HTTPStatus.NO_CONTENT, b"", "text/plain")

    def do_GET(self) -> None:  # noqa: N802
        self._handle()

    def do_POST(self) -> None:  # noqa: N802
        self._handle()

    def do_PUT(self) -> None:  # noqa: N802
        self._handle()

    def log_message(self, format: str, *args) -> None:
        return


def create_server() -> ThreadingHTTPServer:
    settings = get_settings()
    return ThreadingHTTPServer((settings.host, settings.port), RequestHandler)
