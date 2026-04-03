from __future__ import annotations

import json
from pathlib import Path
from typing import Dict

import urllib.error
import urllib.request


class BootstrapError(Exception):
    pass


def load_identity(path: str) -> Dict | None:
    p = Path(path)
    if not p.exists():
        return None
    return json.loads(p.read_text(encoding="utf-8"))


def save_identity(path: str, identity: Dict) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(identity, indent=2), encoding="utf-8")


def bootstrap_if_needed(config: Dict, logger) -> Dict:
    identity_store = config.get("bootstrap", {}).get("identity_store_path", "data/identity.json")
    cached = load_identity(identity_store)
    if cached:
        logger.info("BOOTSTRAP | identidade local carregada")
        return cached

    payload = {
        "activation_token": config.get("bootstrap", {}).get("activation_token", "dev-bootstrap-token"),
        "hostname": config.get("bootstrap", {}).get("hostname", "dev-host"),
        "os_version": config.get("bootstrap", {}).get("os_version", "Windows-dev"),
        "agent_version": config.get("identity", {}).get("agent_version", "0.1.0"),
    }
    url = config["server"]["url"].rstrip("/") + "/v1/agents/bootstrap"
    req = urllib.request.Request(
        url=url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=float(config["server"].get("timeout_seconds", 5))) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8") if exc.fp else ""
        raise BootstrapError(f"bootstrap HTTP error {exc.code}: {body}") from exc
    except Exception as exc:
        raise BootstrapError(f"bootstrap falhou: {exc}") from exc

    identity = {
        "tenant_id": data["tenant_id"],
        "device_id": data["device_id"],
        "agent_id": data["agent_id"],
        "agent_version": payload["agent_version"],
        "token": data["access_token"],
    }
    save_identity(identity_store, identity)
    logger.info("BOOTSTRAP | agente registrado e identidade persistida")
    return identity
