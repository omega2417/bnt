"""Generation and demand profiles (protocol section 10)."""
from __future__ import annotations

import numpy as np


def pv_shape(start_h: int = 6, end_h: int = 16) -> np.ndarray:
    """Normalised hourly PV shape a_h (sums to 1), eq. in section 10.1."""
    h = np.arange(24)
    w = np.where((h >= start_h) & (h < end_h),
                 np.sin(np.pi * (h + 0.5 - start_h) / (end_h - start_h)), 0.0)
    w = np.clip(w, 0.0, None)
    return w / w.sum()


def light_mask(on_hour: int = 18, hours: int = 6) -> np.ndarray:
    h = np.arange(24)
    return ((h >= on_hour) & (h < on_hour + hours)).astype(float)


def hourly_profiles(pv_wp: float, psh_days, k_der: float, p_base: float,
                    p_light: float, on_hour: int = 18, light_hours: int = 6,
                    start_h: int = 6, end_h: int = 16):
    """Return (pv_w, crit_w, aux_w) hourly arrays of length 24*len(psh_days).

    Hourly mean power is held constant inside the hour, which preserves the
    daily energy integral exactly (section 10.1).
    """
    a = pv_shape(start_h, end_h)
    lm = light_mask(on_hour, light_hours)
    pv, crit, aux = [], [], []
    for psh in psh_days:
        e_day = pv_wp * psh * k_der
        pv.append(e_day * a)
        crit.append(np.full(24, p_base))
        aux.append(p_light * lm)
    return np.concatenate(pv), np.concatenate(crit), np.concatenate(aux)


def upsample(hourly: np.ndarray, step_s: float) -> np.ndarray:
    """Zero-order hold from 1 h to step_s, energy preserving."""
    n = int(round(3600 / step_s))
    return np.repeat(hourly, n)


def step_profile(segments, dt_s: float = 1.0) -> np.ndarray:
    """segments: list of (duration_s, value). Returns per-step array."""
    out = [np.full(int(round(d / dt_s)), v, dtype=float) for d, v in segments]
    return np.concatenate(out) if out else np.zeros(0)
