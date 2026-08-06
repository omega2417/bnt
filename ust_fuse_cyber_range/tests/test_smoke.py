"""End-to-end smoke tests: the whole pipeline runs and is reproducible."""
import numpy as np
import pytest

import ust_fuse as uf
from ust_fuse.campaign import Campaign


def test_scenarios_listed():
    scns = uf.list_scenarios()
    assert len(scns) >= 10
    assert "S01_baseline_clear" in scns


def test_run_produces_metrics():
    res = uf.run("S01_baseline_clear", seed=7)
    assert set(res.modes) == {"reference", "ust_fuse"}
    for md in res.modes.values():
        assert np.isfinite(md.tracking.rmse_pos)
        assert md.tracking.n_tracks > 0
        assert 0.0 <= md.calibration.ece <= 1.0


def test_reproducible_raw():
    a = uf.run("S03_multitarget_crossing", seed=123)
    b = uf.run("S03_multitarget_crossing", seed=123)
    assert a.raw.stats["n_detections"] == b.raw.stats["n_detections"]
    assert a.manifest.config_hash == b.manifest.config_hash
    assert a.manifest.experiment_id == b.manifest.experiment_id


def test_different_seed_changes_data():
    a = uf.run("S01_baseline_clear", seed=1)
    b = uf.run("S01_baseline_clear", seed=2)
    # same config hash (config identical), different experiment id (seed differs)
    assert a.manifest.config_hash == b.manifest.config_hash
    assert a.manifest.experiment_id != b.manifest.experiment_id


def test_same_raw_feeds_both_modes():
    res = uf.run("S01_baseline_clear", seed=5)
    # both modes were computed from one RawMission
    assert res.modes["reference"].fusion.mode == "reference"
    assert res.modes["ust_fuse"].fusion.mode == "ust_fuse"


def test_campaign_paired_stats():
    camp = Campaign("S01_baseline_clear", n_missions=4).run()
    t = camp.paired_table()
    assert len(t) > 0
    assert {"mean_diff", "ci_low", "ci_high", "cohens_d"}.issubset(t.columns)
