from __future__ import annotations

import platform
import subprocess
import time
from typing import Dict, List, Optional

from .models import ProcessSample

try:
    import psutil
except ModuleNotFoundError:  # ambiente sem dependências instaladas
    psutil = None


class Collector:
    """Coleta métricas de sistema e processos em tempo real."""

    def __init__(self) -> None:
        self._last_call_ts = time.time()
        self._cpu_count = psutil.cpu_count(logical=True) if psutil else 1
        if psutil:
            psutil.cpu_percent(interval=None)

    def collect(self) -> Dict:
        if not psutil:
            raise RuntimeError("Dependência 'psutil' não instalada. Execute: pip install -r requirements.txt")

        now = time.time()
        elapsed = max(now - self._last_call_ts, 0.001)
        self._last_call_ts = now

        data = {
            "timestamp": now,
            "elapsed_seconds": elapsed,
            "cpu_percent": psutil.cpu_percent(interval=None),
            "ram_percent": psutil.virtual_memory().percent,
            "disk_percent": psutil.disk_usage("/").percent,
            "temperature_c": self._get_temperature(),
            "processes": self._get_processes(),
            "hung_processes": self._get_hung_processes_windows(),
        }
        return data

    def _get_processes(self) -> List[ProcessSample]:
        samples: List[ProcessSample] = []
        for proc in psutil.process_iter(["pid", "name", "cpu_percent", "memory_percent", "status", "create_time"]):
            try:
                info = proc.info
                samples.append(
                    ProcessSample(
                        pid=info["pid"],
                        name=info.get("name") or "unknown",
                        cpu_percent=self._normalize_process_cpu(info.get("cpu_percent") or 0.0),
                        memory_percent=info.get("memory_percent") or 0.0,
                        status=info.get("status") or "unknown",
                        create_time=info.get("create_time") or 0.0,
                        io_read_bytes=float((proc.io_counters().read_bytes if proc.io_counters() else 0.0)),
                        io_write_bytes=float((proc.io_counters().write_bytes if proc.io_counters() else 0.0)),
                    )
                )
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue
        return samples

    def _normalize_process_cpu(self, value: float) -> float:
        """
        psutil no Windows pode reportar CPU por processo acima de 100%
        (soma em múltiplos núcleos). Para comunicação com cliente e
        alinhamento com Task Manager, normalizamos para base 0-100%.
        """
        cpu_count = max(int(self._cpu_count or 1), 1)
        normalized = float(value) / cpu_count
        return max(0.0, min(100.0, normalized))

    def _get_temperature(self) -> Optional[float]:
        try:
            temps = psutil.sensors_temperatures()
            if not temps:
                return None
            values = []
            for entries in temps.values():
                for entry in entries:
                    if entry.current is not None:
                        values.append(float(entry.current))
            return max(values) if values else None
        except (AttributeError, NotImplementedError):
            return None

    def _get_hung_processes_windows(self) -> List[int]:
        if platform.system().lower() != "windows":
            return []

        cmd = [
            "powershell",
            "-NoProfile",
            "-Command",
            "Get-Process | Where-Object {$_.Responding -eq $false} | Select-Object -ExpandProperty Id",
        ]

        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=5, check=False)
            return [int(line.strip()) for line in result.stdout.splitlines() if line.strip().isdigit()]
        except (subprocess.SubprocessError, OSError):
            return []
