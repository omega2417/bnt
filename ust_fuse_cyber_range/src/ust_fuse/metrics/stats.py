"""Paired statistics for Reference vs UST-Fuse comparisons.

The proposal repeatedly demands *paired* analysis at the mission level with
effect sizes and 95% confidence intervals, and a power analysis (sections 5.1,
10, 13; ЛР-3).  This module keeps the "статистичний асистент" honest: it reports
effect sizes and CIs and never a bare p-value.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional

import numpy as np
from scipy import stats


@dataclass
class PairedResult:
    metric: str = ""
    mean_a: float = float("nan")
    mean_b: float = float("nan")
    mean_diff: float = float("nan")
    ci_low: float = float("nan")
    ci_high: float = float("nan")
    cohens_d: float = float("nan")
    t_stat: float = float("nan")
    p_value: float = float("nan")
    wilcoxon_p: float = float("nan")
    n: int = 0
    better: str = ""

    def to_dict(self) -> Dict:
        return dict(self.__dict__)


def bootstrap_ci(x: np.ndarray, n_boot: int = 5000, alpha: float = 0.05,
                 seed: int = 12345) -> tuple:
    """Percentile bootstrap CI for the mean of ``x``."""
    x = np.asarray(x, dtype=float)
    x = x[~np.isnan(x)]
    if len(x) == 0:
        return (float("nan"), float("nan"))
    rng = np.random.default_rng(seed)
    boots = np.array([rng.choice(x, size=len(x), replace=True).mean() for _ in range(n_boot)])
    return (float(np.percentile(boots, 100 * alpha / 2)),
            float(np.percentile(boots, 100 * (1 - alpha / 2))))


def cohens_d(a: np.ndarray, b: np.ndarray, paired: bool = True) -> float:
    """Cohen's d effect size (paired => standardised mean difference)."""
    a = np.asarray(a, dtype=float)
    b = np.asarray(b, dtype=float)
    if paired:
        diff = a - b
        diff = diff[~np.isnan(diff)]
        sd = diff.std(ddof=1)
        return float(diff.mean() / sd) if sd > 0 else 0.0
    pooled = np.sqrt((a.var(ddof=1) + b.var(ddof=1)) / 2)
    return float((a.mean() - b.mean()) / pooled) if pooled > 0 else 0.0


def power_analysis(effect_size: float, n: int, alpha: float = 0.05) -> Dict:
    """Approximate post-hoc power for a paired t-test and the n for 0.8 power."""
    if n < 2 or effect_size == 0:
        return {"power": float("nan"), "n_for_080": float("nan"),
                "effect_size": effect_size, "alpha": alpha}
    df = n - 1
    ncp = abs(effect_size) * np.sqrt(n)
    t_crit = stats.t.ppf(1 - alpha / 2, df)
    power = 1 - stats.nct.cdf(t_crit, df, ncp) + stats.nct.cdf(-t_crit, df, ncp)
    # required n for power 0.8 (normal approx)
    z_a = stats.norm.ppf(1 - alpha / 2)
    z_b = stats.norm.ppf(0.8)
    n_needed = ((z_a + z_b) / abs(effect_size)) ** 2 if effect_size != 0 else float("inf")
    return {
        "power": float(np.clip(power, 0, 1)),
        "n_for_080": float(np.ceil(n_needed)),
        "effect_size": float(effect_size),
        "alpha": alpha,
    }


def paired_comparison(
    a: np.ndarray, b: np.ndarray, metric: str = "", lower_is_better: bool = True,
    seed: int = 12345,
) -> PairedResult:
    """Full paired comparison of two arrays (a = mode A, b = mode B)."""
    a = np.asarray(a, dtype=float)
    b = np.asarray(b, dtype=float)
    mask = ~(np.isnan(a) | np.isnan(b))
    a, b = a[mask], b[mask]
    n = len(a)
    res = PairedResult(metric=metric, n=n)
    if n == 0:
        return res
    res.mean_a = float(a.mean())
    res.mean_b = float(b.mean())
    diff = a - b
    res.mean_diff = float(diff.mean())
    res.ci_low, res.ci_high = bootstrap_ci(diff, seed=seed)
    res.cohens_d = cohens_d(a, b, paired=True)
    if n >= 2 and diff.std() > 0:
        t_stat, p = stats.ttest_rel(a, b)
        res.t_stat, res.p_value = float(t_stat), float(p)
        try:
            if np.any(diff != 0):
                res.wilcoxon_p = float(stats.wilcoxon(a, b).pvalue)
        except ValueError:
            res.wilcoxon_p = float("nan")
    # who wins
    if lower_is_better:
        res.better = "B" if res.mean_b < res.mean_a else "A"
    else:
        res.better = "B" if res.mean_b > res.mean_a else "A"
    return res
