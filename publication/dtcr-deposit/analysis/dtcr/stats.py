"""Statistical estimators for every effect reported in the manuscript.

Covers the descriptive statistics, paired and unpaired inference, bootstrap
confidence intervals for skewed latency distributions, effect sizes, and
binomial intervals for classification rates required by Sections 2.3, 6.1 and
9 of the revision plan.
"""
from __future__ import annotations

import numpy as np
from scipy import stats as sps

__all__ = ["describe", "t_ci", "bootstrap_ci", "paired_bootstrap_diff_ci",
           "hedges_g", "cliffs_delta", "compare_groups", "wilson_ci",
           "classification_metrics", "holm_bonferroni"]


def describe(x) -> dict:
    """n, mean, SD, median, IQR, min, max and the 95% t interval for the mean."""
    x = np.asarray(x, float)
    x = x[~np.isnan(x)]
    n = x.size
    if n == 0:
        return {"n": 0}
    sd = float(x.std(ddof=1)) if n > 1 else float("nan")
    q1, q3 = np.percentile(x, [25, 75])
    lo, hi = t_ci(x)
    return {"n": int(n), "mean": float(x.mean()), "sd": sd,
            "median": float(np.median(x)), "q1": float(q1), "q3": float(q3),
            "iqr": float(q3 - q1), "min": float(x.min()), "max": float(x.max()),
            "ci95_lo": lo, "ci95_hi": hi}


def t_ci(x, conf: float = 0.95):
    """Eq. (23): mean +/- t_{1-alpha/2, n-1} * s / sqrt(n)."""
    x = np.asarray(x, float)
    x = x[~np.isnan(x)]
    n = x.size
    if n < 2:
        return (float("nan"), float("nan"))
    h = sps.t.ppf(0.5 + conf / 2, n - 1) * x.std(ddof=1) / np.sqrt(n)
    return (float(x.mean() - h), float(x.mean() + h))


def bootstrap_ci(x, statistic=np.mean, n_boot: int = 10000, conf: float = 0.95,
                 seed: int = 20260731):
    """Percentile bootstrap interval; preferred for skewed latency distributions."""
    x = np.asarray(x, float)
    x = x[~np.isnan(x)]
    rng = np.random.default_rng(seed)
    idx = rng.integers(0, x.size, size=(n_boot, x.size))
    boots = statistic(x[idx], axis=1)
    lo, hi = np.percentile(boots, [(1 - conf) / 2 * 100, (1 + conf) / 2 * 100])
    return {"point": float(statistic(x)), "ci95_lo": float(lo), "ci95_hi": float(hi),
            "n_boot": n_boot}


def paired_bootstrap_diff_ci(a, b, n_boot: int = 10000, conf: float = 0.95,
                             seed: int = 20260731):
    """Bootstrap interval for the paired mean difference a - b."""
    a, b = np.asarray(a, float), np.asarray(b, float)
    if a.shape != b.shape:
        raise ValueError("paired samples must have equal length")
    keep = ~(np.isnan(a) | np.isnan(b))
    a, b = a[keep], b[keep]
    rng = np.random.default_rng(seed)
    idx = rng.integers(0, a.size, size=(n_boot, a.size))
    boots = (a[idx] - b[idx]).mean(axis=1)
    lo, hi = np.percentile(boots, [(1 - conf) / 2 * 100, (1 + conf) / 2 * 100])
    return {"mean_diff": float((a - b).mean()), "ci95_lo": float(lo),
            "ci95_hi": float(hi), "n_pairs": int(a.size)}


def hedges_g(a, b) -> float:
    """Bias-corrected standardised mean difference for two independent samples."""
    a, b = np.asarray(a, float), np.asarray(b, float)
    a, b = a[~np.isnan(a)], b[~np.isnan(b)]
    na, nb = a.size, b.size
    if na < 2 or nb < 2:
        return float("nan")
    sp = np.sqrt(((na - 1) * a.var(ddof=1) + (nb - 1) * b.var(ddof=1)) / (na + nb - 2))
    if sp == 0:
        return float("nan")
    d = (a.mean() - b.mean()) / sp
    j = 1 - 3 / (4 * (na + nb) - 9)
    return float(d * j)


def cliffs_delta(a, b) -> float:
    """Non-parametric effect size in [-1, 1]; robust to the skew of recovery times."""
    a, b = np.asarray(a, float), np.asarray(b, float)
    a, b = a[~np.isnan(a)], b[~np.isnan(b)]
    if a.size == 0 or b.size == 0:
        return float("nan")
    gt = (a[:, None] > b[None, :]).sum()
    lt = (a[:, None] < b[None, :]).sum()
    return float((gt - lt) / (a.size * b.size))


def compare_groups(baseline, framework, paired: bool = True, seed: int = 20260731):
    """Full comparison record for one scenario and one lower-is-better metric.

    ``paired=True`` is correct only when the two arms ran on a single
    interleaved schedule with matched repetition indices; the flag is recorded in
    the output so the manuscript states which design was used.
    """
    b = np.asarray(baseline, float)
    f = np.asarray(framework, float)
    out = {"baseline": describe(b), "framework": describe(f), "paired": bool(paired)}
    out["abs_diff_mean"] = out["framework"]["mean"] - out["baseline"]["mean"]
    out["rel_reduction_pct"] = (
        100.0 * (out["baseline"]["mean"] - out["framework"]["mean"]) / out["baseline"]["mean"]
        if out["baseline"]["mean"] else float("nan"))
    if paired and b.size == f.size:
        keep = ~(np.isnan(b) | np.isnan(f))
        tt = sps.ttest_rel(b[keep], f[keep])
        wx = sps.wilcoxon(b[keep], f[keep]) if keep.sum() > 0 else None
        out["test"] = {"name": "paired t-test", "statistic": float(tt.statistic),
                       "p_value": float(tt.pvalue), "df": int(keep.sum() - 1)}
        out["test_nonparametric"] = {
            "name": "Wilcoxon signed-rank",
            "statistic": float(wx.statistic), "p_value": float(wx.pvalue)}
        out["diff_ci"] = paired_bootstrap_diff_ci(f, b, seed=seed)
    else:
        tt = sps.ttest_ind(b, f, equal_var=False, nan_policy="omit")
        mw = sps.mannwhitneyu(b[~np.isnan(b)], f[~np.isnan(f)], alternative="two-sided")
        out["test"] = {"name": "Welch t-test", "statistic": float(tt.statistic),
                       "p_value": float(tt.pvalue)}
        out["test_nonparametric"] = {"name": "Mann-Whitney U",
                                     "statistic": float(mw.statistic),
                                     "p_value": float(mw.pvalue)}
    out["hedges_g"] = hedges_g(b, f)
    out["cliffs_delta"] = cliffs_delta(b, f)
    return out


def wilson_ci(successes: int, n: int, conf: float = 0.95):
    """Wilson score interval; correct near 0 and 1 where the normal interval fails."""
    if n == 0:
        return (float("nan"), float("nan"))
    z = sps.norm.ppf(0.5 + conf / 2)
    p = successes / n
    denom = 1 + z ** 2 / n
    centre = (p + z ** 2 / (2 * n)) / denom
    half = z * np.sqrt(p * (1 - p) / n + z ** 2 / (4 * n ** 2)) / denom
    return (float(max(0.0, centre - half)), float(min(1.0, centre + half)))


def classification_metrics(tp: int, tn: int, fp: int, fn: int) -> dict:
    """Full confusion-matrix report with Wilson intervals for every rate."""
    n = tp + tn + fp + fn
    pos, neg = tp + fn, tn + fp
    def _safe(a, b):
        return a / b if b else float("nan")
    acc = _safe(tp + tn, n)
    rec = _safe(tp, pos)
    spec = _safe(tn, neg)
    prec = _safe(tp, tp + fp)
    f1 = _safe(2 * prec * rec, prec + rec) if not (np.isnan(prec) or np.isnan(rec)) else float("nan")
    mcc_den = np.sqrt(float(tp + fp) * (tp + fn) * (tn + fp) * (tn + fn))
    mcc = (tp * tn - fp * fn) / mcc_den if mcc_den > 0 else float("nan")
    return {
        "n": n, "positives": pos, "negatives": neg,
        "tp": tp, "tn": tn, "fp": fp, "fn": fn,
        "accuracy": acc, "accuracy_ci95": wilson_ci(tp + tn, n),
        "recall": rec, "recall_ci95": wilson_ci(tp, pos),
        "specificity": spec, "specificity_ci95": wilson_ci(tn, neg),
        "precision": prec, "precision_ci95": wilson_ci(tp, tp + fp),
        "f1": f1, "mcc": float(mcc),
        "fpr": _safe(fp, neg), "fpr_ci95": wilson_ci(fp, neg),
        "fnr": _safe(fn, pos), "fnr_ci95": wilson_ci(fn, pos),
    }


def holm_bonferroni(pvalues, alpha: float = 0.05):
    """Holm correction for the family of scenario-level tests."""
    p = np.asarray(pvalues, float)
    order = np.argsort(p)
    m = p.size
    adjusted = np.empty(m)
    running = 0.0
    for rank, idx in enumerate(order):
        running = max(running, (m - rank) * p[idx])
        adjusted[idx] = min(1.0, running)
    return {"p_adjusted": adjusted.tolist(),
            "reject": (adjusted <= alpha).tolist(), "alpha": alpha}
