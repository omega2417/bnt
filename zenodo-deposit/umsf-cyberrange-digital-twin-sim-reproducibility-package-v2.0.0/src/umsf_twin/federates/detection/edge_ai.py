"""Zero-dependency online detector (logistic regression on EWMA features).

This stands in for the Edge-AI container of the target architecture. It learns
online from the *rule baseline* only in ``shadow`` mode and never from ground
truth, so its score cannot leak labels into the evaluation.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any

__all__ = ["EwmaFeature", "EdgeDetector"]


@dataclass
class EwmaFeature:
    alpha: float = 0.05
    mean: float = 0.0
    variance: float = 1.0
    initialized: bool = False

    def update(self, value: float) -> float:
        """Return the standardised residual and update the running moments."""

        if not self.initialized:
            self.mean, self.initialized = value, True
            return 0.0
        residual = value - self.mean
        self.mean += self.alpha * residual
        self.variance = (1.0 - self.alpha) * (self.variance + self.alpha * residual ** 2)
        return residual / math.sqrt(max(self.variance, 1e-9))


@dataclass
class EdgeDetector:
    feature_names: tuple[str, ...] = ("scan_rate_pps", "auth_failures", "lateral_events",
                                      "c2_beacons", "retry_pct", "loss_pct", "rtt_ms")
    learning_rate: float = 0.05
    threshold: float = 0.5
    l2: float = 1e-4
    weights: dict[str, float] = field(default_factory=dict)
    bias: float = -1.0
    trackers: dict[str, EwmaFeature] = field(default_factory=dict)
    updates: int = 0

    def __post_init__(self) -> None:
        for name in self.feature_names:
            self.weights.setdefault(name, 0.0)
            self.trackers.setdefault(name, EwmaFeature())

    def features(self, row: dict[str, Any]) -> dict[str, float]:
        output = {}
        for name in self.feature_names:
            value = row.get(name, 0.0)
            if value in ("", None):
                value = 0.0
            output[name] = self.trackers[name].update(float(value))
        return output

    def score(self, row: dict[str, Any]) -> dict[str, Any]:
        features = self.features(row)
        logit = self.bias + sum(self.weights[name] * value
                                for name, value in features.items())
        probability = 1.0 / (1.0 + math.exp(-max(-40.0, min(40.0, logit))))
        contributions = sorted(((abs(self.weights[n] * v), n) for n, v in features.items()),
                               reverse=True)[:3]
        return {
            "detector": "edge_ai_online_logistic",
            "score": probability,
            "alert": probability >= self.threshold,
            "threshold": self.threshold,
            "features": features,
            "explanation": "top features: " + ", ".join(name for _, name in contributions),
        }

    def learn(self, features: dict[str, float], weak_label: float) -> None:
        """One SGD step against a weak (non-ground-truth) label."""

        logit = self.bias + sum(self.weights[n] * v for n, v in features.items())
        prediction = 1.0 / (1.0 + math.exp(-max(-40.0, min(40.0, logit))))
        error = weak_label - prediction
        self.bias += self.learning_rate * error
        for name, value in features.items():
            self.weights[name] += self.learning_rate * (error * value
                                                        - self.l2 * self.weights[name])
        self.updates += 1
