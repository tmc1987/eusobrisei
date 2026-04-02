from __future__ import annotations

from typing import Dict, List, Optional

from .models import Alert, ProcessSample


class Analyzer:
    def __init__(self, thresholds: Dict):
        self.thresholds = thresholds

    def analyze(self, snapshot: Dict) -> List[Alert]:
        alerts: List[Alert] = []

        cpu = snapshot["cpu_percent"]
        ram = snapshot["ram_percent"]
        disk = snapshot["disk_percent"]
        temp = snapshot["temperature_c"]

        if cpu >= self.thresholds["cpu_percent"]:
            alerts.append(Alert("HIGH_CPU", "high", f"CPU alto: {cpu:.1f}%", {"cpu_percent": cpu}))

        if ram >= self.thresholds["ram_percent"]:
            alerts.append(Alert("HIGH_RAM", "high", f"RAM alta: {ram:.1f}%", {"ram_percent": ram}))

        if disk >= self.thresholds["disk_percent"]:
            alerts.append(Alert("HIGH_DISK", "medium", f"Disco alto: {disk:.1f}%", {"disk_percent": disk}))

        if temp is not None and temp >= self.thresholds["temperature_c"]:
            alerts.append(Alert("HIGH_TEMP", "critical", f"Temperatura alta: {temp:.1f}°C", {"temperature_c": temp}))

        alerts.extend(self._analyze_hung_processes(snapshot["processes"], snapshot["hung_processes"]))
        return alerts

    def _analyze_hung_processes(self, processes: List[ProcessSample], hung_pids: List[int]) -> List[Alert]:
        if not hung_pids:
            return []

        by_pid = {p.pid: p for p in processes}
        alerts: List[Alert] = []
        for pid in hung_pids:
            proc: Optional[ProcessSample] = by_pid.get(pid)
            name = proc.name if proc else "unknown"
            alerts.append(
                Alert(
                    "HUNG_PROCESS",
                    "high",
                    f"Processo travado detectado: {name} (PID {pid})",
                    {"pid": pid, "name": name},
                )
            )
        return alerts
