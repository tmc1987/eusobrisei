from __future__ import annotations

import json
from http import HTTPStatus
from typing import Callable, Dict, Tuple

HandlerResult = Tuple[int, Dict]
HandlerFn = Callable[[bytes, Dict[str, str]], HandlerResult]


class Router:
    def __init__(self) -> None:
        self.routes: dict[tuple[str, str], HandlerFn] = {}

    def add(self, method: str, path: str, handler: HandlerFn) -> None:
        self.routes[(method.upper(), path)] = handler

    def dispatch(self, method: str, path: str, body: bytes, headers: Dict[str, str]) -> tuple[int, bytes, str]:
        handler = self.routes.get((method.upper(), path))
        if not handler:
            payload = {"error": "not_found", "path": path}
            return HTTPStatus.NOT_FOUND, json.dumps(payload).encode("utf-8"), "application/json"

        status, data = handler(body, headers)
        return status, json.dumps(data).encode("utf-8"), "application/json"
