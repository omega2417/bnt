"""Detection federate: runs the three comparison arms of section 9.12.

Arm 1 rules, arm 2 local edge detector, arm 3 edge detector plus cross-site
correlation. All three see exactly the same telemetry row, including its
defects, so the comparison is fair.
"""

from __future__ import annotations

from typing import Any

from ...core.clock import Phase
from ...core.federate import Federate, FederateHealth
from ...core.rng import RngHub
from .correlation import CrossSiteCorrelator
from .edge_ai import EdgeDetector
from .rules import RuleEngine

__all__ = ["DetectionFederate"]


class DetectionFederate(Federate):
    order = 70

    def __init__(self, sites: list[str], rng: RngHub, threshold: float = 0.35,
                 arms: tuple[str, ...] = ("rules", "edge", "edge_correlated"),
                 learn_online: bool = True, name: str = "detection") -> None:
        super().__init__(name)
        self.sites = list(sites)
        self.rng = rng
        self.arms = arms
        self.learn_online = learn_online
        self.rules = RuleEngine(threshold=threshold)
        self.edges = {site: EdgeDetector() for site in sites}
        self.correlator = CrossSiteCorrelator()
        self.alerts: list[dict[str, Any]] = []
        self.metrics: dict[str, dict[str, Any]] = {}

    def advance(self, t_ns: int, dt_ns: int) -> None:
        assert self.clock is not None
        t_s = t_ns / 1e9
        shared = self.context["shared"]
        rows = shared.get("telemetry_row", {})

        for site_id in self.sites:
            row = rows.get(site_id)
            if row is None or row.get("telemetry_gap_marker") == 1:
                self.metrics[site_id] = {"site_id": site_id, "score": None,
                                         "alert": False, "reason": "telemetry gap"}
                continue

            rule_row = self.rules.score(row)
            edge = self.edges[site_id]
            edge_row = edge.score(row)
            if self.learn_online:
                edge.learn(edge_row["features"], 1.0 if rule_row["alert"] else 0.0)

            correlation = self.correlator.offer(t_s, site_id, edge_row["score"],
                                                str(shared.get("threats", {})
                                                    .get(site_id, {})
                                                    .get("attack_stage", "")))
            scores = {
                "rules": rule_row["score"],
                "edge": edge_row["score"],
                "edge_correlated": correlation["joint_score"],
            }
            primary = scores.get(self.arms[0], rule_row["score"])
            alert = primary >= self.rules.threshold

            self.metrics[site_id] = {
                "site_id": site_id,
                "score": primary,
                "scores": scores,
                "alert": alert,
                "rule_hits": rule_row["rule_hits"],
                "explanation": rule_row["explanation"],
                "correlated_with": correlation["correlated_with"],
            }
            if alert:
                self.alerts.append({
                    "run_id": row.get("run_id"), "replicate_id": row.get("replicate_id"),
                    "alert_id": f"alert-{site_id}-{self.clock.step_index}",
                    "step": self.clock.step_index,
                    "timestamp_utc": row.get("timestamp_utc"), "site_id": site_id,
                    "detector": self.arms[0], "score": round(primary, 5),
                    "threshold": self.rules.threshold,
                    "rule_hits": rule_row["rule_hits"],
                    "explanation": rule_row["explanation"],
                    "correlated_with": correlation["correlated_with"],
                    "recommended_action": "", "approval_required": 1, "shadow_mode": 1,
                })
                self.emit("alert", {"site_id": site_id, "score": primary}, Phase.INFERENCE)
        shared["detection"] = self.metrics

    def observe(self) -> dict[str, Any]:
        return self.metrics

    def health(self) -> FederateHealth:
        return FederateHealth.ok(self.name, alerts=len(self.alerts))
