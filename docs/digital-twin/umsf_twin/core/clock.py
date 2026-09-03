"""Single logical clock with the phase order of specification section 6.5.

Time is stored as an integer number of nanoseconds so that repeated stepping
never accumulates floating point drift, and every event carries a total order
key ``(time_ns, phase, source_id, source_sequence, event_id)``.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from enum import IntEnum

__all__ = ["Phase", "SimClock", "NS_PER_S"]

NS_PER_S = 1_000_000_000


class Phase(IntEnum):
    """Deterministic intra-step ordering; lower runs first."""

    INTEGRATE = 0        # continuous equations advanced to T
    SCENARIO = 1         # scenario event / fault injection
    PROTECTION = 2       # BMS and ATS hardware protection
    POWER_ASSET = 3      # power path and asset lifecycle
    TOPOLOGY = 4         # routes, WAN selection, VPN, AP state
    FLOWS = 5            # aggregated or packet flows
    SAMPLING = 6         # sensor sampling and telemetry delivery
    INFERENCE = 7        # feature pipeline and detectors
    RESPONSE = 8         # deferred recommendation / response


@dataclass
class SimClock:
    """Wall-clock anchored logical clock."""

    start_utc: datetime
    dt_ns: int = NS_PER_S
    t_ns: int = 0

    def __post_init__(self) -> None:
        if self.start_utc.tzinfo is None:
            self.start_utc = self.start_utc.replace(tzinfo=timezone.utc)
        self.start_utc = self.start_utc.astimezone(timezone.utc)
        if self.dt_ns <= 0:
            raise ValueError("dt_ns must be positive")

    @classmethod
    def from_iso(cls, start_utc: str, dt_s: float = 1.0) -> "SimClock":
        stamp = datetime.fromisoformat(start_utc.replace("Z", "+00:00"))
        return cls(stamp, int(round(dt_s * NS_PER_S)))

    @property
    def t_s(self) -> float:
        return self.t_ns / NS_PER_S

    @property
    def step_index(self) -> int:
        return self.t_ns // self.dt_ns

    @property
    def dt_s(self) -> float:
        return self.dt_ns / NS_PER_S

    def utc(self, offset_ns: int = 0) -> datetime:
        return self.start_utc + timedelta(microseconds=(self.t_ns + offset_ns) / 1000)

    def iso(self, offset_ns: int = 0) -> str:
        return self.utc(offset_ns).isoformat().replace("+00:00", "Z")

    def interval_iso(self) -> tuple[str, str]:
        """Half-open ``[start, end)`` label of the current step."""

        return self.iso(), self.iso(self.dt_ns)

    def advance(self) -> int:
        self.t_ns += self.dt_ns
        return self.t_ns

    def reset(self) -> None:
        self.t_ns = 0
