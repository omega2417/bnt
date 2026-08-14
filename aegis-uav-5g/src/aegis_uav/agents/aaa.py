"""Attack Attribution Agent (AAA).

Hierarchical, calibrated classification: level 1 separates macro-classes
{gnss, network, session_behaviour, benign}; level 2 resolves the leaf T1-T6.
Posterior P(a|E) ∝ P(E|a)P(a) (Eq. 5); origin is attributed by counterfactual
score reduction over the incident's entities.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
from sklearn.calibration import CalibratedClassifierCV
from sklearn.ensemble import HistGradientBoostingClassifier, RandomForestClassifier
from sklearn.neural_network import MLPClassifier

from .. import ATTACK_CLASSES, BENIGN_LABEL, MACRO_CLASSES
from ..schemas import AAAConfig
from .base import BaseAgent

__all__ = ["AttackAttributionAgent"]

MACRO_OF: dict[str, str] = {BENIGN_LABEL: "benign", **MACRO_CLASSES}
LEAVES_BY_MACRO: dict[str, list[str]] = {}
for _leaf, _macro in MACRO_OF.items():
    LEAVES_BY_MACRO.setdefault(_macro, []).append(_leaf)


def _base_estimator(cfg: AAAConfig, seed: int):
    if cfg.classifier == "random_forest":
        return RandomForestClassifier(n_estimators=cfg.n_estimators, random_state=seed)
    if cfg.classifier == "mlp":
        return MLPClassifier(hidden_layer_sizes=(64, 32), max_iter=cfg.max_iter,
                             random_state=seed)
    return HistGradientBoostingClassifier(max_iter=cfg.max_iter, random_state=seed)


def _fit_calibrated(estimator, X, y, method: str, seed: int):
    """Fit with probability calibration, robust to small per-class counts."""
    classes, counts = np.unique(y, return_counts=True)
    if len(classes) < 2:
        estimator.fit(X, y)
        return estimator, classes
    min_count = counts.min()
    if method == "none" or min_count < 3:
        estimator.fit(X, y)
        return estimator, classes
    cv = int(min(3, min_count))
    cal = CalibratedClassifierCV(estimator, method=method, cv=cv)
    cal.fit(X, y)
    return cal, classes


class AttackAttributionAgent(BaseAgent):
    name = "aaa"

    def __init__(self, config: AAAConfig, seed: int = 0, deterministic: bool = True) -> None:
        super().__init__(config, seed, deterministic)
        self.pipe = None
        self.macro_model = None
        self.macro_classes: np.ndarray | None = None
        self.leaf_models: dict[str, object] = {}
        self.leaf_classes: dict[str, np.ndarray] = {}
        self.flat_model = None
        self.flat_classes: np.ndarray | None = None

    def fit(self, train_df: pd.DataFrame, pipe) -> AttackAttributionAgent:
        cfg: AAAConfig = self.config
        self.pipe = pipe
        train_df = self._balance(train_df, cfg.benign_ratio)
        X = pipe.transform(train_df)
        leaf = train_df["attack_label"].to_numpy()
        macro = np.array([MACRO_OF.get(v, "benign") for v in leaf])

        # Flat baseline model (always trained; used by the flat attribution baseline).
        self.flat_model, self.flat_classes = _fit_calibrated(
            _base_estimator(cfg, self.seed), X, leaf, cfg.calibration, self.seed
        )

        # Always train the hierarchical models too (cheap) so that both the
        # hierarchical framework and the flat baseline are available for the E2
        # comparison regardless of which path the agentic loop uses.
        self.macro_model, self.macro_classes = _fit_calibrated(
            _base_estimator(cfg, self.seed + 1), X, macro, cfg.calibration, self.seed
        )
        for m, leaves in LEAVES_BY_MACRO.items():
            mask = macro == m
            if mask.sum() == 0 or len(set(leaf[mask])) < 2:
                self.leaf_classes[m] = np.array(sorted(set(leaf[mask])) or [leaves[0]])
                self.leaf_models[m] = None
                continue
            model, classes = _fit_calibrated(
                _base_estimator(cfg, self.seed + 2), X[mask], leaf[mask],
                cfg.calibration, self.seed,
            )
            self.leaf_models[m] = model
            self.leaf_classes[m] = classes
        return self

    def _balance(self, train_df: pd.DataFrame, ratio: float) -> pd.DataFrame:
        """Cap benign windows at ``ratio`` x the number of attack windows.

        Mitigates class imbalance (Section 5.3) and speeds classifier fitting.
        """
        if ratio is None or ratio <= 0:
            return train_df
        benign = train_df[train_df["attack_label"] == BENIGN_LABEL]
        attack = train_df[train_df["attack_label"] != BENIGN_LABEL]
        cap = int(ratio * max(len(attack), 1))
        if len(benign) > cap:
            benign = benign.sample(n=cap, random_state=self.seed)
        return pd.concat([benign, attack], ignore_index=True)

    def _posterior_hierarchical(self, x: np.ndarray) -> dict[str, float]:
        macro_proba = self.macro_model.predict_proba(x)[0]
        macro_p = dict(zip(self.macro_classes, macro_proba, strict=True))
        post = {lbl: 0.0 for lbl in (BENIGN_LABEL, *ATTACK_CLASSES)}
        for m, p_macro in macro_p.items():
            leaves = LEAVES_BY_MACRO[m]
            model = self.leaf_models.get(m)
            if model is None or len(leaves) == 1:
                for lf in leaves:
                    post[lf] += p_macro
            else:
                leaf_proba = model.predict_proba(x)[0]
                for lf, p_leaf in zip(self.leaf_classes[m], leaf_proba, strict=True):
                    post[lf] += p_macro * p_leaf
        total = sum(post.values()) or 1.0
        return {k: v / total for k, v in post.items()}

    def _posterior_flat(self, x: np.ndarray) -> dict[str, float]:
        proba = self.flat_model.predict_proba(x)[0]
        post = {lbl: 0.0 for lbl in (BENIGN_LABEL, *ATTACK_CLASSES)}
        for lbl, p in zip(self.flat_classes, proba, strict=True):
            post[lbl] = float(p)
        return post

    def attribute(self, feature_vector: np.ndarray, hierarchical: bool | None = None) -> dict:
        x = feature_vector.reshape(1, -1)
        use_h = self.config.hierarchical if hierarchical is None else hierarchical
        post = self._posterior_hierarchical(x) if use_h else self._posterior_flat(x)
        leaf = max(post, key=post.get)
        macro = MACRO_OF.get(leaf, "benign")
        return {
            "predicted_attack": leaf,
            "macro_class": macro,
            "attack_posterior": post,
            "confidence": float(post[leaf]),
        }

    def posterior_matrix(
        self, X: np.ndarray, hierarchical: bool | None = None
    ) -> np.ndarray:
        """Vectorised posterior over ALL_LABELS for a batch of feature vectors."""
        labels = list((BENIGN_LABEL, *ATTACK_CLASSES))
        use_h = self.config.hierarchical if hierarchical is None else hierarchical
        n = X.shape[0]
        post = np.zeros((n, len(labels)))
        if not use_h:
            proba = self.flat_model.predict_proba(X)
            for j, c in enumerate(self.flat_classes):
                post[:, labels.index(c)] = proba[:, j]
        else:
            macro_proba = self.macro_model.predict_proba(X)
            macro_p = {c: macro_proba[:, j] for j, c in enumerate(self.macro_classes)}
            for m, p_macro in macro_p.items():
                leaves = LEAVES_BY_MACRO[m]
                model = self.leaf_models.get(m)
                if model is None or len(leaves) == 1:
                    for lf in leaves:
                        post[:, labels.index(lf)] += p_macro
                else:
                    leaf_proba = model.predict_proba(X)
                    for j, lf in enumerate(self.leaf_classes[m]):
                        post[:, labels.index(lf)] += p_macro * leaf_proba[:, j]
        totals = post.sum(axis=1, keepdims=True)
        totals[totals == 0] = 1.0
        return post / totals

    def predict_batch(
        self, X: np.ndarray, hierarchical: bool | None = None
    ) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
        """Return (leaf_pred, macro_pred, posterior_matrix) for a batch."""
        labels = np.array((BENIGN_LABEL, *ATTACK_CLASSES))
        post = self.posterior_matrix(X, hierarchical)
        leaf_pred = labels[post.argmax(axis=1)]
        macro_pred = np.array([MACRO_OF.get(v, "benign") for v in leaf_pred])
        return leaf_pred, macro_pred, post

    def attribute_origin(
        self, incident_rows: pd.DataFrame, detection: pd.DataFrame
    ) -> tuple[str, float]:
        """Counterfactual origin: the entity whose removal most reduces severity."""
        entities = sorted(incident_rows["uav_index"].unique())
        if len(entities) <= 1:
            u = int(entities[0])
            return f"uav_{u:02d}", 1.0
        idx = incident_rows.index
        base = detection.loc[idx, ["tel_score", "net_score", "beh_score"]].mean().mean()
        reductions: dict[int, float] = {}
        for u in entities:
            keep = incident_rows[incident_rows["uav_index"] != u].index
            if len(keep) == 0:
                reductions[u] = base
                continue
            without = detection.loc[keep, ["tel_score", "net_score", "beh_score"]].mean().mean()
            reductions[u] = float(base - without)
        origin = max(reductions, key=reductions.get)
        total = sum(max(v, 0) for v in reductions.values()) or 1.0
        conf = float(max(reductions[origin], 0) / total)
        return f"uav_{int(origin):02d}", conf
