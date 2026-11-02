"""Poisson pseudo-maximum likelihood (PPML) with fixed effects, implemented with
explicit dummies and iteratively re-weighted least squares (IRLS).

The panel is small (about 150 origins x 15 years), so explicit dummies are exact
and fast enough for bootstrap work. Results should coincide with ``ppmlhdfe``
(Correia, Guimaraes and Zylkin 2020) up to numerical tolerance, provided the same
observations are dropped. Differences to be aware of:

* separation: this module drops fixed-effect groups whose outcome is always zero
  (iteratively). ``ppmlhdfe`` additionally runs the ReLU separation check; with the
  regressors used in the article this rarely matters, but the authors should
  compare the reported number of observations with the Stata log.
* small-sample correction of the clustered variance: G/(G-1), as in ppmlhdfe.

Also provided:
* ``pairs_cluster_bootstrap`` - resample whole origins with replacement;
* ``wild_score_test`` - null-imposed wild cluster score bootstrap
  (Kline and Santos 2012) with Rademacher or Webb weights, and
  ``wild_score_ci`` - confidence set by test inversion.
"""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd
from scipy import linalg, stats
from scipy.special import gammaln


@dataclass
class PPMLResult:
    coef: pd.Series
    se: pd.Series
    pval: pd.Series
    vcov: pd.DataFrame
    nobs: int
    n_clusters: int
    pseudo_r2: float
    converged: bool
    iterations: int
    dropped_vars: list = field(default_factory=list)
    sample: pd.Index = None
    mu: np.ndarray = None

    def row(self, var: str):
        if var not in self.coef.index or not np.isfinite(self.coef[var]):
            return (np.nan, np.nan, np.nan)
        return (self.coef[var], self.se[var], self.pval[var])


def _drop_all_zero_groups(d: pd.DataFrame, y: str, fe: list[str]) -> pd.DataFrame:
    while True:
        n0 = len(d)
        for f in fe:
            pos = d.groupby(f)[y].transform("sum") > 0
            d = d[pos]
        if len(d) == n0:
            return d


def prepare_sample(df, y, x, fe, cluster, extra=()):
    cols = list(dict.fromkeys([y, *x, *fe, cluster, *extra]))
    d = df.loc[:, cols].dropna()
    d = _drop_all_zero_groups(d, y, fe)
    return d


def build_design(d: pd.DataFrame, x: list[str], fe: list[str]):
    parts = [np.ones((len(d), 1))]
    names = ["_cons"]
    if x:
        parts.append(d[x].to_numpy(float))
        names += list(x)
    for f in fe:
        dum = pd.get_dummies(d[f].astype(str), prefix=f"FE[{f}]", drop_first=True, dtype=float)
        parts.append(dum.to_numpy())
        names += list(dum.columns)
    return np.hstack(parts), names


def _independent_columns(X: np.ndarray, names: list[str], protect=()) -> np.ndarray:
    """Boolean mask of linearly independent columns (pivoted QR).

    Regressors listed in ``protect`` are placed first so that a collinear
    fixed-effect dummy is dropped instead of the regressor of interest.
    """
    order = sorted(range(len(names)), key=lambda i: (names[i] not in protect, i))
    Xo = X[:, order]
    scale = np.sqrt((Xo ** 2).sum(0))
    scale[scale == 0] = 1
    _, R, piv = linalg.qr(Xo / scale, mode="economic", pivoting=True)
    diag = np.abs(np.diag(R))
    tol = diag.max() * max(Xo.shape) * np.finfo(float).eps * 1e3
    rank = int((diag > tol).sum())
    keep_o = np.zeros(len(names), bool)
    keep_o[piv[:rank]] = True
    keep = np.zeros(len(names), bool)
    keep[np.array(order)[keep_o]] = True
    return keep


def _irls(X, y, offset, tol=1e-10, maxit=500, beta0=None):
    if beta0 is None:
        mu = (y + y.mean()) / 2
        eta = np.log(mu)
    else:
        eta = X @ beta0 + offset
        mu = np.exp(eta)
    dev_old = np.inf
    beta = beta0
    for it in range(1, maxit + 1):
        z = eta - offset + (y - mu) / mu
        w = mu
        XtW = X.T * w
        beta = linalg.solve(XtW @ X, XtW @ z, assume_a="pos")
        eta = X @ beta + offset
        eta = np.clip(eta, -700, 700)
        mu = np.exp(eta)
        with np.errstate(divide="ignore", invalid="ignore"):
            dev = 2 * np.sum(np.where(y > 0, y * np.log(y / mu), 0) - (y - mu))
        if abs(dev - dev_old) / (abs(dev) + 0.1) < tol:
            return beta, mu, True, it
        dev_old = dev
    return beta, mu, False, maxit


def ppml(df: pd.DataFrame, y: str, x: list[str], fe: list[str] = (), cluster: str = "iso3",
         offset: str | np.ndarray | None = None, sample: pd.DataFrame | None = None,
         protect: tuple = (), tol: float = 1e-10) -> PPMLResult:
    """Estimate a PPML model; returns coefficients on ``x`` (dummies are not reported)."""
    fe = list(fe)
    d = sample if sample is not None else prepare_sample(df, y, x, fe, cluster)
    X, names = build_design(d, x, fe)
    keep = _independent_columns(X, names, protect=tuple(protect) + tuple(x))
    dropped = [n for n, k in zip(names, keep) if not k and not n.startswith("FE[")]
    X, names_k = X[:, keep], [n for n, k in zip(names, keep) if k]
    yv = d[y].to_numpy(float)
    if offset is None:
        off = np.zeros(len(d))
    elif isinstance(offset, str):
        off = d[offset].to_numpy(float)
    else:
        off = np.asarray(offset, float)
    beta, mu, conv, it = _irls(X, yv, off, tol=tol)

    # clustered sandwich
    resid = yv - mu
    H = (X.T * mu) @ X
    Hinv = linalg.inv(H)
    g = pd.factorize(d[cluster])[0]
    G = g.max() + 1
    S = np.zeros((G, X.shape[1]))
    np.add.at(S, g, X * resid[:, None])
    V = Hinv @ (S.T @ S) @ Hinv * G / (G - 1)

    def ll(m):
        return np.sum(yv * np.log(np.where(m > 0, m, 1)) - m - gammaln(yv + 1))
    ll0 = ll(np.full_like(yv, yv.mean()))
    pr2 = 1 - ll(mu) / ll0 if ll0 != 0 else np.nan

    idx = [i for i, n in enumerate(names_k) if n in x]
    vn = [names_k[i] for i in idx]
    coef = pd.Series(beta[idx], index=vn).reindex(x)
    se = pd.Series(np.sqrt(np.diag(V)[idx]), index=vn).reindex(x)
    pval = pd.Series(2 * stats.norm.sf(np.abs(coef / se)), index=x)
    vc = pd.DataFrame(V[np.ix_(idx, idx)], index=vn, columns=vn).reindex(index=x, columns=x)
    return PPMLResult(coef, se, pval, vc, len(d), int(G), float(pr2), conv, it,
                      dropped, d.index, mu)


def lincom(res: PPMLResult, weights: dict) -> tuple[float, float, float]:
    """Linear combination sum_k w_k * b_k with clustered s.e. and normal p-value."""
    v = list(weights)
    w = np.array([weights[k] for k in v])
    b = float(w @ res.coef[v].to_numpy())
    se = float(np.sqrt(w @ res.vcov.loc[v, v].to_numpy() @ w))
    return b, se, float(2 * stats.norm.sf(abs(b / se)))


# --------------------------------------------------------------------------
# Bootstrap inference
# --------------------------------------------------------------------------
def pairs_cluster_bootstrap(df, y, x, fe, cluster, stat, B, rng, log=None):
    """Resample clusters with replacement; each draw re-labels duplicated clusters
    so that they receive their own fixed effect. ``stat(res)`` returns a float.
    Draws in which the statistic is not identified are returned as NaN."""
    base = prepare_sample(df, y, x, fe, cluster)
    groups = {k: v for k, v in base.groupby(cluster)}
    keys = np.array(list(groups))
    out = np.full(B, np.nan)
    for b in range(B):
        draw = rng.choice(keys, size=len(keys), replace=True)
        parts = []
        for j, k in enumerate(draw):
            p = groups[k].copy()
            p["_bid"] = j
            parts.append(p)
        bd = pd.concat(parts, ignore_index=True)
        fe_b = ["_bid" if f == cluster else f for f in fe]
        try:
            r = ppml(bd, y, x, fe_b, cluster="_bid")
            out[b] = stat(r)
        except Exception:  # singular draw (e.g. no treated origin sampled)
            out[b] = np.nan
        if log and (b + 1) % 100 == 0:
            log.info("  pairs bootstrap draw %d/%d", b + 1, B)
    return out


def _weights(kind: str, shape, rng):
    if kind == "rademacher":
        return rng.choice([-1.0, 1.0], size=shape)
    if kind == "webb":
        v = np.array([-np.sqrt(1.5), -1, -np.sqrt(0.5), np.sqrt(0.5), 1, np.sqrt(1.5)])
        return rng.choice(v, size=shape)
    raise ValueError(kind)


def wild_score_test(df, y, x, fe, cluster, test_var, null_value, B, rng, weights="rademacher",
                    sample=None):
    """Null-imposed wild cluster score bootstrap test of H0: b[test_var] = null_value.

    The restricted model is estimated with the coefficient fixed through an offset.
    Each cluster contributes c_g = a' S_g, where S_g is its score at the restricted
    estimates and a the row of the inverse Hessian for ``test_var``. The statistic
    is sum(w_g c_g) / sqrt(sum(w_g^2 c_g^2)); p = share of |t*| >= |t|.
    """
    d = sample if sample is not None else prepare_sample(df, y, x, fe, cluster)
    xr = [v for v in x if v != test_var]
    off = null_value * d[test_var].to_numpy(float)
    r = ppml(d, y, xr, fe, cluster, offset=off, sample=d)
    X, names = build_design(d, x, fe)
    keep = _independent_columns(X, names, protect=tuple(x))
    X, names = X[:, keep], [n for n, k in zip(names, keep) if k]
    j = names.index(test_var)
    mu = r.mu
    resid = d[y].to_numpy(float) - mu
    H = (X.T * mu) @ X
    a = linalg.solve(H, np.eye(len(names))[:, j], assume_a="pos")
    gi = pd.factorize(d[cluster])[0]
    c = np.zeros(gi.max() + 1)
    np.add.at(c, gi, (X @ a) * resid)
    t_obs = c.sum() / np.sqrt((c ** 2).sum())
    W = _weights(weights, (B, len(c)), rng)
    t_b = (W @ c) / np.sqrt((W ** 2) @ (c ** 2))
    return float(np.mean(np.abs(t_b) >= abs(t_obs))), float(t_obs)


def wild_score_ci(df, y, x, fe, cluster, test_var, grid, B, seed, weights="rademacher",
                  level=0.95):
    """Confidence set by inverting the wild score test over ``grid``.
    The same random weights (same seed) are used at every grid point."""
    d = prepare_sample(df, y, x, fe, cluster)
    pvals = []
    for v in grid:
        p, _ = wild_score_test(d, y, x, fe, cluster, test_var, v, B,
                               np.random.default_rng(seed), weights, sample=d)
        pvals.append(p)
    pvals = np.array(pvals)
    inside = np.asarray(grid)[pvals >= 1 - level]
    lo, hi = (inside.min(), inside.max()) if inside.size else (np.nan, np.nan)
    open_lo = inside.size and np.isclose(lo, grid[0])
    open_hi = inside.size and np.isclose(hi, grid[-1])
    return lo, hi, bool(open_lo or open_hi), pd.DataFrame({"null_value": grid, "p": pvals})
