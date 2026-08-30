"""RTO-bounded normalized resilience index - Eq. (15), (18), (19)."""
from __future__ import annotations

import numpy as np

__all__ = ["nri", "recovery_time", "availability_below"]


def nri(t: np.ndarray, A: np.ndarray, t_d: float, rto: float, A_max: float = 1.0) -> float:
    """Trapezoidal NRI over [t_d, t_d + 2*RTO] - Eq. (18), (19).

    The window is clipped to the available trace; the denominator uses the same
    clipped window so that NRI stays in [0,1] and is comparable across runs.
    """
    t = np.asarray(t, dtype=float)
    A = np.asarray(A, dtype=float)
    lo, hi = t_d, t_d + 2.0 * rto
    hi = min(hi, float(t[-1]))
    if hi <= lo:
        return float("nan")
    m = (t >= lo) & (t <= hi)
    if m.sum() < 2:
        return float("nan")
    tt, aa = t[m], A[m]
    return float(np.trapezoid(aa, tt) / (A_max * (tt[-1] - tt[0])))


def recovery_time(t: np.ndarray, A: np.ndarray, t_a: float, a_min: float, hold: float) -> float:
    """Eq. (15): first instant after t_a from which A stays >= a_min for `hold`.

    Returns NaN when no such instant exists inside the trace (right-censored run);
    the caller must record the run as censored rather than dropping it.
    """
    t = np.asarray(t, dtype=float)
    A = np.asarray(A, dtype=float)
    idx = np.where(t >= t_a)[0]
    for i in idx:
        w = (t >= t[i]) & (t <= t[i] + hold)
        if t[-1] < t[i] + hold:
            return float("nan")
        if np.all(A[w] >= a_min):
            return float(t[i] - t_a)
    return float("nan")


def availability_below(t: np.ndarray, A: np.ndarray, a_min: float) -> float:
    """Fraction of the observation window spent below the availability floor."""
    t = np.asarray(t, dtype=float)
    A = np.asarray(A, dtype=float)
    if t[-1] <= t[0]:
        return float("nan")
    below = (A < a_min).astype(float)
    return float(np.trapezoid(below, t) / (t[-1] - t[0]))
