"""Metric model of the protocol (section 7, equations 5-14).

Each function is a direct transcription of one numbered equation, so a
reviewer can check the code against the paper line by line.  The
functions are provenance-agnostic: they operate on transaction records
whatever produced them.
"""

from __future__ import annotations

from typing import Dict, Iterable, Sequence

import numpy as np
import pandas as pd

from .config import MEASURE_S, QUANTILES


def t_visible_first(t_read_ns: np.ndarray, t_send_ns: np.ndarray) -> np.ndarray:
    """Equation (5): ``min_r t_read(i,r) - t_send(i)``, milliseconds.

    ``t_read_ns`` has shape ``(n_readers, n_tx)``.  All timestamps come
    from one client-side monotonic clock, so no inter-host offset enters.
    """
    return (np.min(t_read_ns, axis=0) - t_send_ns) / 1e6


def t_visible_all(t_read_ns: np.ndarray, t_send_ns: np.ndarray) -> np.ndarray:
    """Equation (6): ``max_r t_read(i,r) - t_send(i)``, milliseconds."""
    return (np.max(t_read_ns, axis=0) - t_send_ns) / 1e6


def t_convergence(t_read_ns: np.ndarray) -> np.ndarray:
    """Equation (7): spread between the earliest and latest read node."""
    return (np.max(t_read_ns, axis=0) - np.min(t_read_ns, axis=0)) / 1e6


def empirical_quantile(x: Sequence[float], p: float) -> float:
    """Equation (8): ``Q_p(T) = inf{x : F_T(x) >= p}``.

    This is the inverse of the empirical CDF, i.e. the order statistic
    ``x_(ceil(p*n))``.  NumPy calls it ``inverted_cdf``; the default linear
    interpolation and the ``lower`` method both violate the definition —
    ``lower`` returns the 0.75-quantile when asked for the 0.99-quantile of
    four observations, because it interpolates on ``(n-1)*p`` rather than
    inverting the step function.  The returned value is always an observed
    latency, never a value between two of them.
    """
    a = np.asarray(x, dtype=float)
    if a.size == 0:
        return float("nan")
    return float(np.quantile(a, p, method="inverted_cdf"))


def goodput(n_success: int, window_s: float = MEASURE_S) -> float:
    """Equation (9): committed goodput in transactions per second."""
    return n_success / window_s


def availability(n_success: int, n_submitted: int) -> float:
    """Equation (10): per cent of submitted transactions that became visible.

    Timeouts, reverts and RPC errors stay in the denominator.
    """
    if n_submitted == 0:
        return float("nan")
    return 100.0 * n_success / n_submitted


def consistency(n_agree: int, n_success: int) -> float:
    """Equation (11): per cent of successful transactions on which every
    read node returned the same value and sequence before the timeout."""
    if n_success == 0:
        return float("nan")
    return 100.0 * n_agree / n_success


def quantile_improvement_pct(q_baseline: float, q_profile: float) -> float:
    """Equation (12): ``(Q_baseline - Q_profile) / Q_baseline * 100``.

    Positive values mean the profile is faster than the baseline.
    """
    if q_baseline == 0 or not np.isfinite(q_baseline):
        return float("nan")
    return (q_baseline - q_profile) / q_baseline * 100.0


def observed_block_interval(block_time_ms: Sequence[float]) -> float:
    """Equation (13): median of consecutive block-header time differences."""
    t = np.sort(np.unique(np.asarray(block_time_ms, dtype=float)))
    t = t[np.isfinite(t)]
    if t.size < 2:
        return float("nan")
    return float(np.median(np.diff(t)))


def theil_sen_slope(y: Sequence[float], x: Sequence[float] | None = None) -> float:
    """Equation (14): Theil-Sen slope of the queue depth over time.

    Median of pairwise slopes, robust to the bursts that a mempool shows
    even in a stable regime.  Returned in units of ``y`` per unit of ``x``.
    """
    y = np.asarray(y, dtype=float)
    x = np.arange(y.size, dtype=float) if x is None else np.asarray(x, dtype=float)
    ok = np.isfinite(y) & np.isfinite(x)
    y, x = y[ok], x[ok]
    n = y.size
    if n < 3:
        return float("nan")
    i, j = np.triu_indices(n, k=1)
    dx = x[j] - x[i]
    nz = dx != 0
    if not nz.any():
        return float("nan")
    return float(np.median((y[j][nz] - y[i][nz]) / dx[nz]))


def theil_sen_slope_ci(
    y: Sequence[float],
    x: Sequence[float] | None = None,
    level: float = 0.95,
) -> Dict[str, float]:
    """Theil-Sen slope with its distribution-free confidence interval.

    The interval follows the Kendall-tau based construction: the rank
    offsets ``(N -/+ C_alpha) / 2`` of the sorted pairwise slopes, where
    ``C_alpha = z * sqrt(n(n-1)(2n+5)/18)``.  Used by the stability rule
    "the CI must not confirm positive backlog accumulation".
    """
    from math import sqrt

    from scipy.stats import norm

    y = np.asarray(y, dtype=float)
    x = np.arange(y.size, dtype=float) if x is None else np.asarray(x, dtype=float)
    ok = np.isfinite(y) & np.isfinite(x)
    y, x = y[ok], x[ok]
    n = y.size
    if n < 4:
        return {"slope": float("nan"), "ci_low": float("nan"), "ci_high": float("nan")}
    i, j = np.triu_indices(n, k=1)
    dx = x[j] - x[i]
    nz = dx != 0
    slopes = np.sort((y[j][nz] - y[i][nz]) / dx[nz])
    N = slopes.size
    z = norm.ppf(0.5 + level / 2.0)
    c = z * sqrt(n * (n - 1) * (2 * n + 5) / 18.0)
    lo = int(np.clip(np.floor((N - c) / 2.0), 0, N - 1))
    hi = int(np.clip(np.ceil((N + c) / 2.0) - 1, 0, N - 1))
    return {
        "slope": float(np.median(slopes)),
        "ci_low": float(slopes[lo]),
        "ci_high": float(slopes[hi]),
    }


def run_quantiles(
    values: Sequence[float], quantiles: Iterable[float] = QUANTILES, prefix: str = ""
) -> Dict[str, float]:
    """Named quantiles of one run, e.g. ``{"p50_ms": ..., "p99_ms": ...}``."""
    return {
        f"{prefix}p{int(round(p * 100))}_ms": empirical_quantile(values, p)
        for p in quantiles
    }


def half_split_drift_pct(values: Sequence[float], p: float = 0.99) -> float:
    """Change of the ``p`` quantile between the second and first half of a run.

    Protocol Table 13 rejects a run whose tail degrades by more than
    20 %: a stable regime must not get worse as the window progresses.
    """
    a = np.asarray(values, dtype=float)
    if a.size < 20:
        return float("nan")
    mid = a.size // 2
    q1 = empirical_quantile(a[:mid], p)
    q2 = empirical_quantile(a[mid:], p)
    if not np.isfinite(q1) or q1 == 0:
        return float("nan")
    return (q2 - q1) / q1 * 100.0
