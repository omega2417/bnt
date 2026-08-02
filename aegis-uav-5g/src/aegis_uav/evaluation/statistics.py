"""Statistical protocol: bootstrap CIs, paired tests with Holm correction,
effect sizes, and calibration metrics (prompt §12)."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from scipy import stats

from ..rng import SeededRng

__all__ = [
    "bootstrap_ci",
    "wilcoxon_holm",
    "rank_biserial",
    "expected_calibration_error",
    "brier_score",
    "PairwiseComparison",
]


def bootstrap_ci(
    values: list[float] | np.ndarray,
    n_boot: int = 2000,
    alpha: float = 0.05,
    seed: int = 0,
    statistic: str = "mean",
) -> tuple[float, float, float]:
    """Return (point estimate, lower, upper) via percentile bootstrap."""
    arr = np.asarray(values, dtype=float)
    arr = arr[~np.isnan(arr)]
    if len(arr) == 0:
        return (float("nan"), float("nan"), float("nan"))
    stat_fn = np.median if statistic == "median" else np.mean
    point = float(stat_fn(arr))
    if len(arr) == 1:
        return (point, point, point)
    rng = SeededRng(seed).generator
    idx = rng.integers(0, len(arr), size=(n_boot, len(arr)))
    boot = stat_fn(arr[idx], axis=1)
    lo = float(np.percentile(boot, 100 * alpha / 2))
    hi = float(np.percentile(boot, 100 * (1 - alpha / 2)))
    return (point, lo, hi)


def rank_biserial(x: np.ndarray, y: np.ndarray) -> float:
    """Rank-biserial correlation effect size for paired samples (x - y)."""
    d = np.asarray(x, dtype=float) - np.asarray(y, dtype=float)
    d = d[d != 0]
    if len(d) == 0:
        return 0.0
    ranks = stats.rankdata(np.abs(d))
    r_plus = ranks[d > 0].sum()
    r_minus = ranks[d < 0].sum()
    total = r_plus + r_minus
    if total == 0:
        return 0.0
    return float((r_plus - r_minus) / total)


@dataclass
class PairwiseComparison:
    name: str
    statistic: float
    p_value: float
    p_holm: float
    effect_size: float
    n: int


def wilcoxon_holm(
    comparisons: dict[str, tuple[np.ndarray, np.ndarray]]
) -> list[PairwiseComparison]:
    """Wilcoxon signed-rank for each paired comparison, with Holm correction."""
    raw: list[PairwiseComparison] = []
    for name, (x, y) in comparisons.items():
        x = np.asarray(x, dtype=float)
        y = np.asarray(y, dtype=float)
        n = len(x)
        try:
            if np.allclose(x, y):
                stat, p = 0.0, 1.0
            else:
                stat, p = stats.wilcoxon(x, y)
        except ValueError:
            stat, p = float("nan"), 1.0
        raw.append(PairwiseComparison(name, float(stat), float(p), float("nan"),
                                      rank_biserial(x, y), n))
    # Holm-Bonferroni correction over the family of p-values.
    order = sorted(range(len(raw)), key=lambda i: raw[i].p_value)
    m = len(raw)
    prev = 0.0
    for rank, i in enumerate(order):
        adj = min(1.0, (m - rank) * raw[i].p_value)
        adj = max(adj, prev)
        raw[i].p_holm = adj
        prev = adj
    return raw


def expected_calibration_error(
    confidences: np.ndarray, correct: np.ndarray, n_bins: int = 10
) -> float:
    """ECE over confidence bins."""
    confidences = np.asarray(confidences, dtype=float)
    correct = np.asarray(correct, dtype=float)
    if len(confidences) == 0:
        return float("nan")
    bins = np.linspace(0, 1, n_bins + 1)
    ece = 0.0
    n = len(confidences)
    for b in range(n_bins):
        mask = (confidences > bins[b]) & (confidences <= bins[b + 1])
        if mask.sum() == 0:
            continue
        acc = correct[mask].mean()
        conf = confidences[mask].mean()
        ece += (mask.sum() / n) * abs(acc - conf)
    return float(ece)


def brier_score(probs: np.ndarray, onehot: np.ndarray) -> float:
    """Multiclass Brier score (mean squared error over the probability vector)."""
    probs = np.asarray(probs, dtype=float)
    onehot = np.asarray(onehot, dtype=float)
    if len(probs) == 0:
        return float("nan")
    return float(np.mean(np.sum((probs - onehot) ** 2, axis=1)))
