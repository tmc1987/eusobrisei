from __future__ import annotations

import json
import sqlite3
import time
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List


@dataclass
class OutboxItem:
    id: int
    endpoint: str
    payload: Dict
    idempotency_key: str
    attempt_count: int


class Outbox:
    def __init__(self, db_path: str):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _connect(self):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS outbox (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    endpoint TEXT NOT NULL,
                    payload TEXT NOT NULL,
                    idempotency_key TEXT NOT NULL,
                    attempt_count INTEGER NOT NULL DEFAULT 0,
                    next_attempt_at REAL NOT NULL,
                    created_at REAL NOT NULL
                )
                """
            )

    def enqueue(self, endpoint: str, payload: Dict, idempotency_key: str | None = None) -> None:
        idem = idempotency_key or str(uuid.uuid4())
        now = time.time()
        with self._connect() as conn:
            conn.execute(
                "INSERT INTO outbox (endpoint, payload, idempotency_key, attempt_count, next_attempt_at, created_at) VALUES (?, ?, ?, 0, ?, ?)",
                (endpoint, json.dumps(payload), idem, now, now),
            )

    def due_items(self, limit: int = 50) -> List[OutboxItem]:
        now = time.time()
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT id, endpoint, payload, idempotency_key, attempt_count FROM outbox WHERE next_attempt_at <= ? ORDER BY id ASC LIMIT ?",
                (now, limit),
            ).fetchall()
        return [
            OutboxItem(
                id=row["id"],
                endpoint=row["endpoint"],
                payload=json.loads(row["payload"]),
                idempotency_key=row["idempotency_key"],
                attempt_count=row["attempt_count"],
            )
            for row in rows
        ]

    def mark_sent(self, item_id: int) -> None:
        with self._connect() as conn:
            conn.execute("DELETE FROM outbox WHERE id = ?", (item_id,))

    def mark_retry(self, item_id: int, next_attempt_at: float) -> None:
        with self._connect() as conn:
            conn.execute(
                "UPDATE outbox SET attempt_count = attempt_count + 1, next_attempt_at = ? WHERE id = ?",
                (next_attempt_at, item_id),
            )
