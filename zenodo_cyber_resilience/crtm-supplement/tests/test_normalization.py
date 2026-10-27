"""Theorems 1-2, Corollary 1 and Proposition 3."""
import numpy as np
import pytest

import crtm
from crtm.normalization import ClassTable, ClassTableError, grid_check


@pytest.fixture(scope="module")
def actions():
    return crtm.load_metrics()


def test_level_map_bands():
    assert crtm.level(0.0) == 1 and crtm.level(0.1999) == 1
    assert crtm.level(0.2) == 2 and crtm.level(0.7) == 4
    assert crtm.level(0.9) == 5 and crtm.level(1.0) == 5


def test_condition_8_rejected():
    with pytest.raises(ClassTableError):
        ClassTable((0, 1, 1, 2, 3, 4))


def test_paper_encoding_relevance_time():
    t = ClassTable((180, 179, 90, 30, 10, 0))
    assert t.sigma == -1
    assert t.tabulated_level(25) == 4          # 11-30 min: above average
    assert t.linear(25) == pytest.approx(0.9118, abs=1e-4)
    assert crtm.level(t.linear(25)) == 5      # ... but the linear map says "high"
    assert t.anchored(25) == pytest.approx(0.75)


def test_theorem2a_anchored_consistent_everywhere(actions):
    for a in actions.values():
        for mt in a.metrics:
            assert grid_check(mt.table, "anchored")["violations"] == 0


def test_corollary1_linear_never_consistent(actions):
    for a in actions.values():
        for mt in a.metrics:
            t = mt.table
            c = t.corollary1_interval()
            assert c["length"] > 0
            u = np.linspace(*c["u_interval"], 50)[1:-1]   # interior (avoid rounding at 0.9)
            x = t.sigma * u
            assert np.all(crtm.level(t.linear(x)) == 5)
            assert np.all(t.tabulated_level(x) == 4)


def test_theorem1_even_spacing_gives_consistent_affine_map():
    # anchors spaced proportionally to y: slopes 100 per unit score
    t = ClassTable((0, 20, 40, 70, 90, 100))
    ok, a, b = t.affine_consistent()
    assert ok and a == pytest.approx(0.01) and b == pytest.approx(0.0)
    xs = np.linspace(-10, 110, 5001)
    assert np.all(crtm.level(t.anchored(xs)) == t.tabulated_level(xs))
    # Theorem 2(c): nu coincides with the affine map
    assert np.allclose(t.anchored(xs), np.clip(a * xs + b, 0, 1))


def test_theorem2d_band_width_bound(actions):
    rng = np.random.default_rng(1)
    for a in actions.values():
        for mt in a.metrics:
            t = mt.table
            xs = rng.uniform(min(t.xi), max(t.xi), 200)
            r = t.tabulated_level(xs)
            # any consistent normalization: a random point inside the same band
            lo, hi = crtm.Y[r - 1], crtm.Y[r]
            other = lo + rng.random(xs.size) * (hi - lo) * 0.999
            assert np.all(np.abs(other - t.anchored(xs)) <= (hi - lo) + 1e-12)
            assert np.all(np.abs(other - t.anchored(xs)) <= 0.3 + 1e-12)


def test_proposition3_level_bounds():
    rng = np.random.default_rng(2)
    for _ in range(2000):
        q = rng.integers(2, 8)
        m = rng.random(q)
        w = rng.dirichlet(np.ones(q))
        lv = crtm.level(m)
        assert lv.min() <= crtm.level(w @ m) <= lv.max()


def test_degenerate_critical_anchor_is_consistent():
    t = ClassTable((5, 5, 10, 20, 30, 40))
    xs = np.concatenate([np.linspace(0, 45, 9001), t.anchors_with_neighbours()])
    assert np.all(crtm.level(t.anchored(xs)) == t.tabulated_level(xs))
