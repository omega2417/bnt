"""Mahalanobis anomaly scoring with chi-square calibration - Eq. (6), (7).

Correction relative to Man-V3: the detection threshold is the (1 - fpr) quantile of
chi^2 with p degrees of freedom, where p is the ACTUAL feature dimension. The
manuscript's implied p=2 shortcut is not used anywhere in this implementation.
"""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
from scipy import stats

__all__ = ["BaselineModel", "fit_baseline", "anomaly_likelihood", "anomaly_likelihood_chi2"]


@dataclass
class BaselineModel:
    mu: np.ndarray
    sigma: np.ndarray
    sigma_inv: np.ndarray
    p: int
    shrinkage: float
    n_baseline: int
    threshold_fpr: float
    d2_threshold: float = field(default=float("nan"))

    def d2(self, z: np.ndarray) -> np.ndarray:
        """Squared Mahalanobis distance, Eq. (6). Accepts (p,) or (n,p)."""
        z = np.atleast_2d(np.asarray(z, dtype=float))
        delta = z - self.mu
        return np.einsum("ij,jk,ik->i", delta, self.sigma_inv, delta)

    def is_anomalous(self, z: np.ndarray) -> np.ndarray:
        return self.d2(z) > self.d2_threshold


def fit_baseline(
    z_baseline: np.ndarray,
    threshold_fpr: float = 0.01,
    shrinkage: float = 0.10,
) -> BaselineModel:
    """Estimate mu and Sigma on the permitted baseline window only.

    Ledoit-Wolf-style ridge shrinkage towards a scaled identity keeps Sigma
    invertible for short baselines; the coefficient is frozen in
    protocol/preregistration.yaml and never re-tuned on evaluation data.
    """
    z_baseline = np.asarray(z_baseline, dtype=float)
    n, p = z_baseline.shape
    if n <= p:
        raise ValueError(f"baseline window n={n} must exceed dimension p={p}")
    mu = z_baseline.mean(axis=0)
    sd = z_baseline.std(axis=0, ddof=1)
    if np.any(sd <= 0):
        raise ValueError("degenerate baseline feature with zero variance")
    # Shrinkage is applied on the CORRELATION scale. Shrinking the raw covariance
    # towards trace(Sigma)/p * I is unusable for telemetry whose features differ by
    # orders of magnitude in unit (here bytes/s against a dimensionless gap rate):
    # the identity target is then dominated by the largest-variance feature and
    # inflates every other diagonal entry, collapsing E[d^2] far below p. Measured
    # on the pilot, the raw-scale variant gave E[d^2] = 1.54 instead of 9.
    corr = np.corrcoef(z_baseline, rowvar=False)
    corr = (1.0 - shrinkage) * corr + shrinkage * np.eye(p)
    sigma = corr * np.outer(sd, sd)
    sigma_inv = np.linalg.inv(sigma)
    d2_thr = float(stats.chi2.ppf(1.0 - threshold_fpr, df=p))
    return BaselineModel(
        mu=mu, sigma=sigma, sigma_inv=sigma_inv, p=p, shrinkage=shrinkage,
        n_baseline=n, threshold_fpr=threshold_fpr, d2_threshold=d2_thr,
    )


def anomaly_likelihood(d2: np.ndarray) -> np.ndarray:
    """Eq. (7) exactly as printed in Man-V3: a_i(t) = 1 - exp(-d^2/2).

    RETAINED ONLY FOR REPRODUCING THE MANUSCRIPT. Do not use as a score.
    Under the null hypothesis d^2 ~ chi^2_p, so E[a] = 1 - (1/2)^(p/2)... and for
    p = 9 the mapping returns a >= 0.989 for a *median* healthy sample. The
    transform is only graded for p <= 3; at the p = 9 actually used it saturates
    and destroys every distinction the risk model in Eq. (8) depends on. See
    docs/manuscript_corrections.md, correction C3.
    """
    return 1.0 - np.exp(-0.5 * np.asarray(d2, dtype=float))


def anomaly_likelihood_chi2(d2: np.ndarray, p: int) -> np.ndarray:
    """Dimension-aware replacement for Eq. (7): a_i(t) = F_{chi^2_p}(d_i^2(t)).

    This is the complement of the exact per-sample p-value. Under the null it is
    uniform on [0,1] for every p, so the score stays graded and comparable across
    assets of different feature dimensionality, and it tends to 1 under attack.
    """
    return np.asarray(stats.chi2.cdf(np.asarray(d2, dtype=float), df=p), dtype=float)
