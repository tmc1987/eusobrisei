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
from agent.logger import setup_logger
from agent.outbox import Outbox
from agent.payloads import build_events_batch, build_heartbeat
from agent.policy import PolicyClient, apply_effective_policy
from agent.rules import RuleEngine
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

            for alert in alerts:
                logger.warning("ALERTA | %s | %s | context=%s | policy=%s", alert.code, alert.message, alert.context, effective_cfg.get("meta", {}).get("active_policy_version", "local-fallback"))

            audits = []
            if effective_cfg["actions"].get("enabled", True):
                action_requests = rule_engine.evaluate(alerts)
                action_results = executor.execute(action_requests, snapshot)
                for req, result in zip(action_requests, action_results):
                    level = logger.info if result.success else logger.error
                    level("AÇÃO | %s | success=%s | %s", result.action, result.success, result.message)
                    audits.append(
                        {
                            "action_id": str(uuid4()),
                            "trigger_event_id": str(uuid4()),
                            "action_name": result.action,
                            "reason": req.reason,
                            "risk_level": "medium",
                            "pre_state": {
                                "cpu_percent": snapshot.get("cpu_percent"),
                                "ram_percent": snapshot.get("ram_percent"),
                                "disk_percent": snapshot.get("disk_percent"),
                                "temperature_c": snapshot.get("temperature_c"),
                            },
                            "post_state": {"message": result.message},
                            "rollback_possible": result.action in {"throttle_top_cpu_process", "restart_process"},
                            "rollback_executed": False,
                            "execution_status": "success" if result.success else "failed",
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


if __name__ == "__main__":
    raise SystemExit(run())
