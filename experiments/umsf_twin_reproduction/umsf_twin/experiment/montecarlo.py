"""Monte Carlo driver with sequential stopping and rare-event splitting (12.6-12.7).

Replicates are the unit of analysis, so the stopping rule is expressed on the
cluster mean: keep adding replicates until the half-width of the confidence
interval is below the target, or the budget is exhausted - whichever comes
first, recorded either way.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from statistics import fmean
from typing import Any, Callable, Sequence

from .metrics import summarize
from .runner import run_replicate
from .scenario import Scenario
from .stats import cluster_bootstrap_ci, mean_ci, required_replicates
from ..pipelines.labeling import label_rows

__all__ = ["MonteCarloResult", "run_monte_carlo", "rare_event_probability"]


@dataclass
class MonteCarloResult:
    metric: str
    values: list[float] = field(default_factory=list)
    stopped_because: str = "budget"
    interval: dict[str, Any] = field(default_factory=dict)
    replicates: int = 0
    per_replicate: list[dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {"metric": self.metric, "replicates": self.replicates,
                "stopped_because": self.stopped_because, "interval": self.interval,
                "values": [round(value, 6) for value in self.values]}


def _extract(summary: dict[str, Any], path: str) -> float | None:
    node: Any = summary
    for part in path.split("."):
        if not isinstance(node, dict) or part not in node:
            return None
        node = node[part]
    return float(node) if isinstance(node, (int, float)) else None


def run_monte_carlo(scenario: Scenario, metric: str, max_replicates: int = 30,
                    target_half_width: float | None = None, min_replicates: int = 5,
                    run_id: str = "mc", progress: Callable[[int, float], None] | None = None
                    ) -> MonteCarloResult:
    """Run replicates until the interval is tight enough or the budget ends."""

    scenario.policy.check_budget(scenario.duration_s, len(scenario.events), max_replicates)
    result = MonteCarloResult(metric=metric)
    sites = list(scenario.config["sites"])
    clusters: list[list[float]] = []

    for replicate_id in range(max_replicates):
        artifacts = run_replicate(scenario, replicate_id, f"{run_id}-{replicate_id}")
        labeled = label_rows(artifacts["rows"], artifacts["truth"])
        summary = summarize(artifacts["rows"], labeled, sites)
        value = _extract(summary, metric)
        if value is None:
            raise KeyError(f"metric {metric!r} not found in the run summary")
        result.values.append(value)
        result.per_replicate.append({"replicate_id": replicate_id, "value": value})
        clusters.append([value])
        result.replicates = replicate_id + 1
        if progress is not None:
            progress(replicate_id, value)

        if target_half_width is not None and result.replicates >= min_replicates:
            interval = mean_ci(result.values)
            half_width = (interval["high"] - interval["low"]) / 2.0
            if half_width <= target_half_width:
                result.stopped_because = "target_half_width"
                break

    result.interval = cluster_bootstrap_ci(clusters)
    result.interval["normal_approx"] = mean_ci(result.values)
    if target_half_width is not None and result.values:
        spread = max(result.values) - min(result.values)
        result.interval["suggested_replicates"] = required_replicates(
            max(spread / 4.0, 1e-9), target_half_width)
    return result


def rare_event_probability(indicators: Sequence[bool], weights: Sequence[float] | None = None
                           ) -> dict[str, Any]:
    """Importance-weighted estimate of a rare-event probability.

    ``weights`` are the likelihood ratios of the biased sampling distribution;
    with no weights this reduces to the crude Monte Carlo estimator.
    """

    if not indicators:
        return {"probability": None, "hits": 0, "n": 0}
    if weights is None:
        weights = [1.0] * len(indicators)
    if len(weights) != len(indicators):
        raise ValueError("weights and indicators must have the same length")
    numerator = sum(weight for hit, weight in zip(indicators, weights) if hit)
    denominator = sum(weights)
    probability = numerator / denominator if denominator else 0.0
    effective_n = (denominator ** 2) / sum(weight ** 2 for weight in weights)
    return {"probability": probability, "hits": sum(1 for hit in indicators if hit),
            "n": len(indicators), "effective_sample_size": effective_n,
            "mean_weight": fmean(weights)}
