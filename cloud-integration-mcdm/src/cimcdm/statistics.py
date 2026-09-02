"""Paired nonparametric comparison of the two evolutionary methods.

Two-sided Wilcoxon signed-rank tests on matched seeds, Pratt treatment of zero
differences, and Holm correction across the five reported metrics (Table 6).
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from scipy import stats

METRIC_DIRECTION: dict[str, str] = {
    "hypervolume": "higher",
    "igd_plus": "lower",
    "spacing": "lower",
    "cpu_time": "lower",
    "coverage": "higher",
}


@dataclass(frozen=True)
class TestResult:
    """One paired test, after multiplicity correction."""

    metric: str
    statistic: float
    p_value: float
    adjusted_p: float
    rank_biserial: float
    """Signed with NSGA-II minus NSGA-III, so its meaning depends on whether the
    metric is better-when-higher or better-when-lower."""
    interpretation: str


def rank_biserial_correlation(a: np.ndarray, b: np.ndarray) -> float:
    """Matched-pairs rank-biserial effect size for ``a - b``.

    Signed ranks of the nonzero differences are split into positive and negative
    mass; the statistic is their normalized difference in [-1, 1].
    """
    difference = np.asarray(a, dtype=float) - np.asarray(b, dtype=float)
    nonzero = difference[difference != 0]
    if len(nonzero) == 0:
        return 0.0
    ranks = stats.rankdata(np.abs(nonzero))
    positive = ranks[nonzero > 0].sum()
    negative = ranks[nonzero < 0].sum()
    return float((positive - negative) / (positive + negative))


def holm_adjust(p_values: np.ndarray) -> np.ndarray:
    """Holm step-down adjustment, enforcing monotonicity and capping at 1."""
    p = np.asarray(p_values, dtype=float)
    order = np.argsort(p)
    m = len(p)
    adjusted = np.empty(m)
    running = 0.0
    for i, index in enumerate(order):
        running = max(running, (m - i) * p[index])
        adjusted[index] = min(running, 1.0)
    return adjusted


def _interpret(metric: str, adjusted_p: float, effect: float, alpha: float) -> str:
    if adjusted_p >= alpha:
        return "No significant difference"
    higher_is_better = METRIC_DIRECTION.get(metric, "higher") == "higher"
    # effect > 0 means NSGA-II tended to produce the larger value.
    nsga2_better = (effect > 0) == higher_is_better
    if metric == "cpu_time":
        return "NSGA-II faster" if effect < 0 else "NSGA-III faster"
    return "NSGA-II better" if nsga2_better else "NSGA-III better"


def compare_methods(
    metrics_a: dict[str, np.ndarray],
    metrics_b: dict[str, np.ndarray],
    alpha: float = 0.05,
) -> list[TestResult]:
    """Paired Wilcoxon tests with Holm correction across all shared metrics.

    Parameters
    ----------
    metrics_a, metrics_b:
        Per-metric arrays of matched run-level values (NSGA-II and NSGA-III).
    """
    names = [name for name in metrics_a if name in metrics_b]
    statistics, raw_p, effects = [], [], []

    for name in names:
        a = np.asarray(metrics_a[name], dtype=float)
        b = np.asarray(metrics_b[name], dtype=float)
        if np.allclose(a, b):
            statistics.append(0.0)
            raw_p.append(1.0)
        else:
            result = stats.wilcoxon(
                a, b, zero_method="pratt", alternative="two-sided"
            )
            statistics.append(float(result.statistic))
            raw_p.append(float(result.pvalue))
        effects.append(rank_biserial_correlation(a, b))

    adjusted = holm_adjust(np.array(raw_p))

    return [
        TestResult(
            metric=name,
            statistic=statistics[i],
            p_value=raw_p[i],
            adjusted_p=float(adjusted[i]),
            rank_biserial=effects[i],
            interpretation=_interpret(name, float(adjusted[i]), effects[i], alpha),
        )
        for i, name in enumerate(names)
    ]


def mean_confidence_interval(values: np.ndarray, confidence: float = 0.95):
    """Mean and normal-approximation half-width, as used for Figure 2."""
    values = np.asarray(values, dtype=float)
    n = len(values)
    if n < 2:
        return float(values.mean()) if n else float("nan"), 0.0
    z = stats.norm.ppf(0.5 + confidence / 2.0)
    return float(values.mean()), float(z * values.std(ddof=1) / np.sqrt(n))
