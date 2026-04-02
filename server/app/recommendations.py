from __future__ import annotations

import json
import sqlite3
import time
from collections import Counter
from typing import Dict, List

from .config import get_settings


def _connect():
    return sqlite3.connect(get_settings().db_path)


def _base(rec_type: str, scope: str, scope_id: str, summary: str, evidences: List[str], impact: str, confidence: float, severity: str):
    return {
        "type": rec_type,
        scope: scope_id,
        "summary": summary,
        "evidences": evidences,
        "impact": impact,
        "confidence": round(confidence, 2),
        "severity": severity,
        "timestamp": time.time(),
        "status": "ativa",
    }


def _device_events_and_actions(device_id: str):
    with _connect() as db:
        agent = db.execute("SELECT agent_id, tenant_id FROM agents WHERE device_id=? ORDER BY created_at DESC LIMIT 1", (device_id,)).fetchone()
        if not agent:
            return None, None, [], []
        agent_id, tenant_id = agent[0], agent[1]
        events_rows = db.execute("SELECT payload FROM event_batches WHERE agent_id=? AND received_at>?", (agent_id, time.time() - 7 * 24 * 3600)).fetchall()
        events = []
        for (payload,) in events_rows:
            events.extend(json.loads(payload).get("events", []))
        actions_rows = db.execute("SELECT payload FROM action_audit WHERE agent_id=? AND received_at>?", (agent_id, time.time() - 7 * 24 * 3600)).fetchall()
        actions = [json.loads(p) for (p,) in actions_rows]
        return agent_id, tenant_id, events, actions


def recommendations_for_device(device_id: str) -> List[Dict]:
    agent_id, tenant_id, events, actions = _device_events_and_actions(device_id)
    if not agent_id:
        return []

    recs: List[Dict] = []
    msgs = [str(e.get("context", {}).get("message", "")).lower() for e in events]
    sev = [e.get("severity") for e in events]

    ram_hits = sum("ram" in m or "memory" in m for m in msgs)
    if ram_hits >= 3:
        recs.append(_base("upgrade_ram", "device_id", device_id, "Possível necessidade de upgrade de RAM.", [f"{ram_hits} eventos de memória/ram na última semana"], "Redução de paginação e travamentos", 0.78, "medium"))

    disk_hits = sum("disco" in m or "disk" in m for m in msgs)
    if disk_hits >= 3:
        recs.append(_base("migrate_hdd_to_ssd", "device_id", device_id, "Possível gargalo de disco; avaliar migração para SSD.", [f"{disk_hits} eventos de disco recorrentes"], "Melhora de boot e responsividade", 0.72, "medium"))

    temp_hits = sum("temperatura" in m or "high_temp" in m for m in msgs)
    thermal_actions = sum(a.get("action_name") == "thermal_protect" for a in actions)
    if temp_hits + thermal_actions >= 3:
        recs.append(_base("thermal_investigation", "device_id", device_id, "Investigar refrigeração/temperatura do equipamento.", [f"{temp_hits} alertas térmicos", f"{thermal_actions} ativações de thermal_protect"], "Prevenir throttling e indisponibilidade", 0.84, "high"))

    power_hits = sum("kernel-power" in m or "power" in m for m in msgs)
    if power_hits >= 2:
        recs.append(_base("power_instability_suspect", "device_id", device_id, "Suspeita de energia instável; verificar fonte/rede elétrica.", [f"{power_hits} eventos com indício de energia"], "Reduzir reinícios abruptos", 0.6, "high"))

    network_hits = sum("rede" in m or "network" in m or "latência" in m for m in msgs)
    if network_hits >= 3:
        recs.append(_base("network_degradation_suspect", "device_id", device_id, "Suspeita de degradação de rede.", [f"{network_hits} eventos de rede/latência"], "Melhorar conectividade e tempo de resposta", 0.67, "medium"))

    recurring = Counter([m for m in msgs if m]).most_common(1)
    if recurring and recurring[0][1] >= 4:
        recs.append(_base("software_process_review", "device_id", device_id, "Revisar software/processo recorrente degradando a máquina.", [f"Mensagem recorrente: '{recurring[0][0]}' ({recurring[0][1]}x)"], "Reduzir recorrência de incidentes", 0.75, "medium"))

    failed_actions = sum(a.get("execution_status") == "failed" for a in actions)
    if failed_actions >= 2 or len(actions) >= 8:
        recs.append(_base("preventive_maintenance", "device_id", device_id, "Necessidade de manutenção preventiva por recorrência de autoações/falhas.", [f"Ações totais: {len(actions)}", f"Falhas de ação: {failed_actions}"], "Evitar degradação progressiva", 0.8, "high"))

    return recs


def recommendations_for_tenant(tenant_id: str) -> List[Dict]:
    with _connect() as db:
        devices = [r[0] for r in db.execute("SELECT device_id FROM devices WHERE tenant_id=?", (tenant_id,)).fetchall()]
    all_recs = []
    for d in devices:
        all_recs.extend(recommendations_for_device(d))

    if not all_recs:
        return []

    by_type = Counter([r["type"] for r in all_recs])
    output = []
    for t, count in by_type.items():
        output.append(
            {
                "type": t,
                "tenant_id": tenant_id,
                "summary": f"{count} dispositivo(s) com recomendação {t}",
                "evidences": [f"dispositivos afetados: {count}"],
                "impact": "Priorização de intervenção técnica por tenant",
                "confidence": 0.7,
                "severity": "medium" if count < 3 else "high",
                "timestamp": time.time(),
                "status": "ativa",
            }
        )
    return output


def recommendations_all() -> List[Dict]:
    with _connect() as db:
        devices = [r[0] for r in db.execute("SELECT device_id FROM devices").fetchall()]
    out = []
    for d in devices:
        out.extend(recommendations_for_device(d))
    return out
