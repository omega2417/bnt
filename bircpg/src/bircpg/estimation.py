"""Section 5.2: bounded payoff-estimation error and uncertainty-gated updates.

Equation (7) states the assumption ``|u_hat_i(a) - u_i(a)| <= delta_i`` for the
frozen context and all relevant profiles.  Assumption A5 is emphatic that a
neural confidence output is *not* such a bound without calibration or
independent validation, so the estimator here carries its allowance explicitly
and :func:`coverage_report` exists to test whether a claimed allowance actually
holds against known truth.
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field
from typing import Callable, Dict, List, Optional, Sequence, Tuple

from .game import Action, TaskAllocationGame

__all__ = [
    "PayoffEstimator",
    "BoundedNoiseEstimator",
    "ExactEstimator",
    "GatedSweep",
    "approximate_equilibrium_certificate",
    "estimated_nash_gap",
    "uncertainty_gated_sweep",
    "coverage_report",
]


class PayoffEstimator:
    """Interface for ``u_hat_i`` together with its declared allowance ``delta_i``.

    Implementations must charge every call to ``evaluate`` against the episode's
    coordination allowance via :attr:`evaluations`; Section 4.1 requires
    inner-loop evaluations to be paid for, not treated as free information.
    """

    def __init__(self, delta: Sequence[float] | float, n_agents: int) -> None:
        if isinstance(delta, (int, float)):
            delta = [float(delta)] * n_agents
        if len(delta) != n_agents:
            raise ValueError("one error allowance delta_i per agent is required")
        if any(d < 0 for d in delta):
            raise ValueError("error allowances must be nonnegative")
        self.delta: List[float] = [float(d) for d in delta]
        self.evaluations = 0

    @property
    def delta_max(self) -> float:
        return max(self.delta) if self.delta else 0.0

    def evaluate(self, game: TaskAllocationGame, i: int, profile: Sequence[Action]) -> float:
        raise NotImplementedError


class ExactEstimator(PayoffEstimator):
    """``u_hat_i = u_i`` with ``delta_i = 0``: the analytical benchmark of A4."""

    def __init__(self, n_agents: int) -> None:
        super().__init__(0.0, n_agents)

    def evaluate(self, game: TaskAllocationGame, i: int, profile: Sequence[Action]) -> float:
        self.evaluations += 1
        return float(game.payoff(i, profile))


class BoundedNoiseEstimator(PayoffEstimator):
    """A deterministic-per-(agent, profile) estimator obeying Equation (7).

    The perturbation is drawn once per ``(i, profile)`` and cached, so repeated
    evaluations of the same quantity within a frozen episode are consistent --
    an estimator that re-randomises on every read would silently break the
    uniform bound that Proposition 2 assumes.  The magnitude never exceeds
    ``delta_i``, so the bound is satisfied by construction; that is a modelling
    convenience, not evidence that a real estimator is calibrated.
    """

    def __init__(
        self,
        delta: Sequence[float] | float,
        n_agents: int,
        rng: Optional[random.Random] = None,
        bias: Sequence[float] | float = 0.0,
    ) -> None:
        super().__init__(delta, n_agents)
        self.rng = rng or random.Random(0)
        if isinstance(bias, (int, float)):
            bias = [float(bias)] * n_agents
        self.bias = [float(b) for b in bias]
        for i, (b, d) in enumerate(zip(self.bias, self.delta)):
            if abs(b) > d:
                raise ValueError(
                    f"systematic bias {b} for agent {i} exceeds its allowance {d}; "
                    "Equation (7) would be violated"
                )
        self._cache: Dict[Tuple[int, Tuple[Action, ...]], float] = {}

    def evaluate(self, game: TaskAllocationGame, i: int, profile: Sequence[Action]) -> float:
        self.evaluations += 1
        key = (i, tuple(profile))
        if key not in self._cache:
            slack = self.delta[i] - abs(self.bias[i])
            self._cache[key] = self.bias[i] + self.rng.uniform(-slack, slack)
        return float(game.payoff(i, profile)) + self._cache[key]


def estimated_nash_gap(
    game: TaskAllocationGame, profile: Sequence[Action], estimator: PayoffEstimator
) -> float:
    """Equation (14) evaluated on the *estimated* game."""
    gap = 0.0
    for i in range(game.n_agents):
        u_i = estimator.evaluate(game, i, profile)
        for b_i in game.action_sets[i]:
            if b_i == profile[i]:
                continue
            value = estimator.evaluate(game, i, game.replace(profile, i, b_i))
            gap = max(gap, value - u_i)
    return gap


def approximate_equilibrium_certificate(eta: float, delta_max: float) -> float:
    """Proposition 2: an ``eta``-Nash equilibrium of the estimated game is an
    ``(eta + 2 delta_max)``-Nash equilibrium of the true stage game.

    No potential assumption is needed for this inequality.  The factor two here
    must not be confused with the factor four of the stopping certificate in
    :func:`uncertainty_gated_sweep`.
    """
    if eta < 0 or delta_max < 0:
        raise ValueError("eta and delta_max must be nonnegative")
    return eta + 2.0 * delta_max


@dataclass
class GatedSweep:
    """Result of an uncertainty-gated improvement episode (Equation 8)."""

    profile: Tuple[Action, ...]
    switches: List[Tuple[int, Action, Action]] = field(default_factory=list)
    evaluations: int = 0
    sweeps: int = 0
    terminated: str = "certified"          # "certified" | "budget"
    true_gap_bound: Optional[float] = None  # 4 delta_i + theta, when certified

    @property
    def certified(self) -> bool:
        return self.terminated == "certified"


def uncertainty_gated_sweep(
    game: TaskAllocationGame,
    start: Sequence[Action],
    estimator: PayoffEstimator,
    theta: float = 0.0,
    evaluation_budget: Optional[int] = None,
    order: Optional[Callable[[int], Sequence[int]]] = None,
) -> GatedSweep:
    """The robust branch of Algorithm 1, step 3.

    A switch is accepted only when the *estimated* gain satisfies Equation (8),
    ``u_hat_i(b_i, a_-i) - u_hat_i(a) > 2 delta_i + theta`` with ``theta >= 0``.
    The true gain then exceeds ``theta``, so the exact potential of Equation (5)
    increases and the path remains finite.

    If a complete unchanged-context sweep accepts no switch, the true unilateral
    gain is at most ``4 delta_i + theta`` for each agent -- reported as
    :attr:`GatedSweep.true_gap_bound`.  Exhausting ``evaluation_budget`` instead
    is recorded as a *budget-limited exit* and certifies nothing (Algorithm 1,
    step 4).
    """
    if theta < 0:
        raise ValueError("theta must be nonnegative (Equation 8)")
    profile = tuple(start)
    result = GatedSweep(profile=profile)
    order = order or (lambda _: range(game.n_agents))
    start_evals = estimator.evaluations
    while True:
        accepted_any = False
        result.sweeps += 1
        for i in order(result.sweeps):
            if evaluation_budget is not None and (
                estimator.evaluations - start_evals >= evaluation_budget
            ):
                result.terminated = "budget"
                result.profile = profile
                result.evaluations = estimator.evaluations - start_evals
                return result
            threshold = 2.0 * estimator.delta[i] + theta
            u_hat = estimator.evaluate(game, i, profile)
            chosen, best_gain = None, threshold
            for b_i in game.action_sets[i]:
                if b_i == profile[i]:
                    continue
                gain = estimator.evaluate(game, i, game.replace(profile, i, b_i)) - u_hat
                if gain > best_gain:
                    chosen, best_gain = b_i, gain
            if chosen is not None:
                old = profile[i]
                profile = game.replace(profile, i, chosen)
                result.switches.append((i, old, chosen))
                accepted_any = True
        if not accepted_any:
            result.terminated = "certified"
            result.profile = profile
            result.evaluations = estimator.evaluations - start_evals
            result.true_gap_bound = 4.0 * estimator.delta_max + theta
            return result


def coverage_report(
    game: TaskAllocationGame,
    estimator: PayoffEstimator,
    profiles: Sequence[Sequence[Action]],
) -> Dict[str, float]:
    """Calibration endpoint of Section 7.4.

    Compares the claimed allowance ``delta_i`` against realised errors on the
    supplied profiles and returns the empirical coverage rate.  Section 7.4 is
    explicit that an empirical coverage rate is *not* a deterministic uniform
    bound; the two are reported separately here for that reason.
    """
    covered = 0
    total = 0
    worst = 0.0
    worst_ratio = 0.0
    for profile in profiles:
        for i in range(game.n_agents):
            truth = float(game.payoff(i, profile))
            error = abs(estimator.evaluate(game, i, profile) - truth)
            total += 1
            worst = max(worst, error)
            if estimator.delta[i] > 0:
                worst_ratio = max(worst_ratio, error / estimator.delta[i])
            elif error > 0:
                worst_ratio = float("inf")
            if error <= estimator.delta[i] + 1e-12:
                covered += 1
    return {
        "n_checks": float(total),
        "empirical_coverage": covered / total if total else float("nan"),
        "max_abs_error": worst,
        "max_error_over_delta": worst_ratio,
        "declared_delta_max": estimator.delta_max,
    }
