from __future__ import annotations

import json
import random
import time
import urllib.error
import urllib.request
import uuid
from typing import Dict, Tuple

from .outbox import Outbox


class Transport:
    def __init__(self, config: Dict, outbox: Outbox):
        self.cfg = config
        self.outbox = outbox

    def send_heartbeat(self, payload: Dict) -> None:
        self.outbox.enqueue("/v1/agents/heartbeat", payload, idempotency_key=str(uuid.uuid4()))

    def send_events_batch(self, payload: Dict) -> None:
        self.outbox.enqueue("/v1/ingestion/events:batch", payload, idempotency_key=str(uuid.uuid4()))

    def send_action_audit_batch(self, payload: Dict) -> None:
        self.outbox.enqueue("/v1/audit/actions:batch", payload, idempotency_key=str(uuid.uuid4()))

    def flush(self, logger) -> None:
        for item in self.outbox.due_items(limit=100):
            ok, status, body = self._post(item.endpoint, item.payload, item.idempotency_key)
            if ok:
                logger.info("TRANSPORT | sent endpoint=%s status=%s", item.endpoint, status)
                self.outbox.mark_sent(item.id)
            else:
                delay = self._next_backoff(item.attempt_count)
                self.outbox.mark_retry(item.id, time.time() + delay)
                logger.warning("TRANSPORT | retry endpoint=%s status=%s backoff=%.2fs body=%s", item.endpoint, status, delay, body)

    def _next_backoff(self, attempt_count: int) -> float:
        retry_cfg = self.cfg["retry"]
        base = float(retry_cfg.get("base_seconds", 1.0))
        max_wait = float(retry_cfg.get("max_seconds", 30.0))
        jitter = float(retry_cfg.get("jitter_ratio", 0.2))
        exp = min(base * (2**attempt_count), max_wait)
        return exp * (1 + random.uniform(0, jitter))

    def _post(self, path: str, payload: Dict, idempotency_key: str) -> Tuple[bool, int, str]:
        url = self.cfg["url"].rstrip("/") + path
        request_id = str(uuid.uuid4())
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.cfg.get('token', 'dev-token')}",
            "X-Agent-Id": self.cfg["agent_id"],
            "X-Request-Id": request_id,
            "Idempotency-Key": idempotency_key,
        }
        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(url=url, data=data, headers=headers, method="POST")
        timeout = float(self.cfg.get("timeout_seconds", 5))

        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                body = resp.read().decode("utf-8")
                return 200 <= resp.status < 300, resp.status, body
        except urllib.error.HTTPError as exc:
            try:
                body = exc.read().decode("utf-8")
            except Exception:
                body = ""
            # retry only for transient statuses
            if exc.code in {408, 429, 500, 502, 503, 504}:
                return False, exc.code, body
            return True, exc.code, body
        except Exception as exc:
            return False, 0, str(exc)
