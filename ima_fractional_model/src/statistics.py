"""Statistical estimators for the ensemble analysis.

Self-contained implementations (no lifelines / statsmodels dependency):
  * Wilson score interval for a binomial proportion (catastrophe probability);
  * Kaplan-Meier survival estimator with right-censoring and a Greenwood /
    log-log 95% CI for the median time-to-catastrophe;
  * Partial Rank Correlation Coefficients (PRCC) with Fisher-z confidence
    intervals for monotonic sensitivity of T_cat to sampled inputs.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional, Sequence, Tuple

import numpy as np
from scipy import stats


# --------------------------------------------------------------------- Wilson CI
def wilson_ci(successes: int, n: int, confidence: float = 0.95) -> Tuple[float, float, float]:
    """Wilson score interval for a binomial proportion.

    Returns (p_hat, lower, upper).
    """
    if n == 0:
        return (float("nan"), 0.0, 1.0)
    z = stats.norm.ppf(1 - (1 - confidence) / 2)
    p = successes / n
    denom = 1 + z**2 / n
    centre = (p + z**2 / (2 * n)) / denom
    half = (z * np.sqrt(p * (1 - p) / n + z**2 / (4 * n**2))) / denom
    return (p, max(0.0, centre - half), min(1.0, centre + half))


# ------------------------------------------------------------------- Kaplan-Meier
@dataclass
class KMResult:
    times: np.ndarray
    survival: np.ndarray
    median: Optional[float]
    median_ci: Tuple[Optional[float], Optional[float]]
    var: np.ndarray


def kaplan_meier(durations: Sequence[float], events: Sequence[int],
                 confidence: float = 0.95) -> KMResult:
    """Kaplan-Meier estimator with right censoring.

    Parameters
    ----------
    durations : observed time for each subject (T_cat if catastrophe, else horizon)
    events    : 1 if catastrophe occurred (event), 0 if right-censored
    """
    durations = np.asarray(durations, dtype=float)
    events = np.asarray(events, dtype=int)
    order = np.argsort(durations)
    durations, events = durations[order], events[order]
    n = len(durations)

    uniq = np.unique(durations[events == 1])
    S = 1.0
    surv_t, surv_S, greenwood = [0.0], [1.0], [0.0]
    cum_var = 0.0
    for t in uniq:
        at_risk = np.sum(durations >= t)
        d = np.sum((durations == t) & (events == 1))
        if at_risk == 0:
            continue
        S *= (1 - d / at_risk)
        if at_risk > d:
            cum_var += d / (at_risk * (at_risk - d))
        surv_t.append(float(t))
        surv_S.append(float(S))
        greenwood.append(float(S**2 * cum_var))

    surv_t = np.array(surv_t)
    surv_S = np.array(surv_S)
    greenwood = np.array(greenwood)

    # median: smallest t with S(t) <= 0.5
    median = None
    below = np.where(surv_S <= 0.5)[0]
    if len(below):
        median = float(surv_t[below[0]])

    # 95% CI for the median via the Greenwood-band inversion.
    # Median = min{t: S(t) <= 0.5}.  Confidence limits:
    #   lower limit = min{t: S_lo(t) <= 0.5}  (lower survival band, crosses earlier)
    #   upper limit = min{t: S_hi(t) <= 0.5}  (upper survival band, crosses later)
    z = stats.norm.ppf(1 - (1 - confidence) / 2)
    lower = upper = None
    if median is not None:
        se = np.sqrt(np.maximum(greenwood, 0.0))
        lo_S = np.clip(surv_S - z * se, 0.0, 1.0)
        hi_S = np.clip(surv_S + z * se, 0.0, 1.0)
        li = np.where(lo_S <= 0.5)[0]
        ui = np.where(hi_S <= 0.5)[0]
        if len(li):
            lower = float(surv_t[li[0]])
        if len(ui):
            upper = float(surv_t[ui[0]])

    return KMResult(times=surv_t, survival=surv_S, median=median,
                    median_ci=(lower, upper), var=greenwood)


# ------------------------------------------------------------------------- PRCC
def prcc(X: np.ndarray, y: np.ndarray, names: Sequence[str],
         confidence: float = 0.95) -> Dict[str, Dict[str, float]]:
    """Partial Rank Correlation Coefficients of each column of X vs y.

    Ranks are used (Spearman-style). For each input k, PRCC is the partial
    correlation of rank(X_k) and rank(y) controlling for all other ranked inputs.
    Returns {name: {prcc, ci_low, ci_high, p_value}}.
    """
    X = np.asarray(X, dtype=float)
    y = np.asarray(y, dtype=float)
    n, p = X.shape

    Rx = np.column_stack([stats.rankdata(X[:, k]) for k in range(p)])
    Ry = stats.rankdata(y)
    M = np.column_stack([Rx, Ry])
    # standardise
    M = (M - M.mean(0)) / M.std(0)
    C = np.corrcoef(M, rowvar=False)
    try:
        P = np.linalg.inv(C)
    except np.linalg.LinAlgError:
        P = np.linalg.pinv(C)

    out: Dict[str, Dict[str, float]] = {}
    z = stats.norm.ppf(1 - (1 - confidence) / 2)
    for k, name in enumerate(names):
        # partial corr between input k (index k) and output (index p)
        denom = np.sqrt(P[k, k] * P[p, p])
        r = -P[k, p] / denom if denom > 0 else 0.0
        r = float(np.clip(r, -0.999999, 0.999999))
        # Fisher z CI
        if n - p - 1 > 0:
            se = 1.0 / np.sqrt(n - p - 1)
            zr = np.arctanh(r)
            lo, hi = np.tanh(zr - z * se), np.tanh(zr + z * se)
            t = r * np.sqrt((n - p - 1) / (1 - r**2)) if abs(r) < 1 else np.inf
            pval = 2 * (1 - stats.t.cdf(abs(t), df=n - p - 1))
        else:
            lo = hi = pval = float("nan")
        out[name] = dict(prcc=r, ci_low=float(lo), ci_high=float(hi), p_value=float(pval))
    return out


# ------------------------------------------------------------------ summary stats
def iqr(values: Sequence[float]) -> Tuple[float, float]:
    v = np.asarray(values, dtype=float)
    v = v[np.isfinite(v)]
    if len(v) == 0:
        return (float("nan"), float("nan"))
    return (float(np.percentile(v, 25)), float(np.percentile(v, 75)))


def median_or_nan(values: Sequence[float]) -> float:
    v = np.asarray(values, dtype=float)
    v = v[np.isfinite(v)]
    return float(np.median(v)) if len(v) else float("nan")


__all__ = ["wilson_ci", "kaplan_meier", "KMResult", "prcc", "iqr", "median_or_nan"]
