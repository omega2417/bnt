"""Equations (5)-(14), each checked against a hand-computed case."""

import numpy as np
import pytest

from alp import metrics


def test_visible_latency_equations():
    t_send = np.array([0, 0], dtype=np.int64)
    t_read = np.array([[10_000_000, 40_000_000],     # R1: 10 ms, 40 ms
                       [25_000_000, 30_000_000]])    # R2: 25 ms, 30 ms
    assert metrics.t_visible_first(t_read, t_send).tolist() == [10.0, 30.0]
    assert metrics.t_visible_all(t_read, t_send).tolist() == [25.0, 40.0]
    assert metrics.t_convergence(t_read).tolist() == [15.0, 10.0]


def test_quantile_returns_an_observed_value():
    x = [1.0, 2.0, 3.0, 100.0]
    assert metrics.empirical_quantile(x, 0.5) in x
    assert metrics.empirical_quantile(x, 0.99) == 100.0
    assert np.isnan(metrics.empirical_quantile([], 0.5))


def test_goodput_availability_consistency():
    assert metrics.goodput(3000, 300) == pytest.approx(10.0)
    assert metrics.availability(995, 1000) == pytest.approx(99.5)
    assert metrics.consistency(990, 995) == pytest.approx(99.497, abs=1e-3)
    assert np.isnan(metrics.availability(0, 0))


def test_improvement_is_positive_when_the_profile_is_faster():
    assert metrics.quantile_improvement_pct(1000, 750) == pytest.approx(25.0)
    assert metrics.quantile_improvement_pct(1000, 1250) == pytest.approx(-25.0)


def test_observed_block_interval_is_the_median_difference():
    assert metrics.observed_block_interval([0, 250, 500, 760, 1000]) == 250.0
    assert np.isnan(metrics.observed_block_interval([5.0]))


def test_theil_sen_recovers_a_known_slope():
    y = 3.0 * np.arange(40) + 7.0
    assert metrics.theil_sen_slope(y) == pytest.approx(3.0)


def test_theil_sen_ci_separates_growth_from_noise():
    rng = np.random.default_rng(0)
    growing = 2.0 * np.arange(60) + rng.normal(0, 1, 60)
    flat = rng.normal(0, 1, 60)
    assert metrics.theil_sen_slope_ci(growing)["ci_low"] > 0
    ci = metrics.theil_sen_slope_ci(flat)
    assert ci["ci_low"] < 0 < ci["ci_high"]


def test_half_split_drift_detects_a_degrading_tail():
    stable = np.full(200, 100.0)
    degrading = np.concatenate([np.full(100, 100.0), np.full(100, 200.0)])
    assert metrics.half_split_drift_pct(stable) == pytest.approx(0.0)
    assert metrics.half_split_drift_pct(degrading) == pytest.approx(100.0)


def test_latex_escaping_protects_percent_and_underscore():
    from alp.tables import tex_escape

    assert tex_escape("95 % at 25 tx/s") == r"95 \% at 25 tx/s"
    assert tex_escape("load_tps") == r"load\_tps"
    assert tex_escape("a & b") == r"a \& b"
