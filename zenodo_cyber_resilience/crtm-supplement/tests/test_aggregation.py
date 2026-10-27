"""Propositions 4-7, Theorem 3 and Corollary 2."""
import numpy as np
import pytest

from crtm import aggregation as agg
from crtm import uncertainty as unc

W = np.array([0.25, 0.15, 0.25, 0.20, 0.05, 0.10])
K = [0]


def ops():
    return {"gate": lambda m: agg.hard_gate(m, W, K),
            "power": lambda m: agg.power(m, W, K, 1.0),
            "capped": lambda m: agg.capped(m, W, K, 0.5)}


def test_idempotency_table4():
    o = ops()
    assert agg.is_idempotent(lambda m: agg.additive(m, W), 6)
    assert agg.is_idempotent(o["gate"], 6)
    assert not agg.is_idempotent(o["power"], 6)
    assert agg.is_idempotent(o["capped"], 6)


def test_veto_table4():
    o = ops()
    assert not agg.has_veto(lambda m: agg.additive(m, W), 6, 0)
    for f in o.values():
        assert agg.has_veto(f, 6, 0)


def test_continuity_corollary2():
    m = np.array([0.0, 1, 0.9, 0.87, 0.44, 0.8])
    o = ops()
    assert agg.max_jump_at(o["gate"], m, 0) > 0.5            # Prop. 4(c): jump = S_w(m)
    assert agg.max_jump_at(o["power"], m, 0) < 1e-6
    assert agg.max_jump_at(o["capped"], m, 0) < 1e-6


def test_theorem3_lipschitz_and_limits():
    rng = np.random.default_rng(3)
    for th in (0.25, 0.5, 1.0):
        L = max(1, 1 / th)
        for _ in range(500):
            a, b = rng.random(6), rng.random(6)
            assert abs(agg.capped(a, W, K, th) - agg.capped(b, W, K, th)) <= L * np.abs(a - b).max() + 1e-12
    m = rng.random(6)
    # (c) capped <= gate; (d) convergence to the gate for small theta
    assert agg.capped(m, W, K, 0.5) <= agg.hard_gate(m, W, K) + 1e-12
    assert agg.capped(m, W, K, min(m[0], 1.0)) == pytest.approx(agg.hard_gate(m, W, K))


def test_prop5d_nonuniform_convergence():
    for g in (0.1, 0.5, 1, 2):
        m = np.array([1e-300, 1, 1, 1, 1, 1])
        assert agg.hard_gate(m, W, K) - agg.power(m, W, K, g) >= 1 - W[0] - 1e-3


def test_prop6_enclosure_attained():
    rng = np.random.default_rng(4)
    w = np.full(10, 0.1)
    m = rng.random(10)
    m[8] = np.nan
    enc = agg.missing_enclosure(m, w, [2])
    for fill in (0.0, 1.0):
        full = np.where(np.isnan(m), fill, m)
        s = agg.hard_gate(full, w, [2])
        assert s == pytest.approx(enc["lower"] if fill == 0 else enc["upper"])
    for _ in range(200):
        full = np.where(np.isnan(m), rng.random(), m)
        s = agg.hard_gate(full, w, [2])
        assert enc["lower"] - 1e-12 <= s <= enc["upper"] + 1e-12
        assert abs(s - enc["mu_O"]) <= enc["max_deviation"] + 1e-12


def test_missing_core_not_computed():
    m = np.array([np.nan, 0.5, 0.5])
    assert agg.missing_enclosure(m, np.ones(3) / 3, [0])["status"].startswith("not computed")


def test_prop7_dirichlet_moments():
    m = np.array([1, 1, 0.9118, 0.8667, 0.4444, 0.8])
    for a in (0.5, 1, 4):
        mean, sd = unc.dirichlet_moments(m, a)
        s = unc.sample_scores(m, a, n=200_000, seed=7)
        assert s.mean() == pytest.approx(mean, abs=1e-3)
        assert s.std() == pytest.approx(sd, abs=1e-3)
