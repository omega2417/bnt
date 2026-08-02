"""Anomaly Detection Agent (ADA).

Three per-modality autoencoders trained on benign windows only.  Anomaly score is
the squared-L2 reconstruction error (Eq. 2); a window is flagged when the score
exceeds an adaptive EWMA threshold ``theta = mu + kappa*sigma`` (Eq. 3).
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd
from sklearn.neural_network import MLPRegressor

from ..schemas import ADAConfig
from .base import BaseAgent

__all__ = ["Autoencoder", "AnomalyDetectionAgent"]

MODALITIES = ("telemetry", "network", "behaviour")
_MOD_KEY = {"telemetry": "tel", "network": "net", "behaviour": "beh"}


@dataclass
class Autoencoder:
    """MLP autoencoder (``input -> hidden -> latent -> hidden -> input``)."""

    hidden_sizes: list[int]
    latent_dim: int
    learning_rate: float
    batch_size: int
    max_epochs: int
    seed: int
    model: MLPRegressor | None = field(default=None, init=False)
    benign_mean: float = field(default=0.0, init=False)
    benign_std: float = field(default=1.0, init=False)

    def _layers(self) -> tuple[int, ...]:
        return tuple(self.hidden_sizes + [self.latent_dim] + list(reversed(self.hidden_sizes)))

    def fit(self, x: np.ndarray) -> Autoencoder:
        bs = min(self.batch_size, max(len(x), 1))
        self.model = MLPRegressor(
            hidden_layer_sizes=self._layers(),
            activation="relu",
            solver="adam",
            learning_rate_init=self.learning_rate,
            batch_size=bs,
            max_iter=self.max_epochs,
            random_state=self.seed,
            early_stopping=False,
        )
        self.model.fit(x, x)
        errs = self.reconstruction_error(x)
        self.benign_mean = float(errs.mean())
        self.benign_std = float(errs.std() + 1e-9)
        return self

    def reconstruction_error(self, x: np.ndarray) -> np.ndarray:
        assert self.model is not None
        recon = self.model.predict(x)
        if recon.ndim == 1:
            recon = recon.reshape(-1, 1)
        return np.sum((x - recon) ** 2, axis=1)

    def per_feature_error(self, x: np.ndarray) -> np.ndarray:
        assert self.model is not None
        recon = self.model.predict(x)
        if recon.ndim == 1:
            recon = recon.reshape(-1, 1)
        return (x - recon) ** 2


class AnomalyDetectionAgent(BaseAgent):
    name = "ada"

    def __init__(self, config: ADAConfig, seed: int = 0, deterministic: bool = True) -> None:
        super().__init__(config, seed, deterministic)
        self.autoencoders: dict[str, Autoencoder] = {}
        self.feature_pipeline = None

    def fit(self, train_df: pd.DataFrame, pipe) -> AnomalyDetectionAgent:
        self.feature_pipeline = pipe
        benign = train_df[train_df["attack_label"] == "benign"]
        cfg: ADAConfig = self.config
        if cfg.max_train_windows and len(benign) > cfg.max_train_windows:
            benign = benign.sample(n=cfg.max_train_windows, random_state=self.seed)
        for m in MODALITIES:
            x = pipe.transform_modality(benign, m)
            ae = Autoencoder(
                hidden_sizes=cfg.hidden_sizes,
                latent_dim=cfg.latent_dim,
                learning_rate=cfg.learning_rate,
                batch_size=cfg.batch_size,
                max_epochs=cfg.max_epochs,
                seed=self.seed + hash(m) % 1000,
            )
            ae.fit(x)
            self.autoencoders[m] = ae
        return self

    def raw_scores(self, df: pd.DataFrame) -> dict[str, np.ndarray]:
        pipe = self.feature_pipeline
        return {
            m: self.autoencoders[m].reconstruction_error(pipe.transform_modality(df, m))
            for m in MODALITIES
        }

    # Fixed normalisation scale (in benign std units) so that the reported
    # severity is decoupled from the EWMA sensitivity kappa; kappa affects only
    # the streaming flag threshold in :meth:`detect`.
    NORM_SCALE = 3.0

    def normalised_score(self, m: str, raw: np.ndarray) -> np.ndarray:
        ae = self.autoencoders[m]
        z = (raw - ae.benign_mean) / (self.NORM_SCALE * ae.benign_std)
        return 1.0 - np.exp(-np.clip(z, 0, None))

    def detect(self, df: pd.DataFrame) -> pd.DataFrame:
        """Return per-window modality scores and adaptive-EWMA flags.

        Threshold is maintained as an EWMA stream per (run_id, uav), in window
        temporal order, updated only on non-flagged windows (Eq. 3).
        """
        cfg: ADAConfig = self.config
        raw = self.raw_scores(df)
        out = df[["run_id", "uav_index", "window_id", "window_start"]].copy().reset_index()
        for m in MODALITIES:
            out[f"{_MOD_KEY[m]}_raw"] = raw[m]
            out[f"{_MOD_KEY[m]}_score"] = self.normalised_score(m, raw[m])
            out[f"{_MOD_KEY[m]}_flag"] = False

        order = out.sort_values(["run_id", "uav_index", "window_start"]).index
        for m in MODALITIES:
            ae = self.autoencoders[m]
            key = _MOD_KEY[m]
            mu, var = ae.benign_mean, ae.benign_std**2
            prev_stream: tuple = ()
            for i in order:
                stream = (out.at[i, "run_id"], out.at[i, "uav_index"])
                if stream != prev_stream:
                    mu, var = ae.benign_mean, ae.benign_std**2
                    prev_stream = stream
                s = out.at[i, f"{key}_raw"]
                sigma = np.sqrt(max(var, 1e-12))
                theta = mu + cfg.kappa * sigma
                flag = bool(s > theta)
                out.at[i, f"{key}_flag"] = flag
                if not flag:  # adapt on benign-looking windows only
                    dev = s - mu
                    mu = mu + cfg.alpha * dev
                    var = (1 - cfg.alpha) * (var + cfg.alpha * dev * dev)

        out["any_flag"] = out[[f"{_MOD_KEY[m]}_flag" for m in MODALITIES]].any(axis=1)
        return out.set_index("index")

    def top_features(self, df_rows: pd.DataFrame, modality: str, k: int = 3) -> list[str]:
        pipe = self.feature_pipeline
        from ..features.pipeline import MODALITY_FEATURES

        x = pipe.transform_modality(df_rows, modality)
        err = self.autoencoders[modality].per_feature_error(x).mean(axis=0)
        names = MODALITY_FEATURES[modality]
        idx = np.argsort(err)[::-1][:k]
        return [names[i] for i in idx]
