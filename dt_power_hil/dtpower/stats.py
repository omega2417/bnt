"""Paired statistics at the run/block level (section 16.6)."""
from __future__ import annotations

import itertools

import numpy as np
from scipy import stats as sps


def bca_ci(d, n_boot: int = 10000, alpha: float = 0.05, seed: int = 20260929):
    d = np.asarray(d, float)
    n = len(d)
    theta = d.mean()
    if n < 3 or np.allclose(d, d[0]):
        return float(theta), float(theta), float(theta)
    rng = np.random.default_rng(seed)
    boots = d[rng.integers(0, n, (n_boot, n))].mean(axis=1)
    prop = np.clip((boots < theta).mean(), 1e-6, 1 - 1e-6)
    z0 = sps.norm.ppf(prop)
    jack = np.array([np.delete(d, i).mean() for i in range(n)])
    jm = jack.mean()
    num, den = ((jm - jack) ** 3).sum(), 6 * (((jm - jack) ** 2).sum() ** 1.5)
    a = num / den if den > 0 else 0.0
    zl, zu = sps.norm.ppf(alpha / 2), sps.norm.ppf(1 - alpha / 2)
    p_lo = sps.norm.cdf(z0 + (z0 + zl) / (1 - a * (z0 + zl)))
    p_hi = sps.norm.cdf(z0 + (z0 + zu) / (1 - a * (z0 + zu)))
    return float(theta), float(np.quantile(boots, p_lo)), float(np.quantile(boots, p_hi))


def sign_flip_p(d):
    """Exact two-sided paired sign-flip (randomisation) test on the mean."""
    d = np.asarray(d, float)
    n = len(d)
    obs = abs(d.mean())
    if np.allclose(d, 0):
        return 1.0
    cnt = 0
    tot = 0
    for signs in itertools.product((1, -1), repeat=n):
        tot += 1
        cnt += abs((d * np.array(signs)).mean()) >= obs - 1e-12
    return cnt / tot


def holm(pvals: dict) -> dict:
    items = sorted(pvals.items(), key=lambda kv: kv[1])
    m = len(items)
    out, running = {}, 0.0
    for i, (k, p) in enumerate(items):
        running = max(running, min(1.0, (m - i) * p))
        out[k] = running
    return out


def paired_summary(a, b, label: str):
    """Improvement-oriented contrast b - a (caller orients the sign)."""
    d = np.asarray(b, float) - np.asarray(a, float)
    m, lo, hi = bca_ci(d)
    return {"contrast": label, "n": len(d), "mean": m, "ci_lo": lo, "ci_hi": hi, "median": float(np.median(d)),
            "sd": float(d.std(ddof=1)) if len(d) > 1 else 0.0, "p_signflip": sign_flip_p(d),
            "frac_positive": float((d > 0).mean()), "diffs": d.tolist(),
            "min_attainable_p": 2 / 2 ** len(d)}


def friedman(*groups):
    try:
        r = sps.friedmanchisquare(*groups)
        return {"chi2": float(r.statistic), "p": float(r.pvalue), "df": len(groups) - 1}
    except ValueError as e:
        return {"error": str(e)}
