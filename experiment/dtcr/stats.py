"""Statistical procedures required by section 14 of the experiment protocol."""
from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import Sequence

import numpy as np
from scipy import stats

__all__ = [
    "Describe", "describe", "bootstrap_ci", "hedges_g", "cliffs_delta",
    "wilson_ci", "paired_test", "holm", "risk_difference", "paired_power",
]


@dataclass
class Describe:
    n: int
    mean: float
    sd: float
    median: float
    q1: float
    q3: float
    ci_lo: float
    ci_hi: float
    n_censored: int


def describe(x: Sequence[float], n_censored: int = 0, boot: int = 10000, seed: int = 0) -> Describe:
    a = np.asarray([v for v in x if np.isfinite(v)], dtype=float)
    if a.size == 0:
        nan = float("nan")
        return Describe(0, nan, nan, nan, nan, nan, nan, nan, n_censored)
    lo, hi = bootstrap_ci(a, boot=boot, seed=seed)
    q1, med, q3 = np.percentile(a, [25, 50, 75])
    return Describe(
        n=int(a.size), mean=float(a.mean()),
        sd=float(a.std(ddof=1)) if a.size > 1 else float("nan"),
        median=float(med), q1=float(q1), q3=float(q3),
        ci_lo=lo, ci_hi=hi, n_censored=int(n_censored),
    )


def bootstrap_ci(x: Sequence[float], boot: int = 10000, alpha: float = 0.05, seed: int = 0):
    """Percentile bootstrap CI of the mean - used because time metrics are skewed."""
    a = np.asarray([v for v in x if np.isfinite(v)], dtype=float)
    if a.size < 2:
        return float("nan"), float("nan")
    rng = np.random.default_rng(seed)
    means = rng.choice(a, size=(boot, a.size), replace=True).mean(axis=1)
    lo, hi = np.percentile(means, [100 * alpha / 2, 100 * (1 - alpha / 2)])
    return float(lo), float(hi)


def hedges_g(x: Sequence[float], y: Sequence[float]) -> float:
    """Bias-corrected standardised mean difference (x - y), paired-agnostic pooled SD."""
    a = np.asarray(x, dtype=float); b = np.asarray(y, dtype=float)
    a = a[np.isfinite(a)]; b = b[np.isfinite(b)]
    if a.size < 2 or b.size < 2:
        return float("nan")
    na, nb = a.size, b.size
    sp2 = ((na - 1) * a.var(ddof=1) + (nb - 1) * b.var(ddof=1)) / (na + nb - 2)
    if sp2 <= 0:
        return float("nan")
    d = (a.mean() - b.mean()) / np.sqrt(sp2)
    j = 1.0 - 3.0 / (4.0 * (na + nb) - 9.0)
    return float(d * j)


def cliffs_delta(x: Sequence[float], y: Sequence[float]) -> float:
    """Rank-based non-parametric effect size in [-1, 1]."""
    a = np.asarray([v for v in x if np.isfinite(v)], dtype=float)
    b = np.asarray([v for v in y if np.isfinite(v)], dtype=float)
    if a.size == 0 or b.size == 0:
        return float("nan")
    gt = (a[:, None] > b[None, :]).sum()
    lt = (a[:, None] < b[None, :]).sum()
    return float((gt - lt) / (a.size * b.size))


def wilson_ci(k: int, n: int, alpha: float = 0.05):
    """Wilson score interval for a proportion."""
    if n == 0:
        return float("nan"), float("nan")
    z = stats.norm.ppf(1 - alpha / 2)
    p = k / n
    den = 1 + z * z / n
    centre = (p + z * z / (2 * n)) / den
    half = z * np.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / den
    return float(max(0.0, centre - half)), float(min(1.0, centre + half))


def risk_difference(k1: int, n1: int, k2: int, n2: int):
    """Difference of proportions with a Newcombe hybrid-score interval."""
    if n1 == 0 or n2 == 0:
        return float("nan"), float("nan"), float("nan")
    p1, p2 = k1 / n1, k2 / n2
    l1, u1 = wilson_ci(k1, n1)
    l2, u2 = wilson_ci(k2, n2)
    return float(p1 - p2), float(p1 - p2 - np.hypot(p1 - l1, u2 - p2)), float(p1 - p2 + np.hypot(u1 - p1, p2 - l2))


def paired_test(x: Sequence[float], y: Sequence[float]) -> dict:
    """Wilcoxon signed-rank on complete pairs; the design is blocked by seed."""
    a = np.asarray(x, dtype=float); b = np.asarray(y, dtype=float)
    m = np.isfinite(a) & np.isfinite(b)
    a, b = a[m], b[m]
    n_pairs = int(a.size)
    out = {"n_pairs": n_pairs, "n_dropped_pairs": int((~m).sum()),
           "statistic": float("nan"), "p": float("nan"), "test": "wilcoxon_signed_rank"}
    if n_pairs < 5 or np.allclose(a, b):
        out["p"] = 1.0 if n_pairs and np.allclose(a, b) else float("nan")
        return out
    try:
        res = stats.wilcoxon(a, b, zero_method="wilcox", alternative="two-sided", method="auto")
        out["statistic"], out["p"] = float(res.statistic), float(res.pvalue)
    except ValueError:
        pass
    return out


def holm(pvals: Sequence[float], labels: Sequence[str] | None = None) -> dict:
    """Holm-Bonferroni step-down adjustment over a pre-declared hypothesis family."""
    p = np.asarray(pvals, dtype=float)
    order = np.argsort(np.where(np.isfinite(p), p, np.inf))
    m = int(np.isfinite(p).sum())
    adj = np.full(p.shape, np.nan)
    running = 0.0
    for rank, idx in enumerate(order):
        if not np.isfinite(p[idx]):
            continue
        val = min(1.0, (m - rank) * p[idx])
        running = max(running, val)
        adj[idx] = running
    if labels is None:
        return {str(i): float(v) for i, v in enumerate(adj)}
    return {str(k): float(v) for k, v in zip(labels, adj)}


def paired_power(diffs: Sequence[float], mde: float, alpha: float = 0.05, power: float = 0.80) -> dict:
    """Required n per cell for a paired design, from pilot within-pair SD."""
    d = np.asarray([v for v in diffs if np.isfinite(v)], dtype=float)
    if d.size < 2:
        return {"sd_diff": float("nan"), "dz": float("nan"), "n_required": None}
    sd = float(d.std(ddof=1))
    if sd <= 0:
        return {"sd_diff": 0.0, "dz": float("inf"), "n_required": 2}
    dz = abs(mde) / sd
    za, zb = stats.norm.ppf(1 - alpha / 2), stats.norm.ppf(power)
    n = int(np.ceil(((za + zb) / dz) ** 2)) + 1
    return {"sd_diff": sd, "dz": float(dz), "n_required": max(2, n)}
