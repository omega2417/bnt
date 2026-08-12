"""Cascade-threshold Rc: subcritical/supercritical classification and Theorem 4."""
import numpy as np

from src import cascade_threshold, ScenarioParams, critical_delay_scalar


def test_S1_subcritical(graph):
    tr = cascade_threshold(graph, ScenarioParams(0.93, 0.55, 0.8, 0.8))
    assert tr.Rc < 1.0
    assert abs(tr.Rc - 0.82) < 0.02
    assert "certified" in tr.regime


def test_S2_S3_supercritical_and_equal(graph):
    tr2 = cascade_threshold(graph, ScenarioParams(1.60, 0.75, 0.8, 0.8))
    tr3 = cascade_threshold(graph, ScenarioParams(1.60, 0.38, 0.8, 0.8))
    assert tr2.Rc > 1.0 and tr3.Rc > 1.0
    # Rc is xi-independent (structural) -> S2 and S3 share the same Rc
    assert np.isclose(tr2.Rc, tr3.Rc, atol=1e-6)


def test_Rc_monotone_in_coupling(graph):
    r_lo = cascade_threshold(graph, ScenarioParams(0.5, 0.55, 0.8, 0.8)).Rc
    r_hi = cascade_threshold(graph, ScenarioParams(2.0, 0.55, 0.8, 0.8)).Rc
    assert r_hi > r_lo


def test_margin(graph):
    tr = cascade_threshold(graph, ScenarioParams(0.93, 0.55, 0.8, 0.8))
    assert np.isclose(tr.margin, 1.0 - tr.Rc)


def test_critical_delay_monotone_decreasing():
    taus = [critical_delay_scalar(a)[0] for a in [0.6, 0.7, 0.8, 0.9, 1.0]]
    assert all(taus[i] > taus[i + 1] for i in range(len(taus) - 1))
    assert abs(taus[0] - 3.0) < 0.05      # tau*(0.6) ~= 3.00
    assert abs(taus[-1] - 1.43) < 0.05    # tau*(1.0) ~= 1.43
