from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Settings:
    host: str
    port: int
    environment: str
    db_path: str
    bootstrap_token: str


def get_settings() -> Settings:
    return Settings(
        host=os.getenv("SERVER_HOST", "127.0.0.1"),
        port=int(os.getenv("SERVER_PORT", "8080")),
        environment=os.getenv("SERVER_ENV", "development"),
        db_path=os.getenv("SERVER_DB_PATH", "server/data/dev.db"),
        bootstrap_token=os.getenv("SERVER_BOOTSTRAP_TOKEN", "dev-bootstrap-token"),
    )
