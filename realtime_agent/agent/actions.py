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
    severity: str = "medium"
    outcome: str = "failed"  # resolved | mitigated | failed
    human_recommendation: str = ""
    evidence: Dict | None = None
    operational_context: Dict | None = None


class ActionExecutor:
    """Executa ações automáticas com foco em segurança e reversibilidade."""

    def __init__(self, config: Dict):
        self.config = config
        self._priority_rollback: List[Dict] = []
        self._last_action_at: Dict[str, float] = {}
        self._ineffective_count: Dict[str, int] = {}

    def execute(self, requests: List[ActionRequest], snapshot: Dict) -> List[ActionResult]:
        results: List[ActionResult] = []
        self._restore_priorities_if_due()

        for req in requests:
            action_key = self._action_key(req)
            if self._ineffective_count.get(action_key, 0) >= 2:
                results.append(
                    ActionResult(
                        req.action,
                        False,
                        f"Ação suprimida por recorrência ineficaz ({self._ineffective_count[action_key]} falhas): {req.action}",
                        severity=req.severity,
                        outcome="failed",
                        human_recommendation=req.human_recommendation or "Mitigação local esgotada. Requer intervenção humana.",
                        evidence={"suppressed": True, "ineffective_count": self._ineffective_count[action_key]},
                        operational_context={"action_key": action_key},
                    )
                )
                continue

            cooldown = int(self.config.get("actions", {}).get("cooldown_seconds", 0))
            now = time.time()
            last = self._last_action_at.get(action_key, 0)
            if cooldown > 0 and (now - last) < cooldown:
                results.append(
                    ActionResult(
                        req.action,
                        False,
                        f"Cooldown ativo para {req.action}",
                        cooldown_applied=True,
                        severity=req.severity,
                        outcome="mitigated",
                        human_recommendation="Aguardar cooldown para evitar loop de autoação.",
                        evidence={"cooldown_seconds": cooldown, "seconds_remaining": round(cooldown - (now - last), 2)},
                        operational_context={"action_key": action_key},
                    )
                )
                continue

            try:
                if req.action == "throttle_top_cpu_process":
                    result = self._throttle_top_cpu_process(snapshot, req.params.get("target_name"), req.params.get("resource", "cpu"))
                elif req.action == "thermal_protect":
                    result = self._thermal_protect()
                elif req.action == "restart_process":
                    result = self._restart_process(req.params.get("name"), req.params.get("pid"))
                else:
                    result = ActionResult(req.action, False, "Ação desconhecida")

                result.severity = req.severity
                result.human_recommendation = result.human_recommendation or req.human_recommendation
                result.operational_context = {
                    **(result.operational_context or {}),
                    "action_key": action_key,
                    "recurrence_count": req.recurrence_count,
                    "strategy": req.strategy,
                    "decision_confidence": req.confidence,
                }

                if result.success:
                    self._last_action_at[action_key] = now
                    self._ineffective_count[action_key] = 0
                else:
                    self._ineffective_count[action_key] = self._ineffective_count.get(action_key, 0) + 1
                results.append(result)
            except Exception as exc:
                self._ineffective_count[action_key] = self._ineffective_count.get(action_key, 0) + 1
                results.append(
                    ActionResult(
                        req.action,
                        False,
                        f"Falha na ação: {exc}",
                        severity=req.severity,
                        outcome="failed",
                        human_recommendation=req.human_recommendation,
                        evidence={"exception": str(exc)},
                        operational_context={"action_key": action_key},
                    )
                )

        return results

    def _throttle_top_cpu_process(self, snapshot: Dict, target_name: str | None = None, resource: str = "cpu") -> ActionResult:
        if not psutil:
            return ActionResult("throttle_top_cpu_process", False, "STUB: psutil não instalado")

        if resource == "memory":
            score = lambda p: p.memory_percent
        elif resource == "disk":
            score = lambda p: (p.io_read_bytes + p.io_write_bytes)
        else:
            score = lambda p: p.cpu_percent
        processes = sorted(snapshot["processes"], key=score, reverse=True)
        critical = set(self.config["processes"].get("critical_names", []))
        critical_lower = {c.lower() for c in critical}
        target = None
        if target_name:
            target = next((p for p in processes if p.name.lower() == str(target_name).lower() and p.name.lower() not in critical_lower), None)
        if target is None:
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

        return ActionResult(
            "throttle_top_cpu_process",
            True,
            f"Prioridade reduzida para {target.name} (PID {target.pid})",
            outcome="mitigated",
            evidence={"target_pid": target.pid, "target_name": target.name, "resource": resource, "new_priority": "below_normal"},
            operational_context={"rollback_at": rollback_at},
        )

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
            return ActionResult(
                "thermal_protect",
                True,
                "Plano de energia ajustado para Balanced",
                outcome="mitigated",
                evidence={"power_plan": "balanced"},
            )
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
            return ActionResult(
                "restart_process",
                True,
                f"Processo {name} reiniciado com segurança",
                outcome="resolved",
                evidence={"process_name": name, "pid": pid},
            )
        except (psutil.NoSuchProcess, psutil.AccessDenied, OSError) as exc:
            return ActionResult("restart_process", False, f"Falha ao reiniciar {name}: {exc}")

    @staticmethod
    def _action_key(req: ActionRequest) -> str:
        target = req.params.get("name") or req.params.get("target_name") or req.params.get("pid") or "global"
        return f"{req.action}:{target}"
