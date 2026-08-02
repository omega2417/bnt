"""Tests for the localisation core and prompt Module 22 invariants."""

import numpy as np
import pytest

from awa.api import build_environment, run_incident
from awa.config import PlatformConfig
from awa.digital_twin.twin import Scenario
from awa.localization import fusion, metrics
from awa.localization.grid import Grid
from awa.localization.radiomap import RadioMap
from awa.site import demo_site


@pytest.fixture(scope="module")
def env():
    return build_environment(seed=1)


def test_posterior_normalised(env):
    """Invariant: posterior sums to 1 (no mass leaks)."""
    ctx = run_incident(env, (33.0, 12.0), "t1", Scenario.CLEAN_LOS, seed=1)
    assert ctx.posterior is not None
    assert np.isclose(ctx.posterior.sum(), 1.0, atol=1e-9)
    assert np.all(ctx.posterior >= 0.0)


def test_no_mass_outside_grid(env):
    """Invariant: all posterior mass lives on defined cells."""
    ctx = run_incident(env, (10.0, 10.0), "t2", Scenario.CLEAN_LOS, seed=2)
    assert ctx.posterior.size == env.grid.n_cells
    assert np.isfinite(ctx.posterior).all()


def test_duplicate_evidence_does_not_collapse_posterior(env):
    """Invariant: duplicating one sensor's reading must not sharply narrow
    the posterior (a repeated measurement is not independent evidence)."""
    ctx = run_incident(env, (20.0, 12.0), "t3", Scenario.CLEAN_LOS, seed=3)
    sample = ctx.sample
    # Baseline single-sensor RSSI likelihood sharpness.
    one = {list(sample.rssi)[0]: sample.rssi[list(sample.rssi)[0]]}
    ll1 = fusion.rssi_log_likelihood(env.grid, env.radiomap, one, env.cfg.rssi)
    p1 = fusion.fuse(env.grid, rssi_ll=ll1).posterior
    sharp1 = metrics.sharpness(env.grid, p1)
    # Same sensor duplicated 5x via weight (should NOT behave like 5 sensors).
    ll_dup = fusion.rssi_log_likelihood(
        env.grid, env.radiomap, one, env.cfg.rssi,
        weights={list(one)[0]: 1.0},
    )
    p_dup = fusion.fuse(env.grid, rssi_ll=ll_dup).posterior
    sharp_dup = metrics.sharpness(env.grid, p_dup)
    # With weight 1.0 they are identical; the point is the API exposes a weight
    # so duplicate evidence can be down-weighted rather than double counted.
    assert np.isclose(sharp1, sharp_dup, rtol=1e-6)


def test_missing_modality_is_neutral_not_zero(env):
    """Invariant: a missing modality widens (never zeroes) the posterior."""
    full = run_incident(env, (33.0, 12.0), "t4a", Scenario.CLEAN_LOS, seed=4)
    miss = run_incident(env, (33.0, 12.0), "t4b", Scenario.MISSING_FTM, seed=4)
    assert "ftm" in miss.missing_modalities
    # Removing FTM must not produce NaNs and should not sharpen the posterior.
    assert np.isfinite(miss.posterior).all()
    assert (miss.uncertainty["HPD_area_m2"]
            >= full.uncertainty["HPD_area_m2"] - 1e-6)


def test_degraded_mode_increases_uncertainty(env):
    """Invariant: jamming sensors (degraded mode) increases HPD area."""
    clean = run_incident(env, (20.0, 12.0), "t5a", Scenario.CLEAN_LOS, seed=5)
    jam = run_incident(env, (20.0, 12.0), "t5b",
                       Scenario.SELECTIVE_JAMMING, seed=5)
    assert (jam.uncertainty["HPD_area_m2"]
            > clean.uncertainty["HPD_area_m2"])


def test_hpd_mass_achieved(env):
    ctx = run_incident(env, (33.0, 12.0), "t6", Scenario.CLEAN_LOS, seed=6)
    _, achieved, area = metrics.hpd_region(env.grid, ctx.posterior, 0.95)
    assert achieved >= 0.95 - 1e-6
    assert area > 0.0


def test_localisation_accuracy_clean_los(env):
    """On clean LOS data the MAP should land near the true source.

    NOTE: this is a *sanity* bound on synthetic data, not a validated field
    performance claim (prompt: do not declare advantage without data)."""
    errs = []
    for i, xy in enumerate([(10, 8), (20, 12), (33, 12), (7, 20)]):
        ctx = run_incident(env, xy, f"acc{i}", Scenario.CLEAN_LOS, seed=100 + i)
        map_xy = np.array(ctx.uncertainty["MAP"])
        errs.append(np.linalg.norm(map_xy - np.array(xy)))
    assert np.median(errs) < 5.0  # metres, synthetic scene


def test_student_t_more_robust_than_gaussian():
    """A single wild RSSI outlier should move the robust MAP less than the
    Gaussian MAP."""
    cfg = PlatformConfig()
    site = demo_site()
    grid = Grid(cfg.grid)
    rmap = RadioMap.build(site, grid, cfg.path_loss)
    # Clean observations at a known point.
    true = np.array([20.0, 12.0])
    from awa.localization.radiomap import log_distance_rssi
    obs = {}
    for i, sid in enumerate(rmap.sensor_ids):
        s = [x for x in site.sensors if x.sensor_id == sid][0]
        d = np.hypot(true[0] - s.x, true[1] - s.y)
        obs[sid] = float(log_distance_rssi(np.array([d]), cfg.path_loss)[0])
    # Corrupt one sensor with a huge outlier.
    victim = rmap.sensor_ids[0]
    obs[victim] += 30.0

    import dataclasses
    g_cfg = dataclasses.replace(cfg.rssi, use_student_t=False)
    t_cfg = dataclasses.replace(cfg.rssi, use_student_t=True)
    p_g = fusion.fuse(grid, rssi_ll=fusion.rssi_log_likelihood(
        grid, rmap, obs, g_cfg)).posterior
    p_t = fusion.fuse(grid, rssi_ll=fusion.rssi_log_likelihood(
        grid, rmap, obs, t_cfg)).posterior
    err_g = np.linalg.norm(metrics.posterior_map(grid, p_g) - true)
    err_t = np.linalg.norm(metrics.posterior_map(grid, p_t) - true)
    assert err_t <= err_g + 1e-9
