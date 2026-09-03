"""Transparent rule baseline.

Every rule is a named, inspectable predicate with a weight. The baseline
exists to smoke-test the pipeline and to give the AI detector something honest
to beat; its own numbers are never presented as evidence of AI quality.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

__all__ = ["Rule", "RuleEngine", "DEFAULT_RULES"]


@dataclass(frozen=True)
class Rule:
    name: str
    weight: float
    predicate: Callable[[dict[str, Any]], bool]
    explanation: str


def _number(row: dict[str, Any], key: str, default: float = 0.0) -> float:
    value = row.get(key, default)
    if value in ("", None):
        return default
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


DEFAULT_RULES: tuple[Rule, ...] = (
    Rule("scan_rate", 0.35, lambda r: _number(r, "scan_rate_pps") > 5.0,
         "connection/port counters above the benign envelope"),
    Rule("auth_burst", 0.25, lambda r: _number(r, "auth_failures") > 10.0,
         "authentication failure burst on Wi-Fi"),
    Rule("lateral", 0.30, lambda r: _number(r, "lateral_events") > 0.0,
         "asset-to-asset sequence observed"),
    Rule("c2_beacon", 0.25, lambda r: _number(r, "c2_beacons") > 0.0,
         "periodic low-rate flow pattern"),
    Rule("rogue_ap", 0.20, lambda r: _number(r, "rogue_ap_count") > 0.0,
         "unexpected BSSID in the AP inventory"),
    Rule("path_degraded", 0.15,
         lambda r: _number(r, "loss_pct") > 3.0 or _number(r, "queue_delay_ms") > 150.0,
         "transport degradation that can mask or mimic an incident"),
)


class RuleEngine:
    def __init__(self, rules: tuple[Rule, ...] = DEFAULT_RULES,
                 threshold: float = 0.35) -> None:
        self.rules = rules
        self.threshold = threshold

    def score(self, row: dict[str, Any]) -> dict[str, Any]:
        hits = [rule for rule in self.rules if rule.predicate(row)]
        raw = sum(rule.weight for rule in hits)
        score = min(1.0, raw)
        return {
            "detector": "transparent_rule_baseline",
            "score": score,
            "alert": score >= self.threshold,
            "threshold": self.threshold,
            "rule_hits": "|".join(rule.name for rule in hits),
            "explanation": "; ".join(rule.explanation for rule in hits) or "no rule fired",
        }
