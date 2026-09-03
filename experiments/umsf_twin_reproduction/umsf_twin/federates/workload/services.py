"""Per-service arrival and volume processes (section 9.5).

Each service keeps its own candidate distribution family. None of them is
calibrated yet: the point of naming the family explicitly is that section 13
can later fit it against real traffic instead of replacing an anonymous
"random noise" term.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

from ...core.rng import RngHub

__all__ = ["ServiceProfile", "DEFAULT_SERVICES"]


@dataclass
class ServiceProfile:
    name: str
    flows_mean: float                 # flows per second at reference load
    flow_bytes_median: float
    flow_bytes_sigma: float = 1.1     # lognormal sigma
    dispersion: float = 6.0           # NB size parameter
    burstiness: float = 0.0           # 0..1, Hawkes-like self-excitation
    diurnal: bool = True
    _excitation: float = 0.0

    def step(self, rng: RngHub, t_s: float, seasonal: float,
             load_factor: float = 1.0) -> dict[str, float]:
        mean = self.flows_mean * load_factor * (seasonal if self.diurnal else 1.0)
        mean *= 1.0 + self._excitation
        flows = rng.negative_binomial(f"workload:{self.name}", mean, self.dispersion)
        self._excitation = max(0.0, self._excitation * 0.85
                               + self.burstiness * (flows > mean * 1.5))
        bytes_total = 0.0
        for _ in range(min(flows, 500)):
            bytes_total += rng.lognormal(f"workload_bytes:{self.name}",
                                         self.flow_bytes_median, self.flow_bytes_sigma)
        if flows > 500:                       # scale the tail instead of sampling it
            bytes_total *= flows / 500.0
        return {"flows": float(flows), "bytes": bytes_total,
                "mbps": bytes_total * 8.0 / 1e6}


def seasonal_factor(t_s: float, amplitude: float = 0.3, period_s: int = 86400,
                    phase_s: int = 32400) -> float:
    angle = 2.0 * math.pi * ((t_s + phase_s) % period_s) / period_s
    return max(0.2, 1.0 + amplitude * math.sin(angle))


#: Reference service mix; magnitudes are ``synthetic_demo`` until measured.
DEFAULT_SERVICES = (
    ServiceProfile("dns", flows_mean=40.0, flow_bytes_median=320.0, flow_bytes_sigma=0.6,
                   dispersion=12.0),
    ServiceProfile("dhcp", flows_mean=1.5, flow_bytes_median=600.0, flow_bytes_sigma=0.4,
                   dispersion=4.0),
    ServiceProfile("web", flows_mean=55.0, flow_bytes_median=48_000.0,
                   flow_bytes_sigma=1.4, dispersion=5.0, burstiness=0.3),
    ServiceProfile("file", flows_mean=6.0, flow_bytes_median=1_500_000.0,
                   flow_bytes_sigma=1.6, dispersion=3.0, burstiness=0.2),
    ServiceProfile("update", flows_mean=2.0, flow_bytes_median=6_000_000.0,
                   flow_bytes_sigma=1.2, dispersion=2.0, diurnal=False),
    ServiceProfile("control", flows_mean=12.0, flow_bytes_median=1_200.0,
                   flow_bytes_sigma=0.5, dispersion=10.0, diurnal=False),
)
