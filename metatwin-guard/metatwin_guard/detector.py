"""Static rules and the robust explainable detector, Equations (3)-(7)."""
from __future__ import annotations

import math
import statistics
from dataclasses import dataclass, field
from typing import Iterable, Mapping

from . import config


@dataclass
class StaticRules:
    rules: tuple = config.STATIC_RULES

    def fired(self, x: Mapping[str, float]) -> list[str]:
        out = []
        for feat, op, thr in self.rules:
            v = x[feat]
            if (op == ">" and v > thr) or (op == "<" and v < thr):
                out.append(f"{feat}{op}{thr:g}")
        return out

    def decide(self, x: Mapping[str, float]) -> bool:
        return bool(self.fired(x))


@dataclass
class RobustResult:
    score: float
    z: dict[str, float]
    contributions: dict[str, float]
    top: list[tuple[str, float]]
    flagged: bool


@dataclass
class RobustDetector:
    floor: float = config.DISPERSION_FLOOR
    threshold: float = config.SCORE_THRESHOLD
    clip: float = config.Z_CLIP
    features: tuple = config.FEATURES
    median: dict[str, float] = field(default_factory=dict)
    mad: dict[str, float] = field(default_factory=dict)
    scale: dict[str, float] = field(default_factory=dict)

    def fit(self, baseline: Iterable[Mapping[str, float]]) -> "RobustDetector":
        rows = list(baseline)
        if not rows:
            raise ValueError("baseline is empty")
        for f in self.features:
            vals = [float(r[f]) for r in rows]
            m = statistics.median(vals)
            mad = statistics.median(abs(v - m) for v in vals)
            self.median[f] = m
            self.mad[f] = mad
            # Eq. (3): s_j = max(1.4826 * MAD_j, floor)
            self.scale[f] = max(config.MAD_CONSISTENCY * mad, self.floor)
        return self

    def zscores(self, x: Mapping[str, float]) -> dict[str, float]:
        # Eq. (4): z_j = min(20, |x_j - m_j| / s_j)
        return {f: min(self.clip, abs(float(x[f]) - self.median[f]) / self.scale[f]) for f in self.features}

    def evaluate(self, x: Mapping[str, float], top_k: int = config.TOP_K) -> RobustResult:
        z = self.zscores(x)
        p = len(self.features)
        score = math.sqrt(sum(v * v for v in z.values()) / p)  # Eq. (5)
        total = sum(z.values())
        contrib = {f: (z[f] / total if total > 0 else 0.0) for f in self.features}  # Eq. (6)
        top = sorted(contrib.items(), key=lambda kv: (-kv[1], self.features.index(kv[0])))[:top_k]
        if total == 0:
            top = []
        return RobustResult(score, z, contrib, top, score >= self.threshold)


def hybrid_decision(rule_alert: bool, robust_alert: bool, admitted: bool) -> bool:
    """Eq. (7): d_H = d_R OR d_X OR NOT g."""
    return rule_alert or robust_alert or not admitted


def min_simultaneous_deviations(z: float, threshold: float, p: int = len(config.FEATURES)) -> int | None:
    """Smallest k with sqrt(k z^2 / p) >= threshold, i.e. ceil(p tau^2 / z^2); None if k > p."""
    if z <= 0:
        return None
    k = math.ceil(p * threshold**2 / z**2 - 1e-12)
    return k if k <= p else None
