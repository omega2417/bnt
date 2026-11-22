"""Statistical helpers: sample-size planning (Eq. 22), rule of three, confidence intervals,
calibration error and the Friedman/Nemenyi critical difference used in Section 5.5."""
from __future__ import annotations

import math

import numpy as np
from scipy import stats

from .model import wilson_ci  # noqa: F401  (re-exported)

Q05_NEMENYI = {2: 1.960, 3: 2.343, 4: 2.569, 5: 2.728, 6: 2.850, 7: 2.949, 8: 3.031}  # Demsar (2006)


def n_two_proportions(p1: float, p2: float, alpha: float = 0.05, power: float = 0.80) -> int:
    """Equation (22): proposals per policy for a two-sided comparison of two proportions."""
    za, zb = stats.norm.ppf(1 - alpha / 2), stats.norm.ppf(power)
    return math.ceil((za + zb) ** 2 * (p1 * (1 - p1) + p2 * (1 - p2)) / (p1 - p2) ** 2)


def rule_of_three_n(upper: float = 0.01) -> int:
    """Smallest number of trials with zero events whose 95 % upper bound is <= ``upper``."""
    return math.ceil(3.0 / upper)


def zero_event_upper(n: int, conf: float = 0.95) -> float:
    """Exact (Clopper-Pearson) one-sided upper bound for 0 events in n trials."""
    return 1.0 - (1.0 - conf) ** (1.0 / n) if n > 0 else 1.0


def t_ci(x, conf: float = 0.95):
    """Mean and half-width of the Student-t interval."""
    x = np.asarray(x, float)
    if len(x) < 2:
        return float(x.mean()) if len(x) else float("nan"), float("nan")
    h = stats.t.ppf(0.5 + conf / 2, len(x) - 1) * x.std(ddof=1) / math.sqrt(len(x))
    return float(x.mean()), float(h)


def expected_calibration_error(conf, y, n_bins: int = 15) -> float:
    conf, y = np.asarray(conf, float), np.asarray(y, float)
    edges = np.linspace(0, 1, n_bins + 1)
    idx = np.clip(np.digitize(conf, edges) - 1, 0, n_bins - 1)
    ece = 0.0
    for b in range(n_bins):
        m = idx == b
        if m.any():
            ece += m.mean() * abs(y[m].mean() - conf[m].mean())
    return float(ece)


def conservativeness(conf, y, n_bins: int = 15) -> float:
    """Share of occupied bins in which the empirical precision is at least the mean
    confidence (1.0 = the map never overstates confidence)."""
    conf, y = np.asarray(conf, float), np.asarray(y, float)
    edges = np.linspace(0, 1, n_bins + 1)
    idx = np.clip(np.digitize(conf, edges) - 1, 0, n_bins - 1)
    ok = tot = 0
    for b in range(n_bins):
        m = idx == b
        if m.sum() >= 20:
            tot += 1
            ok += int(y[m].mean() >= conf[m].mean() - 1e-12)
    return ok / tot if tot else float("nan")


def friedman_nemenyi(table):
    """``table``: blocks x treatments (pandas DataFrame).  Returns mean ranks, Friedman chi2,
    p, Iman-Davenport F and p, and the Nemenyi critical difference at alpha = 0.05."""
    N, k = table.shape
    ranks = table.rank(axis=1, method="average").mean()
    chi2, p = stats.friedmanchisquare(*[table[c] for c in table.columns])
    ff = (N - 1) * chi2 / (N * (k - 1) - chi2)
    p_ff = stats.f.sf(ff, k - 1, (k - 1) * (N - 1))
    cd = Q05_NEMENYI[k] * math.sqrt(k * (k + 1) / (6.0 * N))
    return dict(N=N, k=k, ranks=ranks.sort_values().to_dict(), chi2=float(chi2), p=float(p), FF=float(ff),
                p_FF=float(p_ff), CD=float(cd))
