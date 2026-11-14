"""Regression tests: the re-implemented link model must reproduce the numbers printed in the article."""
import numpy as np
import pytest
from satqkd_sentinel.linkmodel import Link, slant_range, pass_profile, H_GEO, R_E, R_GEO
from satqkd_sentinel.geo import (coverage_angle, coverage_stats, isl_chord, isl_max_angle, central_angle, elevation,
                            range_from_angle, contact_plan)

lk = Link()


def test_divergence_and_background():
    assert lk.theta_w * 1e6 == pytest.approx(14.8, abs=0.05)        # Table 2
    assert lk.y0() == pytest.approx(5.0e-7, rel=0.02)               # Table 2


@pytest.mark.parametrize("elev, loss, rate", [(90, 34.8, 23.8), (20, 43.2, 2.8)])
def test_loss_and_rate(elev, loss, rate):                          # Section 4.2
    e = np.radians(elev); L = slant_range(e, 500e3)
    assert lk.loss_db(L, e) == pytest.approx(loss, abs=0.05)
    assert lk.rate(lk.eta(L, e))[0] / 1e3 == pytest.approx(rate, abs=0.05)


def test_loss_limit_and_pointing():
    assert lk.loss_limit_db() == pytest.approx(51.4, abs=0.05)
    assert -10 * np.log10(lk.with_(sigma_j=10e-6).eta_pt()) == pytest.approx(4.5, abs=0.05)
    assert -10 * np.log10(lk.with_(sigma_j=20e-6).eta_pt()) == pytest.approx(9.2, abs=0.05)


@pytest.mark.parametrize("eps_max, k_inf, r_max", [(25, 0.62, 4.3), (30, 0.99, 6.0), (40, 1.67, 9.8), (60, 2.77, 17.8), (90, 3.45, 23.8)])
def test_asymptotic_key_per_pass(eps_max, k_inf, r_max):           # Table 5 of the revised article
    t, el, L, az = pass_profile(np.radians(eps_max))
    r = lk.rate(lk.eta(L, el))[0]
    assert r.sum() / 1e6 == pytest.approx(k_inf, abs=0.006)
    assert r.max() / 1e3 == pytest.approx(r_max, abs=0.05)


def test_geo_geometry():                                           # Section 4.9, Table 7
    assert np.degrees(coverage_angle(np.radians(20))) == pytest.approx(61.8, abs=0.05)
    assert isl_chord(4) / 1e3 == pytest.approx(59619, abs=1)
    assert np.degrees(isl_max_angle(R_E + 500e3, R_GEO)) == pytest.approx(100.8, abs=0.05)
    psi = central_angle(np.radians(48.46), np.radians(35.05), np.radians(35.0))
    assert np.degrees(elevation(psi)) == pytest.approx(34.4, abs=0.05)
    assert range_from_angle(psi) / 1e3 == pytest.approx(38231, abs=1)


@pytest.mark.parametrize("n, s1, s2", [(3, 78.5, 0.7), (4, 84.6, 21.1), (6, 86.8, 70.2)])
def test_coverage(n, s1, s2):
    c = coverage_stats(n)
    assert 100 * c["share1"] == pytest.approx(s1, abs=0.05)
    assert 100 * c["share2"] == pytest.approx(s2, abs=0.05)


def test_geo_link_budget():
    psi = central_angle(np.radians(48.46), np.radians(35.05), np.radians(35.0))
    assert lk.loss_db(range_from_angle(psi), elevation(psi)) == pytest.approx(72.8, abs=0.05)
    big = lk.with_(d_tx=1.0, d_rx=1.5, sigma_j=0.2e-6)
    assert big.rate(big.eta(range_from_angle(psi), elevation(psi)))[0] == pytest.approx(1160, rel=0.01)
    assert big.loss_limit_db() == pytest.approx(48.3, abs=0.05)


def test_contact_plan_short():
    cp = contact_plan(4, [(48.46, 35.05)], hours=48, dt=20.0)
    assert (cp["geo"].sum(0) >= 2).all()                           # two backbone nodes always in view
    assert cp["site"][0].mean() < 0.02                             # a ground station sees the relay rarely
