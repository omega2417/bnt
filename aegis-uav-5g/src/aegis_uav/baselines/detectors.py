"""Baseline detectors/classifiers (B1-B4).

- B1 single-modality detectors: obtained directly from the ADA per-modality flags.
- B2 flat attribution classifier: obtained from AAA in non-hierarchical mode.
- B3 Random Forest flow classifier: supervised binary detector on network features.
- B4 static response policy: obtained from RSA.static_select.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier

from ..features.pipeline import MODALITY_FEATURES
from ..features.windowing import NETWORK_FEATURES

__all__ = ["RandomForestFlowDetector"]


class RandomForestFlowDetector:
    """Supervised Random-Forest attack/benign detector on flow (network) features.

    Represents the SDN + Random-Forest rogue-node detector baseline (B3).
    """

    def __init__(self, n_estimators: int = 200, seed: int = 0) -> None:
        self.model = RandomForestClassifier(n_estimators=n_estimators, random_state=seed)
        self.features = list(MODALITY_FEATURES["network"]) or list(NETWORK_FEATURES)

    def fit(self, train_df: pd.DataFrame) -> RandomForestFlowDetector:
        X = train_df[self.features].to_numpy()
        y = (train_df["attack_label"] != "benign").astype(int).to_numpy()
        self.model.fit(X, y)
        return self

    def predict(self, df: pd.DataFrame) -> np.ndarray:
        X = df[self.features].to_numpy()
        return self.model.predict(X)

    def predict_proba(self, df: pd.DataFrame) -> np.ndarray:
        X = df[self.features].to_numpy()
        proba = self.model.predict_proba(X)
        # Return P(attack); handle degenerate single-class training.
        if proba.shape[1] == 1:
            only = self.model.classes_[0]
            return np.full(len(df), float(only))
        return proba[:, list(self.model.classes_).index(1)]
