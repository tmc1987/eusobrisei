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
                    if not result.success:
                        fallback = self._try_safety_fallback(req, result.message)
                        if fallback:
                            result = fallback
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

    def _try_safety_fallback(self, req: ActionRequest, reason: str) -> ActionResult | None:
        allowed = set(self.config.get("actions", {}).get("allowed_actions", []))
        if "thermal_protect" not in allowed:
            return None
        fallback = self._thermal_protect()
        if not fallback.success:
            return None
        fallback.message = f"{fallback.message} (fallback após throttling indisponível: {reason})"
        fallback.human_recommendation = (
            "Processo não elegível para ajuste automático. Mitigação conservadora aplicada; "
            "coletar evidências e conduzir correção humana do aplicativo."
        )
        fallback.severity = req.severity
        fallback.outcome = "mitigated"
        fallback.operational_context = {
            **(fallback.operational_context or {}),
            "fallback_from": req.action,
            "fallback_reason": reason,
        }
        return fallback

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
        blocked_names = self._blocked_for_throttle()
        candidates = []
        if target_name:
            target_lower = str(target_name).lower()
            candidates.extend([p for p in processes if p.name.lower() == target_lower])
            candidates.extend([p for p in processes if p.name.lower() != target_lower])
        else:
            candidates = processes

        skip_reasons: List[str] = []
        for target in candidates:
            if target.name.lower() in blocked_names:
                skip_reasons.append(f"{target.name}: protegido")
                continue
            try:
                proc = psutil.Process(target.pid)
                old_nice = proc.nice()

                if platform.system().lower() == "windows":
                    proc.nice(psutil.BELOW_NORMAL_PRIORITY_CLASS)
                    new_priority = "below_normal"
                else:
                    proc.nice(min(old_nice + 5, 19))
                    new_priority = "nice+5"

                rollback_at = time.time() + int(self.config["actions"].get("priority_rollback_seconds", 120))
                self._priority_rollback.append({"pid": target.pid, "old_nice": old_nice, "rollback_at": rollback_at})

                return ActionResult(
                    "throttle_top_cpu_process",
                    True,
                    f"Prioridade reduzida para {target.name} (PID {target.pid})",
                    outcome="mitigated",
                    evidence={"target_pid": target.pid, "target_name": target.name, "resource": resource, "new_priority": new_priority},
                    operational_context={"rollback_at": rollback_at},
                )
            except (psutil.NoSuchProcess, psutil.AccessDenied, PermissionError) as exc:
                skip_reasons.append(f"{target.name}: {exc.__class__.__name__}")
                continue

        detail = "; ".join(skip_reasons[:4]) if skip_reasons else "sem processos candidatos"
        return ActionResult(
            "throttle_top_cpu_process",
            False,
            "Nenhum processo elegível para throttling seguro",
            outcome="failed",
            human_recommendation="Aplicativo protegido/crítico ou sem permissão de ajuste. Priorizar correção manual do app recorrente.",
            evidence={"skip_reasons": skip_reasons[:10], "resource": resource, "target_name": target_name, "detail": detail},
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

    def _blocked_for_throttle(self) -> set[str]:
        critical = {c.lower() for c in self.config.get("processes", {}).get("critical_names", [])}
        explicit = {c.lower() for c in self.config.get("processes", {}).get("non_throttle_names", [])}
        default_windows_protected = {
            "systemsettings.exe",
            "dwm.exe",
            "csrss.exe",
            "wininit.exe",
            "winlogon.exe",
            "lsass.exe",
        }
        return critical | explicit | default_windows_protected

    @staticmethod
    def _action_key(req: ActionRequest) -> str:
        target = req.params.get("name") or req.params.get("target_name") or req.params.get("pid") or "global"
        return f"{req.action}:{target}"
