"""Wi-Fi client population with seasonality (section 9.5).

Counts are Negative Binomial around a diurnal mean, which reproduces the
over-dispersion of real campus Wi-Fi far better than a Poisson draw, and keeps
the distribution family that the calibration stage will later fit.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

from ...core.rng import RngHub

__all__ = ["ClientPopulation"]


@dataclass
class ClientPopulation:
    site_id: str
    mean_clients: float
    dispersion: float = 8.0
    diurnal_amplitude: float = 0.25
    period_s: int = 86400
    phase_s: int = 32400                 # peak near 09:00 local

    def seasonal_factor(self, t_s: float) -> float:
        angle = 2.0 * math.pi * ((t_s + self.phase_s) % self.period_s) / self.period_s
        return 1.0 + self.diurnal_amplitude * math.sin(angle)

    def draw(self, rng: RngHub, t_s: float, drift_factor: float = 1.0) -> int:
        mean = max(0.0, self.mean_clients * self.seasonal_factor(t_s) * drift_factor)
        return rng.negative_binomial(f"wifi_clients:{self.site_id}", mean, self.dispersion)

    def spread(self, total: int, ap_count: int, rng: RngHub) -> list[int]:
        """Distribute clients over APs with a mild imbalance."""

        if ap_count <= 0:
            return []
        weights = [max(0.1, rng.normal(f"wifi_spread:{self.site_id}", 1.0, 0.25))
                   for _ in range(ap_count)]
        total_weight = sum(weights)
        counts = [int(total * weight / total_weight) for weight in weights]
        remainder = total - sum(counts)
        for index in range(max(0, remainder)):
            counts[index % ap_count] += 1
        return counts
