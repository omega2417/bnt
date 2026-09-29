"""Causal forecasts for the EMS (section 11.4). The forecaster is only ever
fed past measurements through observe(); it has no handle on the scenario
profile, which enforces the no-future-leakage rule by construction."""
from __future__ import annotations

import numpy as np


class CausalGenForecaster:
    def __init__(self, alpha_per_min: float = 0.05, cold_start_w: float = 0.0):
        self.alpha = alpha_per_min
        self.level = None
        self.cold_start_w = cold_start_w
        self._acc, self._n = 0.0, 0

    def observe(self, p_gen_w: float) -> None:
        self._acc += p_gen_w
        self._n += 1
        if self._n >= 60:  # update once per minute of data
            m = self._acc / self._n
            self.level = m if self.level is None else (1 - self.alpha) * self.level + self.alpha * m
            self._acc, self._n = 0.0, 0

    @property
    def cold(self) -> bool:
        return self.level is None

    def forecast(self, n_steps: int) -> np.ndarray:
        lvl = self.cold_start_w if self.level is None else self.level
        if self._n:
            recent = self._acc / self._n
            lvl = recent if self.level is None else (1 - self.alpha) * lvl + self.alpha * recent
        return np.full(n_steps, max(0.0, lvl))


class DemandForecaster:
    def __init__(self):
        self.crit_bus = None

    def observe(self, p_crit_bus_w: float) -> None:
        self.crit_bus = p_crit_bus_w if self.crit_bus is None else 0.99 * self.crit_bus + 0.01 * p_crit_bus_w

    def forecast(self, n_steps: int, aux_schedule_bus_w: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
        crit = np.full(n_steps, self.crit_bus if self.crit_bus is not None else 20.0)
        return crit, np.asarray(aux_schedule_bus_w[:n_steps], float)
