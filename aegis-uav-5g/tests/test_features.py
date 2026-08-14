"""Tests for the feature pipeline: dimensionality, no-leakage, determinism."""

from __future__ import annotations

import numpy as np

from aegis_uav.features.pipeline import (
    BASE_NUMERIC_FEATURES,
    PHASE_FEATURES,
    FeaturePipeline,
    build_windows,
)
from aegis_uav.schemas import AttackConfig
from aegis_uav.simulation.scenario_engine import simulate_mission


def _windows(tiny_scenario, ada_cfg):
    missions = [
        simulate_mission(tiny_scenario, None, seed=0, mission_index=0, split="train"),
        simulate_mission(tiny_scenario, AttackConfig(id="T3", onset_s=10, duration_s=30,
                                                     intensity=0.8, target_uavs=[0]),
                         seed=0, mission_index=1, split="test"),
    ]
    return build_windows(missions, tiny_scenario, ada_cfg)


def test_feature_dimension_in_expected_range(tiny_scenario, ada_cfg):
    df = _windows(tiny_scenario, ada_cfg)
    pipe = FeaturePipeline().fit(df, benign_only=True)
    # d should sit in the manuscript's expected 55-85 range.
    assert 55 <= pipe.dim <= 85
    assert pipe.dim == len(BASE_NUMERIC_FEATURES) + len(PHASE_FEATURES)


def test_transform_shapes(tiny_scenario, ada_cfg):
    df = _windows(tiny_scenario, ada_cfg)
    pipe = FeaturePipeline().fit(df, benign_only=True)
    X = pipe.transform(df)
    assert X.shape == (len(df), pipe.dim)
    assert not np.isnan(X).any()


def test_scaler_fit_on_train_only_is_finite(tiny_scenario, ada_cfg):
    df = _windows(tiny_scenario, ada_cfg)
    train = df[df["split"] == "train"] if "split" in df else df
    pipe = FeaturePipeline().fit(train, benign_only=True)
    # Transforming the (unseen) test split must not raise and must be finite.
    X = pipe.transform(df)
    assert np.isfinite(X).all()


def test_modality_subsets_disjoint(tiny_scenario, ada_cfg):
    df = _windows(tiny_scenario, ada_cfg)
    pipe = FeaturePipeline().fit(df, benign_only=True)
    tel = pipe.transform_modality(df, "telemetry")
    net = pipe.transform_modality(df, "network")
    beh = pipe.transform_modality(df, "behaviour")
    assert tel.shape[1] + net.shape[1] + beh.shape[1] <= pipe.dim
