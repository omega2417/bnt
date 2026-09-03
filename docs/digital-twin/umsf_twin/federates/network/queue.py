"""Fluid queue of specification section 9.1.

Per step the queue receives ``A_t = R_t*dt/8`` megabytes and drains
``S_t = C_t*dt/8``; the residual backlog becomes queueing delay
``D_q = 8*Q/C``. This is a deliberately coarse surrogate: it reproduces
saturation and recovery dynamics, not packet-level behaviour.
"""

from __future__ import annotations

from dataclasses import dataclass

__all__ = ["FluidQueue", "MAX_QUEUE_DELAY_MS"]

MAX_QUEUE_DELAY_MS = 60_000.0


@dataclass
class FluidQueue:
    name: str = "queue"
    backlog_mb: float = 0.0
    max_backlog_mb: float = 4_000.0
    drops_mb: float = 0.0

    def step(self, offered_mbps: float, capacity_mbps: float, dt_s: float) -> dict:
        """Advance one step and return throughput, delay and drop metrics.

        A capacity of zero means there is no usable path at all. The queue then
        reports ``path_available=False`` instead of an astronomically large
        delay derived from a near-zero denominator, and the telemetry federate
        blanks the corresponding latency fields.
        """

        if capacity_mbps <= 0.0:
            arrivals_mb = max(0.0, offered_mbps) * dt_s / 8.0
            self.backlog_mb = min(self.max_backlog_mb, self.backlog_mb + arrivals_mb)
            return {
                "throughput_mbps": 0.0,
                "queue_backlog_mb": self.backlog_mb,
                "queue_delay_ms": MAX_QUEUE_DELAY_MS,
                "queue_drop_mbps": 0.0,
                "utilization": 1.0,
                "path_available": False,
            }
        arrivals_mb = max(0.0, offered_mbps) * dt_s / 8.0
        service_mb = capacity_mbps * dt_s / 8.0
        backlog = self.backlog_mb + arrivals_mb
        served_mb = min(backlog, service_mb)
        backlog -= served_mb
        dropped = max(0.0, backlog - self.max_backlog_mb)
        backlog -= dropped
        self.drops_mb += dropped
        self.backlog_mb = backlog

        delay_ms = min(MAX_QUEUE_DELAY_MS, 8.0 * backlog / capacity_mbps * 1000.0)
        return {
            "throughput_mbps": served_mb * 8.0 / dt_s,
            "queue_backlog_mb": backlog,
            "queue_delay_ms": delay_ms,
            "queue_drop_mbps": dropped * 8.0 / dt_s,
            "utilization": min(1.0, offered_mbps / capacity_mbps),
            "path_available": True,
        }

    def reset(self) -> None:
        self.backlog_mb = 0.0
        self.drops_mb = 0.0
