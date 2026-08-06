"""Unit tests for the mathematical building blocks."""
import numpy as np

from ust_fuse.geometry import cart_to_spherical, spherical_to_cart, spherical_measurement_covariance
from ust_fuse.tracking.kalman import KalmanCV
from ust_fuse.metrics.stats import cohens_d, paired_comparison, bootstrap_ci
from ust_fuse.rng import RNGHub


def test_spherical_roundtrip():
    p = np.array([120.0, -80.0, 45.0])
    r, az, el = cart_to_spherical(p)
    q = spherical_to_cart(r, az, el)
    assert np.allclose(p, q, atol=1e-6)


def test_covariance_psd_and_elongated_for_bearing():
    # bearing-only: huge sigma_range => strongly elongated along LOS
    R = spherical_measurement_covariance(800, 0.3, 0.1, sigma_r=1500, sigma_az=0.003, sigma_el=0.003)
    w = np.linalg.eigvalsh(R)
    assert np.all(w > 0)                     # positive definite
    assert w.max() / w.min() > 100           # needle-shaped


def test_kalman_predict_update_reduces_covariance():
    kf = KalmanCV(np.zeros(6), np.eye(6) * 100.0, q=1.0)
    kf.predict(0.1)
    tr_before = np.trace(kf.cov[:3, :3])
    kf.update(np.array([1.0, 1.0, 1.0]), np.eye(3) * 1.0)
    tr_after = np.trace(kf.cov[:3, :3])
    assert tr_after < tr_before


def test_kalman_converges_to_measurement():
    kf = KalmanCV(np.zeros(6), np.eye(6) * 100.0, q=0.01)
    z = np.array([10.0, -5.0, 3.0])
    for _ in range(50):
        kf.predict(0.1)
        kf.update(z, np.eye(3) * 0.5)
    assert np.linalg.norm(kf.position() - z) < 1.0


def test_cohens_d_sign():
    # non-constant paired differences so the paired SD is well-defined
    a = np.array([2.0, 3.5, 4.0, 5.5])
    b = np.array([1.5, 2.0, 3.5, 3.0])
    d = cohens_d(a, b, paired=True)
    assert d > 0


def test_paired_comparison_picks_winner():
    rng = np.random.default_rng(0)
    a = rng.normal(10, 1, 30)          # reference RMSE
    b = a - 2.0                         # ust_fuse consistently 2 m better
    pr = paired_comparison(a, b, metric="rmse", lower_is_better=True)
    assert pr.better == "B"           # ust_fuse (b) has lower RMSE
    assert pr.mean_diff > 0           # mean_diff = mean(a) - mean(b) ≈ +2
    assert pr.ci_low > 0              # CI excludes zero


def test_bootstrap_ci_contains_mean():
    x = np.arange(100.0)
    lo, hi = bootstrap_ci(x, n_boot=1000)
    assert lo < x.mean() < hi


def test_rng_streams_independent_and_reproducible():
    h1 = RNGHub(42)
    h2 = RNGHub(42)
    assert np.allclose(h1.stream("a").random(5), h2.stream("a").random(5))
    # different stream names => different draws
    h3 = RNGHub(42)
    assert not np.allclose(h3.stream("a").random(5), h3.stream("b").random(5))
