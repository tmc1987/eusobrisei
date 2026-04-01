from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List

from .models import Alert


@dataclass
class ActionRequest:
    action: str
    reason: str
    params: Dict


class RuleEngine:
    """Converte alertas em ações automáticas seguras."""

    def __init__(self, config: Dict):
        self.config = config

    def evaluate(self, alerts: List[Alert]) -> List[ActionRequest]:
        reqs: List[ActionRequest] = []
        safe_mode = self.config["actions"].get("safe_mode", True)

        for alert in alerts:
            if alert.code == "HIGH_CPU" and self.config["actions"].get("allowed_priority_adjustments", True):
                reqs.append(
                    ActionRequest(
                        action="throttle_top_cpu_process",
                        reason=alert.message,
                        params={"safe_mode": safe_mode},
                    )
                )
            elif alert.code == "HIGH_TEMP":
                reqs.append(
                    ActionRequest(
                        action="thermal_protect",
                        reason=alert.message,
                        params={"safe_mode": safe_mode},
                    )
                )
            elif alert.code == "HUNG_PROCESS" and self.config["actions"].get("auto_restart_hung_process", False):
                reqs.append(
                    ActionRequest(
                        action="restart_process",
                        reason=alert.message,
                        params={"pid": alert.context.get("pid"), "name": alert.context.get("name")},
                    )
                )

        return reqs
