"""Shared pytest fixtures."""

from __future__ import annotations

import warnings

import pytest

warnings.filterwarnings("ignore")


@pytest.fixture(scope="session")
def tiny_scenario():
    from aegis_uav.schemas import ScenarioConfig

    return ScenarioConfig(name="test", fleet_size=4, mission_duration_s=60, export_period_s=1.0)


@pytest.fixture(scope="session")
def ada_cfg():
    from aegis_uav.schemas import ADAConfig

    return ADAConfig(window_length_s=2.0, window_stride_s=2.0, hidden_sizes=[16],
                     latent_dim=6, max_epochs=15, max_train_windows=800)
