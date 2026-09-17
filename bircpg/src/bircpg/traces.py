"""Section 5.3: environmental traces and the frozen reference distribution.

Equation (9) is the between-epoch trace update
``z_j(t+1) = (1 - rho) z_j(t) + rho s_j(t)`` with ``0 < rho <= 1``, where
``s_j(t) in [0, 1]`` is the mean of verified reports from that epoch, or zero
when no report is received.  Equation (10) freezes ``z`` and builds a positive
reference distribution on each agent's feasible set.

This is a *designed information mechanism*.  It is not a claim that real insects
implement Equation (9), and reading or writing a trace is not free
communication (Section 7.4) -- the access cost belongs in ``k_i`` of Equation (2).
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Dict, List, Mapping, Optional, Sequence

from .game import Action

__all__ = ["TraceField", "reference_distribution"]


@dataclass
class TraceField:
    """The environmental trace ``z in [0, 1]^m`` with decay ``rho`` (Equation 9).

    Parameters
    ----------
    rho:
        Decay/learning rate, ``0 < rho <= 1``.  Table 3 lists levels
        ``rho in {0.05, 0.2, 0.5}``.
    delay:
        Number of epochs by which the *readable* trace lags the updated one.
        Table 3 lists added delays of 0, 1 and 5 epochs; H2 of Section 3 is the
        hypothesis that delayed or misleading traces reverse the advantage of
        H1, so the delay is a first-class experimental factor, not an artefact.
    """

    n_tasks: int
    rho: float = 0.2
    delay: int = 0
    z: List[float] = field(default_factory=list)
    epoch: int = 0
    _history: List[List[float]] = field(default_factory=list, repr=False)

    def __post_init__(self) -> None:
        if not 0.0 < self.rho <= 1.0:
            raise ValueError("Equation (9) requires 0 < rho <= 1")
        if self.delay < 0:
            raise ValueError("delay must be nonnegative")
        if not self.z:
            self.z = [0.0] * self.n_tasks
        if len(self.z) != self.n_tasks:
            raise ValueError("trace vector length must equal the number of tasks")
        self._history = [list(self.z)]

    def update(self, reports: Mapping[int, float]) -> None:
        """Apply Equation (9) once, between physical epochs.

        ``reports[j]`` is ``s_j(t)``, the mean of verified reports for task
        ``j``.  A task with no report is updated with ``s_j = 0``, exactly as
        stated in Section 5.3 -- that is decay towards zero, and it is the
        mechanism by which stale traces age.
        """
        for j in range(self.n_tasks):
            s_j = float(reports.get(j, 0.0))
            if not 0.0 <= s_j <= 1.0:
                raise ValueError(f"report s_{j} = {s_j} outside [0, 1]")
            self.z[j] = (1.0 - self.rho) * self.z[j] + self.rho * s_j
        self.epoch += 1
        self._history.append(list(self.z))

    def frozen(self) -> List[float]:
        """The trace snapshot readable by the current inner episode (A2).

        With ``delay = 0`` this is the current ``z``; otherwise it is the value
        from ``delay`` epochs ago, so the age of the information is explicit
        rather than hidden.
        """
        index = max(0, len(self._history) - 1 - self.delay)
        return list(self._history[index])

    @property
    def age(self) -> int:
        """Stale-information age in epochs (a robustness endpoint, Section 7.4)."""
        return min(self.delay, self.epoch)


def reference_distribution(
    actions: Sequence[Action],
    z: Sequence[float],
    kappa: float = 1.0,
    epsilon_z: float = 0.1,
) -> Dict[Action, float]:
    """Equation (10): ``q_i(b|z) = (1-eps) exp(kappa z_j(b)) / sum_c exp(kappa z_j(c)) + eps/|A_i|``.

    ``z_j(0) = 0`` is used for the outside action, as stated after Equation (10).
    The mixture weight ``epsilon_z in (0, 1]`` (Table 3 suggests ``0.1``)
    guarantees full support, which Proposition 3 requires; ``kappa in {0, 1, 3}``
    is the trace-strength factor of Table 3, and ``kappa = 0`` recovers the
    uniform reference used by baseline B2.

    The reference depends only on the frozen trace and the candidate action,
    never on the current inner-game profile -- that independence is what makes
    the detailed-balance argument of Proposition 3 go through.
    """
    if not actions:
        raise ValueError("cannot build a reference distribution on an empty A_i")
    if not 0.0 < epsilon_z <= 1.0:
        raise ValueError("Equation (10) requires 0 < epsilon_z <= 1")
    size = len(actions)
    scores = []
    for a in actions:
        z_j = 0.0 if a.is_outside else float(z[a.task])
        scores.append(kappa * z_j)
    shift = max(scores)
    weights = [math.exp(s - shift) for s in scores]
    total = sum(weights)
    return {
        a: (1.0 - epsilon_z) * w / total + epsilon_z / size
        for a, w in zip(actions, weights)
    }
