"""Anomaly scoring (manuscript Eq. 6-7).

The manuscript maps the squared Mahalanobis distance through
``a = 1 - exp(-d^2 / 2)``, which is a bounded monotone score but is *not* the
probability of anomaly for a p-dimensional feature vector.  Under the Gaussian
assumption stated in Section 2.4 the calibrated quantity is the chi-square CDF
with p degrees of freedom.  Both mappings are implemented so that the printed
manuscript value and the corrected value can be reported side by side.
"""
from __future__ import annotations

import numpy as np
from scipy import stats as _sps

__all__ = [
    "BaselineModel",
    "mahalanobis_sq",
    "score_legacy",
    "score_chi2",
    "empirical_calibration",
    "gaussian_fit_check",
]


class BaselineModel:
    """Normal-phase mean and regularised covariance for one asset.

    Parameters
    ----------
    shrinkage
        Ridge applied as ``Sigma + shrinkage * tr(Sigma)/p * I``.  A strictly
        positive value is required whenever ``n_samples`` is not much larger than
        the feature dimension, otherwise ``Sigma`` is ill-conditioned and the
        distances are not comparable across assets.
    """

    def __init__(self, X: np.ndarray, shrinkage: float = 0.05):
        X = np.asarray(X, dtype=float)
        if X.ndim != 2:
            raise ValueError("X must be (n_samples, n_features)")
        self.n_samples, self.p = X.shape
        if self.n_samples <= self.p:
            raise ValueError(
                f"n_samples ({self.n_samples}) must exceed feature dimension ({self.p})"
            )
        self.mu = X.mean(axis=0)
        cov = np.atleast_2d(np.cov(X, rowvar=False))
        self.shrinkage = float(shrinkage)
        self.sigma = cov + self.shrinkage * np.trace(cov) / self.p * np.eye(self.p)
        self.sigma_inv = np.linalg.inv(self.sigma)
        self.condition_number = float(np.linalg.cond(self.sigma))

    def distance_sq(self, z: np.ndarray):
        return mahalanobis_sq(z, self.mu, self.sigma_inv)


def mahalanobis_sq(z, mu, sigma_inv):
    """d_i^2(t) = (z - mu)^T Sigma^-1 (z - mu), Eq. (6)."""
    z = np.atleast_2d(np.asarray(z, dtype=float))
    delta = z - np.asarray(mu, dtype=float)
    d2 = np.einsum("ij,jk,ik->i", delta, sigma_inv, delta)
    return d2 if d2.size > 1 else float(d2[0])


def score_legacy(d2):
    """Manuscript Eq. (7) as printed: a = 1 - exp(-d^2/2). A monotone score only."""
    return 1.0 - np.exp(-0.5 * np.asarray(d2, dtype=float))


def score_chi2(d2, p: int):
    """Corrected calibration a = F_{chi2_p}(d^2); a probability under Gaussianity."""
    return _sps.chi2.cdf(np.asarray(d2, dtype=float), df=p)


def empirical_calibration(d2_calibration, d2_test):
    """Distribution-free alternative: empirical CDF of the calibration distances.

    Use when the Gaussian assumption fails the goodness-of-fit check; the result
    is a calibrated tail probability rather than an unnormalised score.
    """
    ref = np.sort(np.asarray(d2_calibration, dtype=float))
    return np.searchsorted(ref, np.asarray(d2_test, dtype=float), side="right") / ref.size


def gaussian_fit_check(d2, p: int):
    """Kolmogorov-Smirnov test of d^2 against chi2_p on the calibration set.

    Reported in the manuscript so the Gaussian assumption behind Eq. (7) is
    verified rather than assumed.
    """
    d2 = np.asarray(d2, dtype=float)
    ks = _sps.kstest(d2, "chi2", args=(p,))
    return {"n": int(d2.size), "df": p, "ks_statistic": float(ks.statistic),
            "p_value": float(ks.pvalue)}
