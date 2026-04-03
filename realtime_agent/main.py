from __future__ import annotations

import argparse
import time
from uuid import uuid4

from agent.actions import ActionExecutor
from agent.analyzer import Analyzer
from agent.audit import build_action_audit_batch
from agent.bootstrap import bootstrap_if_needed
from agent.collector import Collector
from agent.config import ConfigError, load_config
from agent.incidents import IncidentStateMachine
from agent.logger import setup_logger
from agent.outbox import Outbox
from agent.payloads import build_events_batch, build_heartbeat
from agent.policy import PolicyClient, apply_effective_policy
from agent.rules import RuleEngine
from agent.slo import RemediationSLOTracker
from agent.transport import Transport


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Agente de monitoramento inteligente (MVP)")
    parser.add_argument("--config", default="config.json", help="Caminho do arquivo JSON de configuração")
    parser.add_argument("--once", action="store_true", help="Executa apenas um ciclo de coleta/análise")
    return parser


def run() -> int:
    args = build_parser().parse_args()

    try:
        config = load_config(args.config)
    except ConfigError as exc:
        print(f"Erro de configuração: {exc}")
        return 2

    logger = setup_logger(config["log_file"])

    if config["server"].get("enabled", False):
        try:
            identity = bootstrap_if_needed(config, logger)
            config["identity"] = identity
            config["server"]["token"] = identity["token"]
        except Exception as exc:
            logger.error("BOOTSTRAP | falhou, continuando modo local: %s", exc)

    outbox = Outbox(config["outbox"]["db_path"])
    transport = Transport({**config["server"], "agent_id": config["identity"]["agent_id"]}, outbox)
    policy_client = PolicyClient(config["server"], config["identity"])

    collector = Collector()
    analyzer = Analyzer(config["thresholds"])
    rule_engine = RuleEngine(config)
    executor = ActionExecutor(config)
    incidents = IncidentStateMachine(
        escalation_after_failures=int(config.get("actions", {}).get("escalation_after_failures", 3)),
        action_budget_per_incident=int(config.get("actions", {}).get("max_attempts_per_incident", 3)),
    )
    slo_tracker = RemediationSLOTracker()

    logger.info("Agente iniciado | interval=%ss", config["interval_seconds"])

    while True:
        try:
            remote_policy = None
            if config["server"].get("enabled", False) and config["server"].get("token"):
                remote_policy = policy_client.fetch_if_due(interval_seconds=int(config.get("policy", {}).get("fetch_interval_seconds", 60)))

            effective_cfg = apply_effective_policy(config, remote_policy)
            analyzer.thresholds = effective_cfg["thresholds"]
            rule_engine.config = effective_cfg
            executor.config = effective_cfg

            snapshot = collector.collect()
            alerts = analyzer.analyze(snapshot)
            alert_incident_ctx = {}
            for alert in alerts:
                signature = _incident_signature(alert.code, alert.context)
                alert_incident_ctx[id(alert)] = incidents.observe(signature)
                alert.context = {**alert.context, **alert_incident_ctx[id(alert)]}

            for alert in alerts:
                logger.warning("ALERTA | %s | %s | context=%s | policy=%s", alert.code, alert.message, alert.context, effective_cfg.get("meta", {}).get("active_policy_version", "local-fallback"))

            audits = []
            if effective_cfg["actions"].get("enabled", True):
                action_requests = rule_engine.evaluate(alerts, snapshot=snapshot)
                action_results = executor.execute(action_requests, snapshot)
                post_snapshot = collector.collect() if action_requests else snapshot
                for req, result in zip(action_requests, action_results):
                    _assess_effectiveness(req, result, snapshot, post_snapshot, effective_cfg["thresholds"])
                    signature = _incident_signature(req.params.get("source_alert") or req.action, req.params)
                    incident_after_action = incidents.apply_action_result(
                        signature=signature,
                        execution_status="success" if result.success and result.outcome == "resolved" else ("partial" if result.success else "failed"),
                    )
                    rule_engine.record_action_feedback(req, result.outcome)
                    slo_metrics = slo_tracker.observe(
                        incident=incident_after_action,
                        execution_context={
                            "human_intervention_required": bool(result.human_recommendation) and result.outcome != "resolved",
                            "evidence_complete": bool(result.evidence) and bool(result.operational_context) and bool(result.message),
                        },
                    )
                    level = logger.info if result.success else logger.error
                    level(
                        "AÇÃO | %s | success=%s | outcome=%s | %s",
                        result.action,
                        result.success,
                        result.outcome,
                        result.message,
                    )
                    audits.append(
                        {
                            "action_id": str(uuid4()),
                            "trigger_event_id": str(uuid4()),
                            "action_name": result.action,
                            "reason": req.reason,
                            "risk_level": req.severity if req.severity in {"low", "medium", "high", "critical"} else "medium",
                            "pre_state": {
                                "cpu_percent": snapshot.get("cpu_percent"),
                                "ram_percent": snapshot.get("ram_percent"),
                                "disk_percent": snapshot.get("disk_percent"),
                                "temperature_c": snapshot.get("temperature_c"),
                                "evidences": req.params,
                                "operational_severity": req.severity,
                                "recurrence_count": req.recurrence_count,
                                "incident": incident_after_action,
                                "strategy_ranking": req.params.get("strategy_ranking", []),
                                "playbook": {
                                    "process_class": req.params.get("process_class", "unknown_process"),
                                    "allowed_actions": req.params.get("playbook_allowed_actions", []),
                                    "risk_level": req.params.get("playbook_risk", "unknown"),
                                    "rollback": req.params.get("playbook_rollback", ""),
                                    "documentation": req.params.get("playbook_documentation", ""),
                                },
                            },
                            "post_state": {
                                "message": result.message,
                                "outcome": result.outcome,
                                "evidence": result.evidence or {},
                                "operational_context": result.operational_context or {},
                                "human_recommendation": result.human_recommendation,
                                "post_metrics": {
                                    "cpu_percent": post_snapshot.get("cpu_percent"),
                                    "ram_percent": post_snapshot.get("ram_percent"),
                                    "disk_percent": post_snapshot.get("disk_percent"),
                                    "temperature_c": post_snapshot.get("temperature_c"),
                                },
                                "incident": incident_after_action,
                                "remediation_slo": slo_metrics,
                            },
                            "rollback_possible": result.action in {"throttle_top_cpu_process", "restart_process"},
                            "rollback_executed": False,
                            "execution_status": "success" if result.success and result.outcome == "resolved" else ("partial" if result.success else "failed"),
                            "error_message": "" if result.success else result.message,
                            "policy_version": effective_cfg.get("meta", {}).get("active_policy_version", "local-fallback"),
                            "cooldown_applied": result.cooldown_applied,
                        }
                    )

            if effective_cfg["server"].get("enabled", False) and effective_cfg["server"].get("token"):
                hb = build_heartbeat(effective_cfg["identity"], queue_depth=len(outbox.due_items(limit=1000)))
                transport.send_heartbeat(hb)
                if alerts:
                    transport.send_events_batch(build_events_batch(alerts))
                if audits:
                    transport.send_action_audit_batch(build_action_audit_batch(effective_cfg["identity"], audits))
                transport.flush(logger)

            if args.once:
                break

            time.sleep(effective_cfg["interval_seconds"])
        except KeyboardInterrupt:
            logger.info("Agente interrompido pelo usuário")
            break
        except Exception as exc:
            logger.exception("Erro inesperado no ciclo de monitoramento: %s", exc)
            if args.once:
                return 1
            time.sleep(2)

    return 0


def _assess_effectiveness(req, result, pre_snapshot, post_snapshot, thresholds):
    if not result.evidence:
        result.evidence = {}
    delta_ram = round(pre_snapshot.get("ram_percent", 0) - post_snapshot.get("ram_percent", 0), 2)
    delta_cpu = round(pre_snapshot.get("cpu_percent", 0) - post_snapshot.get("cpu_percent", 0), 2)
    delta_disk = round(pre_snapshot.get("disk_percent", 0) - post_snapshot.get("disk_percent", 0), 2)
    delta_temp = round((pre_snapshot.get("temperature_c") or 0) - (post_snapshot.get("temperature_c") or 0), 2)
    result.evidence.update({"delta_ram": delta_ram, "delta_cpu": delta_cpu, "delta_disk": delta_disk, "delta_temp": delta_temp})

    if not result.success:
        result.outcome = "failed"
        if req.params.get("probable_cause") == "structural_memory_pressure":
            result.human_recommendation = (
                result.human_recommendation
                or "Padrão indica limitação estrutural de memória após tentativas locais. Avaliar upgrade de RAM com evidências históricas."
            )
        return

    if req.action == "thermal_protect":
        result.outcome = "resolved" if post_snapshot.get("temperature_c") and post_snapshot.get("temperature_c") < thresholds.get("temperature_c", 999) else "mitigated"
    elif req.params.get("resource") == "memory":
        result.outcome = "resolved" if post_snapshot.get("ram_percent", 0) < thresholds.get("ram_percent", 100) else ("mitigated" if delta_ram > 1.0 else "failed")
    elif req.params.get("resource") == "disk":
        result.outcome = "resolved" if post_snapshot.get("disk_percent", 0) < thresholds.get("disk_percent", 100) else ("mitigated" if delta_disk > 1.0 else "failed")
    else:
        result.outcome = "resolved" if delta_cpu > 5 else ("mitigated" if delta_cpu > 1 else "failed")

    if result.outcome != "resolved" and req.params.get("probable_cause") == "structural_memory_pressure":
        result.human_recommendation = (
            result.human_recommendation
            or "Mitigação local insuficiente e padrão recorrente estrutural. Avaliar expansão de RAM."
        )


def _incident_signature(code: str, context: dict | None) -> str:
    ctx = context or {}
    keys = ("resource", "source_alert", "target_name", "name", "pid", "probable_cause")
    parts = [str(code)]
    for key in keys:
        if key in ctx and ctx.get(key) not in (None, ""):
            parts.append(f"{key}={ctx.get(key)}")
    return "|".join(parts)


if __name__ == "__main__":
    raise SystemExit(run())
