from __future__ import annotations

from collections import deque
import time
from typing import Deque, Dict, List, Optional

from .models import Alert, ProcessSample


class Analyzer:
    def __init__(self, thresholds: Dict):
        self.thresholds = thresholds
        self._ram_history: Deque[float] = deque(maxlen=12)
        self._cpu_history: Deque[float] = deque(maxlen=12)
        self._disk_history: Deque[float] = deque(maxlen=12)
        self._hung_tracker: Dict[int, Dict[str, float]] = {}
        self._hung_emit_interval_seconds = int(thresholds.get("hung_emit_interval_seconds", 60))

    def analyze(self, snapshot: Dict) -> List[Alert]:
        alerts: List[Alert] = []

        cpu = snapshot["cpu_percent"]
        ram = snapshot["ram_percent"]
        disk = snapshot["disk_percent"]
        temp = snapshot["temperature_c"]

        self._ram_history.append(float(ram))
        self._cpu_history.append(float(cpu))
        self._disk_history.append(float(disk))
        top_cpu = self._top_processes(snapshot["processes"], by="cpu_percent")
        top_ram = self._top_processes(snapshot["processes"], by="memory_percent")
        top_disk = self._top_processes(snapshot["processes"], by="io_total")

        if cpu >= self.thresholds["cpu_percent"]:
            alerts.append(
                Alert(
                    "HIGH_CPU",
                    "high",
                    f"CPU alto: {cpu:.1f}%",
                    {
                        "cpu_percent": cpu,
                        "top_cpu_processes": top_cpu,
                        "probable_cause": "abusive_process" if top_cpu and top_cpu[0]["cpu_percent"] >= 35 else "distributed_load",
                        "structural_suspect": self._is_recurring(self._cpu_history, self.thresholds["cpu_percent"]) and (not top_cpu or top_cpu[0]["cpu_percent"] < 35),
                        "recurrence_hint": "recurring" if self._is_recurring(self._cpu_history, self.thresholds["cpu_percent"]) else "point_spike",
                    },
                )
            )

        if ram >= self.thresholds["ram_percent"]:
            top_share = sum(p["memory_percent"] for p in top_ram[:3]) if top_ram else 0.0
            structural = self._is_recurring(self._ram_history, self.thresholds["ram_percent"]) and top_share < 55
            alerts.append(
                Alert(
                    "HIGH_RAM",
                    "high",
                    f"RAM alta: {ram:.1f}%",
                    {
                        "ram_percent": ram,
                        "top_ram_processes": top_ram,
                        "top3_ram_share_percent": round(top_share, 2),
                        "probable_cause": "structural_memory_pressure" if structural else "process_memory_pressure",
                        "recurrence_hint": "recurring" if self._is_recurring(self._ram_history, self.thresholds["ram_percent"]) else "point_spike",
                    },
                )
            )

        if disk >= self.thresholds["disk_percent"]:
            top_disk_share = sum(p["io_share_percent"] for p in top_disk[:3]) if top_disk else 0.0
            disk_structural = self._is_recurring(self._disk_history, self.thresholds["disk_percent"]) and top_disk_share < 55
            alerts.append(
                Alert(
                    "HIGH_DISK",
                    "medium",
                    f"Disco alto: {disk:.1f}%",
                    {
                        "disk_percent": disk,
                        "top_disk_processes": top_disk,
                        "top3_disk_share_percent": round(top_disk_share, 2),
                        "probable_cause": "structural_disk_pressure" if disk_structural else "disk_io_process_pressure",
                        "recurrence_hint": "recurring" if self._is_recurring(self._disk_history, self.thresholds["disk_percent"]) else "point_spike",
                    },
                )
            )

        if temp is not None and temp >= self.thresholds["temperature_c"]:
            alerts.append(Alert("HIGH_TEMP", "critical", f"Temperatura alta: {temp:.1f}°C", {"temperature_c": temp}))

        alerts.extend(self._analyze_hung_processes(snapshot["processes"], snapshot["hung_processes"]))
        return alerts

    @staticmethod
    def _top_processes(processes: List[ProcessSample], by: str) -> List[Dict]:
        def _metric(p: ProcessSample) -> float:
            if by == "io_total":
                return float(p.io_read_bytes + p.io_write_bytes)
            return float(getattr(p, by))

        ordered = sorted(processes, key=_metric, reverse=True)[:5]
        total = sum(_metric(p) for p in processes) or 1.0
        out = []
        for p in ordered:
            io_total = float(p.io_read_bytes + p.io_write_bytes)
            out.append(
                {
                    "pid": p.pid,
                    "name": p.name,
                    "cpu_percent": round(p.cpu_percent, 2),
                    "memory_percent": round(p.memory_percent, 2),
                    "io_total_bytes": round(io_total, 2),
                    "io_share_percent": round((io_total / total) * 100 if by == "io_total" else 0.0, 2),
                    "status": p.status,
                }
            )
        return out

    @staticmethod
    def _is_recurring(history: Deque[float], threshold: float) -> bool:
        if len(history) < 4:
            return False
        return sum(1 for x in history if x >= threshold) >= max(3, int(len(history) * 0.6))

    def _analyze_hung_processes(self, processes: List[ProcessSample], hung_pids: List[int]) -> List[Alert]:
        if not hung_pids:
            self._hung_tracker.clear()
            return []

        by_pid = {p.pid: p for p in processes}
        alerts: List[Alert] = []
        now = time.time()
        current = set(hung_pids)
        for known in list(self._hung_tracker.keys()):
            if known not in current:
                self._hung_tracker.pop(known, None)

        for pid in hung_pids:
            proc: Optional[ProcessSample] = by_pid.get(pid)
            name = proc.name if proc else "unknown"
            state = self._hung_tracker.get(pid)
            if not state:
                state = {"first_seen": now, "last_emitted": 0.0, "count": 0.0}
                self._hung_tracker[pid] = state
            state["count"] += 1
            should_emit = (now - state["last_emitted"]) >= self._hung_emit_interval_seconds
            if not should_emit:
                continue
            state["last_emitted"] = now
            alerts.append(
                Alert(
                    "HUNG_PROCESS",
                    "high",
                    f"Processo travado detectado: {name} (PID {pid})",
                    {
                        "pid": pid,
                        "name": name,
                        "recurrence_count": int(state["count"]),
                        "hung_for_seconds": round(now - state["first_seen"], 1),
                    },
                )
            )
        return alerts
