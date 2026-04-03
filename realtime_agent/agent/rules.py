from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional

from .models import Alert


@dataclass
class ActionRequest:
    action: str
    reason: str
    params: Dict
    severity: str = "medium"
    recurrence_count: int = 1
    human_recommendation: str = ""
    strategy: str = "default"
    confidence: float = 0.5


class RuleEngine:
    """Converte alertas em ações automáticas seguras."""

    def __init__(self, config: Dict):
        self.config = config
        self._alert_counts: Dict[str, int] = {}
        self._suppressed_failures: Dict[str, int] = {}

    def evaluate(self, alerts: List[Alert], snapshot: Optional[Dict] = None) -> List[ActionRequest]:
        reqs: List[ActionRequest] = []
        safe_mode = self.config["actions"].get("safe_mode", True)
        allowed = set(self.config.get("actions", {}).get("allowed_actions", ["throttle_top_cpu_process", "thermal_protect", "restart_process"]))

        for alert in alerts:
            self._alert_counts[alert.code] = self._alert_counts.get(alert.code, 0) + 1
            rec = self._alert_counts[alert.code]
            if alert.code == "HIGH_CPU":
                req = self._plan_pressure_action(
                    alert=alert,
                    recurrence_count=rec,
                    safe_mode=safe_mode,
                    allowed=allowed,
                    resource="cpu",
                    top_process=(alert.context.get("top_cpu_processes") or [{}])[0] if alert.context else {"name": self._top_process_name(snapshot)},
                )
                if req:
                    reqs.append(req)
            elif alert.code == "HIGH_RAM":
                req = self._plan_pressure_action(
                    alert=alert,
                    recurrence_count=rec,
                    safe_mode=safe_mode,
                    allowed=allowed,
                    resource="memory",
                    top_process=(alert.context.get("top_ram_processes") or [{}])[0],
                )
                if req:
                    reqs.append(req)
            elif alert.code == "HIGH_TEMP" and "thermal_protect" in allowed:
                reqs.append(
                    ActionRequest(
                        action="thermal_protect",
                        reason=alert.message,
                        params={"safe_mode": safe_mode},
                        severity=alert.severity,
                        recurrence_count=rec,
                        human_recommendation="Se recorrente, revisar refrigeração física, limpeza, pasta térmica e airflow.",
                        strategy="thermal_guardrail",
                        confidence=0.85,
                    )
                )
            elif alert.code == "HIGH_DISK":
                req = self._plan_pressure_action(
                    alert=alert,
                    recurrence_count=rec,
                    safe_mode=safe_mode,
                    allowed=allowed,
                    resource="disk",
                    top_process=(alert.context.get("top_disk_processes") or [{}])[0],
                )
                if req:
                    reqs.append(req)
            elif alert.code == "HUNG_PROCESS" and self.config["actions"].get("auto_restart_hung_process", False) and "restart_process" in allowed:
                reqs.append(
                    ActionRequest(
                        action="restart_process",
                        reason=alert.message,
                        params={"pid": alert.context.get("pid"), "name": alert.context.get("name")},
                        severity=alert.severity,
                        recurrence_count=rec,
                        human_recommendation="Se não resolver, coletar dump/log do processo e abrir investigação humana.",
                        strategy="hung_process_restart",
                        confidence=0.9,
                    )
                )

        return reqs

    def _plan_pressure_action(
        self,
        alert: Alert,
        recurrence_count: int,
        safe_mode: bool,
        allowed: set[str],
        resource: str,
        top_process: Optional[Dict],
    ) -> Optional[ActionRequest]:
        adjustments_allowed = self.config["actions"].get("allowed_priority_adjustments", True)
        probable_cause = alert.context.get("probable_cause") if alert.context else None
        recurrence_hint = alert.context.get("recurrence_hint") if alert.context else ""
        recurring = recurrence_hint == "recurring" or recurrence_count >= 3
        process_name = (top_process or {}).get("name", "")
        process_pid = (top_process or {}).get("pid")

        structural_causes = {"distributed_load", "structural_memory_pressure", "structural_disk_pressure"}
        process_causes = {"abusive_process", "process_memory_pressure", "disk_io_process_pressure"}
        is_structural = probable_cause in structural_causes
        is_process_cause = probable_cause in process_causes

        can_restart = self._can_restart_process(process_name) and "restart_process" in allowed
        allow_restart_on_recurrence = self.config["actions"].get("auto_restart_on_recurrence", False)

        if recurring and is_process_cause and can_restart and allow_restart_on_recurrence:
            return ActionRequest(
                action="restart_process",
                reason=f"{alert.message} | recorrência={recurrence_count}",
                params={"name": process_name, "pid": process_pid, "source_alert": alert.code, "resource": resource},
                severity=alert.severity,
                recurrence_count=recurrence_count,
                human_recommendation=(
                    "Recorrência processual detectada. Reinício controlado aplicado; se voltar a ocorrer, abrir investigação humana com logs."
                ),
                strategy="recurrence_restart",
                confidence=0.78,
            )

        if recurring and is_structural and "thermal_protect" in allowed:
            return ActionRequest(
                action="thermal_protect",
                reason=f"{alert.message} | pressão estrutural recorrente",
                params={"safe_mode": safe_mode, "source_alert": alert.code, "resource": resource},
                severity=alert.severity,
                recurrence_count=recurrence_count,
                human_recommendation=(
                    "Pressão estrutural recorrente. Mitigação de proteção aplicada; validar capacidade, política e janela de manutenção."
                ),
                strategy="structural_guardrail",
                confidence=0.7,
            )

        if adjustments_allowed and "throttle_top_cpu_process" in allowed:
            return ActionRequest(
                action="throttle_top_cpu_process",
                reason=alert.message,
                params={
                    "safe_mode": safe_mode,
                    "target_name": process_name,
                    "target_pid": process_pid,
                    "resource": resource,
                    "probable_cause": probable_cause,
                    "source_alert": alert.code,
                },
                severity=alert.severity,
                recurrence_count=recurrence_count,
                human_recommendation=(
                    "Mitigação local aplicada. Se houver recorrência, o motor aumenta a agressividade com estratégia orientada por causa provável."
                ),
                strategy="targeted_throttle",
                confidence=0.74 if is_process_cause else 0.62,
            )

        if "thermal_protect" in allowed:
            return ActionRequest(
                action="thermal_protect",
                reason=f"{alert.message} | fallback de segurança",
                params={"safe_mode": safe_mode, "source_alert": alert.code, "resource": resource},
                severity=alert.severity,
                recurrence_count=recurrence_count,
                human_recommendation="Ajuste conservador aplicado por indisponibilidade de throttling.",
                strategy="safety_fallback",
                confidence=0.55,
            )

        return None

    @staticmethod
    def _top_process_name(snapshot: Optional[Dict]) -> str:
        if not snapshot:
            return ""
        procs = snapshot.get("processes") or []
        if not procs:
            return ""
        top = sorted(procs, key=lambda p: p.cpu_percent, reverse=True)[0]
        return top.name

    def _can_restart_process(self, name: str) -> bool:
        if not name:
            return False
        allowlist = {p.lower() for p in self.config.get("processes", {}).get("restart_allowlist", [])}
        return not allowlist or name.lower() in allowlist
