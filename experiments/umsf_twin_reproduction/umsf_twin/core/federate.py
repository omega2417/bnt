"""The federate contract of specification section 6.4.

Every simulated element - a WAN link, an access point, a battery pack, the
telemetry plane - is a federate exposing the same eight operations, so the
orchestrator can advance, checkpoint and health-check them uniformly.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from .bus import EventBus, Message
from .clock import SimClock

__all__ = ["Federate", "FederateHealth"]


class FederateHealth(dict):
    """Small helper so ``health()`` implementations stay one-liners."""

    @classmethod
    def ok(cls, name: str, **details: Any) -> "FederateHealth":
        return cls(name=name, status="OK", **details)

    @classmethod
    def degraded(cls, name: str, reason: str, **details: Any) -> "FederateHealth":
        return cls(name=name, status="DEGRADED", reason=reason, **details)

    @classmethod
    def failed(cls, name: str, reason: str, **details: Any) -> "FederateHealth":
        return cls(name=name, status="FAILED", reason=reason, **details)


class Federate(ABC):
    """Base class implementing the shared bookkeeping of a federate."""

    #: federates advance in ascending order of this attribute
    order: int = 50

    def __init__(self, name: str) -> None:
        self.name = name
        self.bus: EventBus | None = None
        self.clock: SimClock | None = None
        self.context: dict[str, Any] = {}
        self._initialized = False

    # -- lifecycle -------------------------------------------------------
    def initialize(self, clock: SimClock, bus: EventBus, context: dict[str, Any]) -> None:
        self.clock = clock
        self.bus = bus
        self.context = context
        self.on_initialize()
        self._initialized = True

    def on_initialize(self) -> None:  # pragma: no cover - optional hook
        """Subclass hook executed once before the first step."""

    def next_time(self) -> int:
        """Next time this federate wants control, in nanoseconds.

        The default surrogate is time-stepped, so it always asks for the next
        tick; discrete-event federates override this.
        """

        assert self.clock is not None
        return self.clock.t_ns + self.clock.dt_ns

    def apply_event(self, message: Message) -> None:  # pragma: no cover - optional
        """Consume one bus message addressed to this federate."""

    @abstractmethod
    def advance(self, t_ns: int, dt_ns: int) -> None:
        """Integrate internal state up to ``t_ns``."""

    @abstractmethod
    def observe(self) -> dict[str, Any]:
        """Return the observable state of the current step."""

    def checkpoint(self) -> dict[str, Any]:
        """Serializable snapshot; default is the observable state."""

        return {"name": self.name, "state": self.observe()}

    def restore(self, snapshot: dict[str, Any]) -> None:  # pragma: no cover - optional
        raise NotImplementedError(f"{self.name} does not support restore")

    def reset(self) -> None:  # pragma: no cover - optional
        """Return to the post-initialize state."""

    def health(self) -> FederateHealth:
        return FederateHealth.ok(self.name)

    def emit(self, kind: str, payload: dict[str, Any], phase=None) -> None:
        """Publish a message on the shared bus at the current step."""

        assert self.bus is not None and self.clock is not None
        from .clock import Phase

        self.bus.publish(self.clock.t_ns, phase or Phase.FLOWS, self.name, kind, payload)

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        return f"<{type(self).__name__} {self.name}>"
