from __future__ import annotations

import platform
import subprocess
import time
import ctypes
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
        self._total_memory_bytes = psutil.virtual_memory().total if psutil else 1
        self._proc_cpu_last: Dict[int, tuple[float, float]] = {}
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
        # Cálculo orientado a delta de cpu_times para reduzir oscilação e manter
        # equivalência com escala do Task Manager (0-100% total da máquina).
        raw_procs = []
        for proc in psutil.process_iter(["pid", "name", "status", "create_time"]):
            try:
                raw_procs.append(proc)
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue

        samples: List[ProcessSample] = []
        now = time.time()
        next_last: Dict[int, tuple[float, float]] = {}
        for proc in raw_procs:
            try:
                info = proc.as_dict(attrs=["pid", "name", "status", "create_time"])
                pid = int(info["pid"])
                cpu_total = self._process_total_cpu_time(proc)
                cpu = self._compute_process_cpu_percent(pid=pid, cpu_total=cpu_total, now=now, proc=proc)
                mem = self._memory_percent(proc)
                samples.append(
                    ProcessSample(
                        pid=pid,
                        name=info.get("name") or "unknown",
                        cpu_percent=cpu,
                        memory_percent=mem,
                        status=info.get("status") or "unknown",
                        create_time=info.get("create_time") or 0.0,
                        io_read_bytes=float((proc.io_counters().read_bytes if proc.io_counters() else 0.0)),
                        io_write_bytes=float((proc.io_counters().write_bytes if proc.io_counters() else 0.0)),
                    )
                )
                next_last[pid] = (now, cpu_total)
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue
        self._proc_cpu_last = next_last
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

    def _memory_percent(self, proc) -> float:
        try:
            return max(0.0, min(100.0, float(proc.memory_percent(memtype="rss"))))
        except (psutil.NoSuchProcess, psutil.AccessDenied, AttributeError):
            return 0.0

    @staticmethod
    def _process_total_cpu_time(proc) -> float:
        times = proc.cpu_times()
        return float(getattr(times, "user", 0.0) + getattr(times, "system", 0.0))

    def _compute_process_cpu_percent(self, pid: int, cpu_total: float, now: float, proc) -> float:
        prev = self._proc_cpu_last.get(pid)
        if prev:
            prev_ts, prev_total = prev
            elapsed = max(now - prev_ts, 0.001)
            delta = max(cpu_total - prev_total, 0.0)
            # escala 0-100 no total da máquina (equivalente visual ao Task Manager)
            return max(0.0, min(100.0, (delta / elapsed) * 100.0 / max(float(self._cpu_count), 1.0)))
        # fallback na primeira amostra
        return self._normalize_process_cpu(proc.cpu_percent(interval=None))

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

        api_result = self._get_hung_processes_windows_api()
        if api_result is not None:
            return api_result

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

    def _get_hung_processes_windows_api(self) -> Optional[List[int]]:
        """
        Implementação preferencial via Win32 API (mais leve que abrir PowerShell
        a cada ciclo). Retorna None quando a API não estiver disponível.
        """
        if platform.system().lower() != "windows":
            return []
        try:
            user32 = ctypes.windll.user32
            pids = set()

            WNDENUMPROC = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_void_p, ctypes.c_void_p)

            def _enum_windows(hwnd, _lparam):
                if not user32.IsWindowVisible(hwnd):
                    return True
                if not user32.IsHungAppWindow(hwnd):
                    return True
                pid = ctypes.c_ulong()
                user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
                if pid.value:
                    pids.add(int(pid.value))
                return True

            user32.EnumWindows(WNDENUMPROC(_enum_windows), 0)
            return sorted(pids)
        except Exception:
            return None
