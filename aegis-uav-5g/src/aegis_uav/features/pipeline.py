"""Feature pipeline: assemble windows, fit preprocessors on the train split only,
and produce leakage-free numeric feature matrices.

The fitted scaler + column order are serialised so evaluation is reproducible and
the test split is transformed with statistics computed on train data alone.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.preprocessing import StandardScaler

from ..schemas import ADAConfig, ScenarioConfig
from ..simulation.scenario_engine import MissionData
from .windowing import (
    BEHAVIOUR_FEATURES,
    CROSS_VEHICLE_FEATURES,
    NETWORK_FEATURES,
    TELEMETRY_FEATURES,
    mission_windows,
)

__all__ = ["FeaturePipeline", "build_windows", "MODALITY_FEATURES", "PHASE_CATEGORIES"]

PHASE_CATEGORIES = ["takeoff", "transit", "loiter", "return"]
PHASE_FEATURES = [f"phase_{p}" for p in PHASE_CATEGORIES]

MODALITY_FEATURES: dict[str, list[str]] = {
    "telemetry": TELEMETRY_FEATURES,
    "network": NETWORK_FEATURES,
    "behaviour": BEHAVIOUR_FEATURES,
}

# Numeric (pre-standardisation) feature columns, before one-hot phase.
BASE_NUMERIC_FEATURES = (
    TELEMETRY_FEATURES + NETWORK_FEATURES + BEHAVIOUR_FEATURES + CROSS_VEHICLE_FEATURES
)

META_COLUMNS = [
    "scenario_id", "run_id", "seed", "uav_id", "uav_index", "window_id", "window_start",
    "mission_phase", "attack_label", "attack_origin", "attack_onset", "attack_intensity",
    "mission_impact_window", "is_attack", "split",
]


def build_windows(
    missions: list[MissionData], scenario: ScenarioConfig, ada: ADAConfig
) -> pd.DataFrame:
    """Concatenate windowed features across missions (splits already assigned)."""
    parts = [
        mission_windows(m, scenario, ada.window_length_s, ada.window_stride_s)
        for m in missions
    ]
    df = pd.concat(parts, ignore_index=True)
    return df


@dataclass
class FeaturePipeline:
    """Fits standardisation on train-only rows and emits numeric matrices."""

    feature_names: list[str] = field(default_factory=list)
    scaler: StandardScaler | None = None
    fitted: bool = False

    def fit(self, train_df: pd.DataFrame, benign_only: bool = False) -> FeaturePipeline:
        cols = list(BASE_NUMERIC_FEATURES)
        fit_df = train_df
        if benign_only:
            fit_df = train_df[train_df["attack_label"] == "benign"]
        self.scaler = StandardScaler()
        self.scaler.fit(fit_df[cols].to_numpy())
        self.feature_names = list(BASE_NUMERIC_FEATURES) + PHASE_FEATURES
        self.fitted = True
        return self

    def transform(self, df: pd.DataFrame) -> np.ndarray:
        if not self.fitted or self.scaler is None:
            raise RuntimeError("FeaturePipeline.transform called before fit")
        numeric = self.scaler.transform(df[list(BASE_NUMERIC_FEATURES)].to_numpy())
        phase = _one_hot_phase(df["mission_phase"])
        return np.hstack([numeric, phase])

    def transform_modality(self, df: pd.DataFrame, modality: str) -> np.ndarray:
        """Return the standardised sub-matrix for a single modality (for ADA)."""
        if not self.fitted or self.scaler is None:
            raise RuntimeError("transform_modality called before fit")
        cols = MODALITY_FEATURES[modality]
        idx = [list(BASE_NUMERIC_FEATURES).index(c) for c in cols]
        full = self.scaler.transform(df[list(BASE_NUMERIC_FEATURES)].to_numpy())
        return full[:, idx]

    @property
    def dim(self) -> int:
        return len(self.feature_names)

    def save(self, path: Path) -> Path:
        path.parent.mkdir(parents=True, exist_ok=True)
        joblib.dump(
            {"scaler": self.scaler, "feature_names": self.feature_names}, path
        )
        return path

    @classmethod
    def load(cls, path: Path) -> FeaturePipeline:
        blob = joblib.load(path)
        pipe = cls(feature_names=blob["feature_names"], scaler=blob["scaler"], fitted=True)
        return pipe


def _one_hot_phase(series: pd.Series) -> np.ndarray:
    out = np.zeros((len(series), len(PHASE_CATEGORIES)))
    values = series.to_numpy()
    for j, cat in enumerate(PHASE_CATEGORIES):
        out[:, j] = (values == cat).astype(float)
    return out
