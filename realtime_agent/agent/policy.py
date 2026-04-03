from __future__ import annotations

import json
import time
import urllib.request
from typing import Dict, Optional


class PolicyClient:
    def __init__(self, server_cfg: Dict, identity: Dict):
        self.server_cfg = server_cfg
        self.identity = identity
        self._last_fetch = 0.0
        self._cached: Optional[Dict] = None

    def fetch_if_due(self, interval_seconds: int = 60) -> Optional[Dict]:
        now = time.time()
        if now - self._last_fetch < interval_seconds:
            return self._cached

        self._last_fetch = now
        url = self.server_cfg["url"].rstrip("/") + "/v1/policies/resolved"
        req = urllib.request.Request(
            url=url,
            method="GET",
            headers={
                "Authorization": f"Bearer {self.server_cfg.get('token', '')}",
                "X-Agent-Id": self.identity["agent_id"],
                "X-Request-Id": f"pol-{int(now)}",
            },
        )
        try:
            with urllib.request.urlopen(req, timeout=float(self.server_cfg.get("timeout_seconds", 5))) as resp:
                self._cached = json.loads(resp.read().decode("utf-8"))
                return self._cached
        except Exception:
            return None


def apply_effective_policy(base_config: Dict, policy: Optional[Dict]) -> Dict:
    merged = json.loads(json.dumps(base_config))
    if not policy:
        return merged

    merged.setdefault("meta", {})
    merged["meta"]["active_policy_version"] = policy.get("version")

    if "thresholds" in policy:
        merged["thresholds"].update(policy["thresholds"])

    p_actions = policy.get("actions", {})
    if "enabled" in p_actions:
        merged["actions"]["enabled"] = p_actions["enabled"]
    if "safe_mode" in p_actions:
        merged["actions"]["safe_mode"] = p_actions["safe_mode"]
    if "cooldown_seconds" in p_actions:
        merged["actions"]["cooldown_seconds"] = p_actions["cooldown_seconds"]
    if "restart_allowlist" in p_actions:
        merged.setdefault("processes", {})["restart_allowlist"] = p_actions["restart_allowlist"]
    if "rate_limit" in p_actions and "max_actions_per_hour" in p_actions["rate_limit"]:
        merged.setdefault("server", {}).setdefault("retry", {})["max_actions_per_hour"] = p_actions["rate_limit"]["max_actions_per_hour"]

    return merged
