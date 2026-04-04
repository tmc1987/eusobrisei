from __future__ import annotations

from typing import Dict, List


def build_client_guidance(alert, config: Dict) -> Dict:
    code = alert.code
    ctx = alert.context or {}
    if code == "HIGH_RAM":
        return _memory_guidance(ctx, config)
    if code == "HIGH_CPU":
        return _cpu_guidance(ctx, config)
    if code == "HIGH_DISK":
        return _disk_guidance(ctx, config)
    if code == "HUNG_PROCESS":
        name = ctx.get("name", "aplicativo")
        return {
            "message": f"O aplicativo {name} travou e estamos aplicando estabilização segura.",
            "suggestions": [
                "Salvar trabalho em andamento em outros apps para evitar perda de dados.",
                "Se o travamento persistir, fechar e reabrir o aplicativo principal.",
            ],
            "safe_secondary_processes": [],
            "principal_process": name,
        }
    return {
        "message": "Detectamos uma degradação e estamos aplicando correção automática segura.",
        "suggestions": ["Acompanhar estabilidade nos próximos minutos."],
        "safe_secondary_processes": [],
        "principal_process": "",
    }


def _memory_guidance(ctx: Dict, config: Dict) -> Dict:
    processes = ctx.get("top_ram_processes") or []
    principal = (processes[0] if processes else {}).get("name", "processo principal")
    principal_mem = (processes[0] if processes else {}).get("memory_percent")
    secondary = _safe_secondary_processes(processes, config)
    suggestions = []
    if secondary:
        suggestions.append(f"Processos secundários que podem ser fechados com baixo risco: {', '.join(secondary[:3])}.")
    browser_hint = _browser_hint(principal)
    if browser_hint:
        suggestions.append(browser_hint)
    suggestions.append("Se continuar alto por vários dias, o sistema consolidará evidências para avaliação estrutural.")
    msg = (
        f"Memória alta detectada. Principal responsável: {principal}"
        + (f" (~{round(float(principal_mem), 1)}% da RAM)." if principal_mem is not None else ".")
    )
    return {
        "message": msg,
        "suggestions": suggestions,
        "safe_secondary_processes": secondary,
        "principal_process": principal,
    }


def _cpu_guidance(ctx: Dict, config: Dict) -> Dict:
    processes = ctx.get("top_cpu_processes") or []
    principal = (processes[0] if processes else {}).get("name", "processo principal")
    secondary = _safe_secondary_processes(processes, config)
    suggestions = []
    if secondary:
        suggestions.append(f"Fechar processos secundários pode aliviar CPU: {', '.join(secondary[:3])}.")
    suggestions.append("Evitar abrir tarefas pesadas em paralelo até a estabilização.")
    return {
        "message": f"CPU alta detectada. Principal responsável: {principal}.",
        "suggestions": suggestions,
        "safe_secondary_processes": secondary,
        "principal_process": principal,
    }


def _disk_guidance(ctx: Dict, config: Dict) -> Dict:
    processes = ctx.get("top_disk_processes") or []
    principal = (processes[0] if processes else {}).get("name", "processo principal")
    secondary = _safe_secondary_processes(processes, config)
    return {
        "message": f"Uso de disco elevado. Processo dominante: {principal}.",
        "suggestions": [
            "Pausar sincronizações/backup não essenciais até normalizar.",
            *( [f"Fechamentos secundários seguros sugeridos: {', '.join(secondary[:3])}."] if secondary else [] ),
        ],
        "safe_secondary_processes": secondary,
        "principal_process": principal,
    }


def _safe_secondary_processes(processes: List[Dict], config: Dict) -> List[str]:
    critical = {p.lower() for p in config.get("processes", {}).get("critical_names", [])}
    protected = {p.lower() for p in config.get("processes", {}).get("non_throttle_names", [])}
    safe: List[str] = []
    for proc in processes[1:]:
        name = str(proc.get("name", "")).strip()
        if not name:
            continue
        low = name.lower()
        if low in critical or low in protected:
            continue
        if name not in safe:
            safe.append(name)
    return safe


def _browser_hint(process_name: str) -> str:
    low = str(process_name or "").lower()
    if any(b in low for b in ["chrome", "firefox", "msedge", "edge", "brave", "opera"]):
        return "Fechar algumas abas do navegador pode reduzir memória sem impacto crítico."
    return ""
