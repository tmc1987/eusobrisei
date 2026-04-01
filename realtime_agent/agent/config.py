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

    return data
