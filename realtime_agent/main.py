from __future__ import annotations

import argparse
import time

from agent.actions import ActionExecutor
from agent.analyzer import Analyzer
from agent.collector import Collector
from agent.config import ConfigError, load_config
from agent.logger import setup_logger
from agent.rules import RuleEngine


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
    collector = Collector()
    analyzer = Analyzer(config["thresholds"])
    rule_engine = RuleEngine(config)
    executor = ActionExecutor(config)

    logger.info("Agente iniciado | interval=%ss", config["interval_seconds"])

    while True:
        try:
            snapshot = collector.collect()
            alerts = analyzer.analyze(snapshot)

            for alert in alerts:
                logger.warning("ALERTA | %s | %s | context=%s", alert.code, alert.message, alert.context)

            if config["actions"].get("enabled", True):
                action_requests = rule_engine.evaluate(alerts)
                action_results = executor.execute(action_requests, snapshot)
                for result in action_results:
                    level = logger.info if result.success else logger.error
                    level("AÇÃO | %s | success=%s | %s", result.action, result.success, result.message)

            if args.once:
                break

            time.sleep(config["interval_seconds"])
        except KeyboardInterrupt:
            logger.info("Agente interrompido pelo usuário")
            break
        except Exception as exc:  # robustez de loop contínuo
            logger.exception("Erro inesperado no ciclo de monitoramento: %s", exc)
            if args.once:
                return 1
            time.sleep(2)

    return 0


if __name__ == "__main__":
    raise SystemExit(run())
