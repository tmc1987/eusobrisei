from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Tuple


@dataclass
class InMemoryStore:
    heartbeats: List[dict] = field(default_factory=list)
    events_batches: List[dict] = field(default_factory=list)
    idempotency: Dict[Tuple[str, str], dict] = field(default_factory=dict)


STORE = InMemoryStore()
