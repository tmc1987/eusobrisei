from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict


class ConfigError(Exception):
    """Erro de configuração do agente."""


def load_config(path: str | Path) -> Dict[str, Any]:
    cfg_path = Path(path)
    if not cfg_path.exists():
        raise ConfigError(f"Arquivo de configuração não encontrado: {cfg_path}")

    try:
        data = json.loads(cfg_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ConfigError(f"JSON inválido em {cfg_path}: {exc}") from exc

    required_root = ["interval_seconds", "log_file", "thresholds", "actions", "processes"]
    missing = [key for key in required_root if key not in data]
    if missing:
        raise ConfigError(f"Configuração incompleta. Campos ausentes: {missing}")

    # defaults de fase 1 para integração agente -> servidor
    data.setdefault("identity", {})
    data["identity"].setdefault("tenant_id", "00000000-0000-0000-0000-000000000001")
    data["identity"].setdefault("device_id", "00000000-0000-0000-0000-000000000002")
    data["identity"].setdefault("agent_id", "00000000-0000-0000-0000-000000000003")
    data["identity"].setdefault("agent_version", "0.1.0")

    data.setdefault("server", {})
    data["server"].setdefault("enabled", False)
    data["server"].setdefault("url", "http://127.0.0.1:8080")
    data["server"].setdefault("token", "dev-token")
    data["server"].setdefault("timeout_seconds", 5)
    data["server"].setdefault("retry", {"base_seconds": 1, "max_seconds": 30, "jitter_ratio": 0.2})

    data.setdefault("outbox", {})
    data["outbox"].setdefault("db_path", "data/outbox.db")

    data.setdefault("policy", {})
    data["policy"].setdefault("fetch_interval_seconds", 60)

    data.setdefault("bootstrap", {})
    data["bootstrap"].setdefault("activation_token", "dev-bootstrap-token")
    data["bootstrap"].setdefault("identity_store_path", "data/identity.json")
    data["bootstrap"].setdefault("hostname", "dev-host")
    data["bootstrap"].setdefault("os_version", "Windows-dev")

    data.setdefault("processes", {})
    data["processes"].setdefault("restart_allowlist", [])
    data.setdefault("actions", {})
    data["actions"].setdefault("max_attempts_per_incident", 3)

    return data
