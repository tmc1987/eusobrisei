from __future__ import annotations

import platform
import subprocess
import time
from dataclasses import dataclass
from typing import Dict, List, Optional

from .rules import ActionRequest

try:
    import psutil
except ModuleNotFoundError:
    psutil = None


@dataclass
class ActionResult:
    action: str
    success: bool
    message: str
    cooldown_applied: bool = False


class ActionExecutor:
    """Executa ações automáticas com foco em segurança e reversibilidade."""

    def __init__(self, config: Dict):
        self.config = config
        self._priority_rollback: List[Dict] = []
        self._last_action_at: Dict[str, float] = {}

    def execute(self, requests: List[ActionRequest], snapshot: Dict) -> List[ActionResult]:
        results: List[ActionResult] = []
        self._restore_priorities_if_due()

        for req in requests:
            cooldown = int(self.config.get("actions", {}).get("cooldown_seconds", 0))
            now = time.time()
            last = self._last_action_at.get(req.action, 0)
            if cooldown > 0 and (now - last) < cooldown:
                results.append(ActionResult(req.action, False, f"Cooldown ativo para {req.action}", cooldown_applied=True))
                continue

            try:
                if req.action == "throttle_top_cpu_process":
                    result = self._throttle_top_cpu_process(snapshot)
                elif req.action == "thermal_protect":
                    result = self._thermal_protect()
                elif req.action == "restart_process":
                    result = self._restart_process(req.params.get("name"), req.params.get("pid"))
                else:
                    result = ActionResult(req.action, False, "Ação desconhecida")

                if result.success:
                    self._last_action_at[req.action] = now
                results.append(result)
            except Exception as exc:
                results.append(ActionResult(req.action, False, f"Falha na ação: {exc}"))

        return results

    def _throttle_top_cpu_process(self, snapshot: Dict) -> ActionResult:
        if not psutil:
            return ActionResult("throttle_top_cpu_process", False, "STUB: psutil não instalado")

        processes = sorted(snapshot["processes"], key=lambda p: p.cpu_percent, reverse=True)
        critical = set(self.config["processes"].get("critical_names", []))
        critical_lower = {c.lower() for c in critical}

        target = next((p for p in processes if p.name.lower() not in critical_lower), None)
        if not target:
            return ActionResult("throttle_top_cpu_process", False, "Nenhum processo elegível para throttling")

        proc = psutil.Process(target.pid)
        old_nice = proc.nice()

        if platform.system().lower() == "windows":
            proc.nice(psutil.BELOW_NORMAL_PRIORITY_CLASS)
        else:
            proc.nice(min(old_nice + 5, 19))

        rollback_at = time.time() + int(self.config["actions"].get("priority_rollback_seconds", 120))
        self._priority_rollback.append({"pid": target.pid, "old_nice": old_nice, "rollback_at": rollback_at})

        return ActionResult("throttle_top_cpu_process", True, f"Prioridade reduzida para {target.name} (PID {target.pid})")

    def _restore_priorities_if_due(self) -> None:
        if not psutil:
            return

        remaining = []
        now = time.time()
        for item in self._priority_rollback:
            if now < item["rollback_at"]:
                remaining.append(item)
                continue
            try:
                psutil.Process(item["pid"]).nice(item["old_nice"])
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass
        self._priority_rollback = remaining

    def _thermal_protect(self) -> ActionResult:
        if platform.system().lower() != "windows":
            return ActionResult("thermal_protect", False, "STUB: proteção térmica automática apenas no Windows")

        try:
            subprocess.run(["powercfg", "/SETACTIVE", "SCHEME_BALANCED"], check=False, capture_output=True)
            return ActionResult("thermal_protect", True, "Plano de energia ajustado para Balanced")
        except OSError as exc:
            return ActionResult("thermal_protect", False, f"Falha ao acionar proteção térmica: {exc}")

    def _restart_process(self, name: Optional[str], pid: Optional[int]) -> ActionResult:
        if not name:
            return ActionResult("restart_process", False, "Nome do processo ausente")

        allowlist = {p.lower() for p in self.config.get("processes", {}).get("restart_allowlist", [])}
        if allowlist and name.lower() not in allowlist:
            return ActionResult("restart_process", False, f"Processo fora da allowlist de restart: {name}")

        critical = {c.lower() for c in self.config["processes"].get("critical_names", [])}
        if name.lower() in critical:
            return ActionResult("restart_process", False, f"Processo crítico não será reiniciado: {name}")

        restart_cmd = self.config["processes"].get("restart_commands", {}).get(name.lower())
        if not restart_cmd:
            return ActionResult("restart_process", False, f"STUB: sem comando de restart mapeado para {name}")

        if not psutil:
            return ActionResult("restart_process", False, "STUB: psutil não instalado")

        try:
            if pid:
                psutil.Process(int(pid)).terminate()
            subprocess.Popen(restart_cmd, shell=True)
            return ActionResult("restart_process", True, f"Processo {name} reiniciado com segurança")
        except (psutil.NoSuchProcess, psutil.AccessDenied, OSError) as exc:
            return ActionResult("restart_process", False, f"Falha ao reiniciar {name}: {exc}")
