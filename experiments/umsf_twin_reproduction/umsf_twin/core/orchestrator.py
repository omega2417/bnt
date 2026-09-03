"""Master clock and federation loop (sections 6.3-6.5).

The orchestrator owns time. Federates never advance each other; they are
stepped in phase order, their bus messages are delivered causally, and their
observations are merged into one telemetry row per site and step.
"""

from __future__ import annotations

from typing import Any, Callable, Iterable

from .bus import EventBus
from .clock import Phase, SimClock
from .errors import InvariantViolation
from .federate import Federate
from .parameters import ParameterRegistry
from .safety import SafetyPolicy

__all__ = ["Orchestrator", "StepResult"]


class StepResult(dict):
    """Observations of one step keyed by federate name."""


class Orchestrator:
    def __init__(self, clock: SimClock, policy: SafetyPolicy,
                 registry: ParameterRegistry, bus: EventBus | None = None) -> None:
        self.clock = clock
        self.policy = policy
        self.registry = registry
        self.bus = bus or EventBus()
        self.federates: list[Federate] = []
        self.context: dict[str, Any] = {"mode": policy.mode, "policy": policy,
                                        "registry": registry, "shared": {}}
        self.invariants: list[Callable[[StepResult, "Orchestrator"], None]] = []
        self.step_hooks: list[Callable[[StepResult, "Orchestrator"], None]] = []
        self._started = False

    # -- assembly --------------------------------------------------------
    def add(self, *federates: Federate) -> "Orchestrator":
        if self._started:
            raise InvariantViolation("cannot add federates after the run started")
        self.federates.extend(federates)
        self.federates.sort(key=lambda fed: (fed.order, fed.name))
        return self

    def add_invariant(self, check: Callable[[StepResult, "Orchestrator"], None]) -> None:
        self.invariants.append(check)

    def add_step_hook(self, hook: Callable[[StepResult, "Orchestrator"], None]) -> None:
        self.step_hooks.append(hook)

    def initialize(self) -> None:
        self.policy.check_mode()
        self.registry.assert_mode_ready(self.policy.mode)
        for federate in self.federates:
            federate.initialize(self.clock, self.bus, self.context)
        self._started = True

    # -- execution -------------------------------------------------------
    def step(self) -> StepResult:
        """Advance every federate by one tick and collect observations."""

        t_ns, dt_ns = self.clock.t_ns, self.clock.dt_ns
        for message in self.bus.drain_until(t_ns):
            target = message.payload.get("target")
            for federate in self.federates:
                if target in (None, federate.name):
                    federate.apply_event(message)

        result = StepResult()
        for federate in self.federates:
            federate.advance(t_ns, dt_ns)
            result[federate.name] = federate.observe()

        for check in self.invariants:
            check(result, self)
        for hook in self.step_hooks:
            hook(result, self)
        self.clock.advance()
        return result

    def run(self, duration_s: float) -> Iterable[StepResult]:
        if not self._started:
            self.initialize()
        steps = int(round(duration_s / self.clock.dt_s))
        for _ in range(steps):
            yield self.step()

    # -- introspection ---------------------------------------------------
    def health(self) -> list[dict[str, Any]]:
        return [dict(federate.health()) for federate in self.federates]

    def checkpoint(self) -> dict[str, Any]:
        return {
            "t_ns": self.clock.t_ns,
            "federates": [federate.checkpoint() for federate in self.federates],
        }

    def topology(self) -> list[dict[str, Any]]:
        return [{"name": f.name, "type": type(f).__name__, "order": f.order,
                 "phase_hint": Phase(min(8, f.order // 10)).name}
                for f in self.federates]
