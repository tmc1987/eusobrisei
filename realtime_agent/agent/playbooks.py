from __future__ import annotations

from typing import Dict, Set


DEFAULT_PROTECTED = {
    "systemsettings.exe",
    "dwm.exe",
    "csrss.exe",
    "wininit.exe",
    "winlogon.exe",
    "lsass.exe",
}


def classify_process(process_name: str, config: Dict) -> str:
    name = (process_name or "").lower()
    if not name:
        return "unknown_process"

    critical = {p.lower() for p in config.get("processes", {}).get("critical_names", [])}
    protected = {p.lower() for p in config.get("processes", {}).get("non_throttle_names", [])} | DEFAULT_PROTECTED

    if name in critical:
        return "critical_service"
    if name in protected:
        return "protected_process"
    return "user_app"


def playbook_for(process_class: str) -> Dict:
    playbooks = {
        "critical_service": {
            "allowed_actions": {"thermal_protect"},
            "risk_by_action": {
                "thermal_protect": "low",
                "throttle_top_cpu_process": "critical",
                "restart_process": "critical",
            },
            "rollback_by_action": {
                "thermal_protect": "Reverter para plano energético anterior em janela de manutenção.",
                "throttle_top_cpu_process": "N/A (bloqueado por playbook).",
                "restart_process": "N/A (bloqueado por playbook).",
            },
            "documentation": "Playbook serviço crítico: evitar interrupção/instabilidade do serviço; escalar humano cedo.",
        },
        "protected_process": {
            "allowed_actions": {"thermal_protect"},
            "risk_by_action": {
                "thermal_protect": "low",
                "throttle_top_cpu_process": "high",
                "restart_process": "high",
            },
            "rollback_by_action": {
                "thermal_protect": "Reverter plano energético quando estabilidade térmica retornar.",
                "throttle_top_cpu_process": "N/A (bloqueado por playbook).",
                "restart_process": "N/A (bloqueado por playbook).",
            },
            "documentation": "Playbook processo protegido: não aplicar ações invasivas localmente.",
        },
        "user_app": {
            "allowed_actions": {"throttle_top_cpu_process", "restart_process", "thermal_protect"},
            "risk_by_action": {
                "thermal_protect": "low",
                "throttle_top_cpu_process": "medium",
                "restart_process": "medium",
            },
            "rollback_by_action": {
                "thermal_protect": "Reverter plano energético se necessário.",
                "throttle_top_cpu_process": "Rollback automático de prioridade após cooldown configurado.",
                "restart_process": "Reiniciar processo com comando mapeado; validar estado funcional pós-ação.",
            },
            "documentation": "Playbook app usuário: prioriza mitigação gradual com rollback auditável.",
        },
        "unknown_process": {
            "allowed_actions": {"thermal_protect"},
            "risk_by_action": {
                "thermal_protect": "low",
                "throttle_top_cpu_process": "high",
                "restart_process": "high",
            },
            "rollback_by_action": {
                "thermal_protect": "Reverter plano energético quando possível.",
                "throttle_top_cpu_process": "N/A (bloqueado por playbook).",
                "restart_process": "N/A (bloqueado por playbook).",
            },
            "documentation": "Playbook processo desconhecido: adotar postura conservadora e coletar evidências.",
        },
    }
    return playbooks.get(process_class, playbooks["unknown_process"])


def filter_allowed(playbook: Dict, allowed_actions: Set[str]) -> Set[str]:
    return set(playbook.get("allowed_actions", set())) & set(allowed_actions)
