from __future__ import annotations

from dataclasses import dataclass
from typing import Dict


@dataclass
class ProcessSample:
    pid: int
    name: str
    cpu_percent: float
    memory_percent: float
    status: str
    create_time: float
    io_read_bytes: float = 0.0
    io_write_bytes: float = 0.0


@dataclass
class Alert:
    code: str
    severity: str
    message: str
    context: Dict
