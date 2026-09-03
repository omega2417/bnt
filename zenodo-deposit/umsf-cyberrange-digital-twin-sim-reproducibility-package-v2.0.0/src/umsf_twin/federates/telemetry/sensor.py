"""Sensor model: noise, quantisation, clock error and missingness (9.11).

The twin distinguishes ``event_time`` (when it happened in the model),
``observed_time`` (when a sensor saw it) and ``ingest_time`` (when the pipeline
received it). Any analysis that ignores that distinction will look better than
reality, which is precisely the bias this module exists to reproduce.
"""

from __future__ import annotations

import random
from dataclasses import dataclass
from typing import Any

__all__ = ["Sensor", "MissingnessModel"]


@dataclass
class MissingnessModel:
    """MCAR / MAR / MNAR sample loss."""

    mcar_pct: float = 0.2
    mar_pct_per_util: float = 1.5        # scales with link utilisation
    mnar_threshold: float | None = None  # values beyond it are dropped
    mnar_pct: float = 30.0

    def drops(self, rng: random.Random, value: float | None, utilization: float) -> str | None:
        if rng.random() * 100.0 < self.mcar_pct:
            return "MCAR"
        if rng.random() * 100.0 < self.mar_pct_per_util * max(0.0, utilization):
            return "MAR"
        if (self.mnar_threshold is not None and value is not None
                and value > self.mnar_threshold
                and rng.random() * 100.0 < self.mnar_pct):
            return "MNAR"
        return None


@dataclass
class Sensor:
    sensor_id: str
    noise_sd: float = 0.0
    quantum: float = 0.0                 # 0 disables quantisation
    bias: float = 0.0
    clock_offset_ms: float = 0.0
    clock_drift_ppm: float = 0.0
    freeze_probability: float = 0.0
    missingness: MissingnessModel = None  # type: ignore[assignment]
    _frozen_value: float | None = None
    _frozen_steps: int = 0

    def __post_init__(self) -> None:
        if self.missingness is None:
            self.missingness = MissingnessModel()

    def observed_offset_ms(self, t_s: float) -> float:
        return self.clock_offset_ms + self.clock_drift_ppm * t_s / 1000.0

    def measure(self, true_value: float | None, rng: random.Random, t_s: float,
                utilization: float = 0.0) -> dict[str, Any]:
        flags: list[str] = []
        if true_value is None:
            return {"value": None, "flags": ["GAP"], "offset_ms": self.observed_offset_ms(t_s)}

        reason = self.missingness.drops(rng, true_value, utilization)
        if reason is not None:
            return {"value": None, "flags": ["GAP", f"MISSING_{reason}"],
                    "offset_ms": self.observed_offset_ms(t_s)}

        if self._frozen_steps > 0:
            self._frozen_steps -= 1
            return {"value": self._frozen_value, "flags": ["STALE"],
                    "offset_ms": self.observed_offset_ms(t_s)}
        if rng.random() < self.freeze_probability:
            self._frozen_value = true_value
            self._frozen_steps = rng.randint(2, 8)
            flags.append("STALE")

        value = true_value + self.bias + (rng.gauss(0.0, self.noise_sd)
                                          if self.noise_sd > 0 else 0.0)
        if self.quantum > 0:
            value = round(value / self.quantum) * self.quantum
            flags.append("SYNTHETIC")
        return {"value": value, "flags": flags or ["OK"],
                "offset_ms": self.observed_offset_ms(t_s)}
