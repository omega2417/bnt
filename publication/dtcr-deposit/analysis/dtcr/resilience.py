"""Availability, recovery time and the normalized resilience index.

Implements manuscript Eq. (15), (18) and (19).  The manuscript reuses the symbol
``t_d`` for both detection time and disruption time; this module keeps them
strictly separate as ``t_det`` and ``t_dis`` and the integration window of
Eq. (18) is anchored on ``t_dis``.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np

__all__ = ["NRIConfig", "recovery_time", "nri", "nri_from_trace", "resilience_deficit"]


@dataclass(frozen=True)
class NRIConfig:
    """Every quantity Figure 6 and Eq. (18) depend on, stated explicitly."""

    rto: float = 300.0            # organizational recovery-time objective, s
    a_min: float = 0.95           # acceptable availability threshold
    a_max: float = 1.00           # ideal availability used as the denominator
    hold: float = 30.0            # Delta_h, s
    sampling_interval: float = 1.0  # s


def recovery_time(t: np.ndarray, a: np.ndarray, t_attack: float,
                  cfg: NRIConfig) -> float:
    """Eq. (15): first instant from which A >= a_min holds for the whole hold window.

    Returns ``nan`` when availability never satisfies the hold condition inside
    the observed trace; the caller must treat such runs as censored rather than
    dropping them silently.
    """
    t = np.asarray(t, float)
    a = np.asarray(a, float)
    mask = t >= t_attack
    ts, as_ = t[mask], a[mask]
    if ts.size == 0:
        return float("nan")
    ok = as_ >= cfg.a_min
    for i in range(ts.size):
        if not ok[i]:
            continue
        window = (ts >= ts[i]) & (ts <= ts[i] + cfg.hold)
        if ts[window][-1] < ts[i] + cfg.hold - cfg.sampling_interval / 2:
            break  # hold window runs past the end of the trace -> censored
        if ok[window].all():
            return float(ts[i] - t_attack)
    return float("nan")


def nri(t: np.ndarray, a: np.ndarray, t_dis: float, cfg: NRIConfig) -> float:
    """Eq. (18)-(19): trapezoidal AUC over [t_dis, t_dis + 2*RTO] normalised by A_max.

    The window is resampled onto the trace grid with linear interpolation at both
    endpoints so that traces with different sampling offsets are comparable.
    """
    t = np.asarray(t, float)
    a = np.asarray(a, float)
    t0, t1 = t_dis, t_dis + 2.0 * cfg.rto
    if t1 > t[-1] + 1e-9:
        raise ValueError(
            f"trace ends at {t[-1]:.1f}s but the NRI window needs {t1:.1f}s")
    grid = np.unique(np.concatenate(([t0], t[(t > t0) & (t < t1)], [t1])))
    vals = np.interp(grid, t, a)
    area = np.trapezoid(vals, grid) if hasattr(np, "trapezoid") else np.trapz(vals, grid)
    return float(area / (cfg.a_max * (t1 - t0)))


def nri_from_trace(df, cfg: NRIConfig, t_col="t_s", a_col="availability",
                   t_dis: float | None = None) -> float:
    """Convenience wrapper for a two-column availability trace DataFrame."""
    t = df[t_col].to_numpy(float)
    a = df[a_col].to_numpy(float)
    if t_dis is None:
        below = np.flatnonzero(a < cfg.a_min)
        if below.size == 0:
            return 1.0
        t_dis = float(t[below[0]])
    return nri(t, a, t_dis, cfg)


def resilience_deficit(value: float) -> float:
    """1 - NRI, the cumulative availability loss relative to the ideal curve."""
    return 1.0 - float(value)
