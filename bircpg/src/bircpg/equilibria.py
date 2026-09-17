"""Section 5.1: exact potential, pure equilibria, finite improvement paths.

Proposition 1 (exact potential) and Corollary 1 (existence and finite
improvement) are *verified* here rather than assumed: :func:`verify_exact_potential`
checks Equation (6) on every feasible unilateral deviation from every feasible
profile.  With :class:`fractions.Fraction` inputs the residual is exactly zero,
which is the Level I check demanded by Section 7.1.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from fractions import Fraction
from typing import Callable, List, Optional, Sequence, Tuple

from .game import Action, TaskAllocationGame

__all__ = [
    "PotentialCheck",
    "ImprovementPath",
    "verify_exact_potential",
    "enumerate_profiles",
    "pure_nash_equilibria",
    "welfare_maximiser",
    "potential_maximiser",
    "price_of_anarchy",
    "improvement_path",
]


@dataclass
class PotentialCheck:
    """Outcome of the Equation (6) identity check (Proposition 1)."""

    profiles_checked: int
    deviations_checked: int
    max_residual: object
    worst_case: Optional[Tuple[Tuple[Action, ...], int, Action]] = None

    @property
    def exact(self) -> bool:
        """True when every residual is identically zero."""
        return self.max_residual == 0

    def __str__(self) -> str:  # pragma: no cover - cosmetic
        verdict = "exact" if self.exact else f"max residual {float(self.max_residual):.3e}"
        return (
            f"Equation (6) checked on {self.deviations_checked} deviations "
            f"from {self.profiles_checked} profiles: {verdict}"
        )


def verify_exact_potential(
    game: TaskAllocationGame, active_only: bool = False
) -> PotentialCheck:
    """Check ``Phi(b_i,a_-i) - Phi(a_i,a_-i) == u_i(b_i,a_-i) - u_i(a_i,a_-i)``.

    Parameters
    ----------
    active_only:
        Restrict the sweep to changes *between active profiles*: neither the
        starting profile nor the deviation may use the outside action.  The
        full sweep (default) also covers entry from and exit to the outside
        action, which is the case distinguished separately in the proof of
        Proposition 1.
    """
    source = game.active_profiles() if active_only else game.profiles()
    n_profiles = 0
    n_deviations = 0
    max_residual = 0
    worst: Optional[Tuple[Tuple[Action, ...], int, Action]] = None
    for profile in source:
        n_profiles += 1
        phi_a = game.potential(profile)
        for i in range(game.n_agents):
            u_a = game.payoff(i, profile)
            for b_i in game.action_sets[i]:
                if b_i == profile[i]:
                    continue
                if active_only and b_i.is_outside:
                    continue
                n_deviations += 1
                deviated = game.replace(profile, i, b_i)
                residual = (game.potential(deviated) - phi_a) - (
                    game.payoff(i, deviated) - u_a
                )
                magnitude = abs(residual)
                if magnitude > max_residual:
                    max_residual = magnitude
                    worst = (tuple(profile), i, b_i)
    return PotentialCheck(n_profiles, n_deviations, max_residual, worst)


def enumerate_profiles(game: TaskAllocationGame, active_only: bool = False) -> List[dict]:
    """Full Level I enumeration: payoffs, welfare, potential and Nash gap.

    Returns one record per profile.  ``|A|`` grows multiplicatively, so this is
    for the exact-enumeration regime only (Section 7.1 suggests ``n <= 6``).
    """
    source = game.active_profiles() if active_only else game.profiles()
    records = []
    for profile in source:
        profile = tuple(profile)
        records.append(
            {
                "profile": profile,
                "payoffs": game.payoffs(profile),
                "welfare": game.welfare(profile),
                "potential": game.potential(profile),
                "nash_gap": game.nash_gap(profile),
                "is_pne": game.nash_gap(profile) <= 0,
            }
        )
    return records


def pure_nash_equilibria(
    game: TaskAllocationGame, active_only: bool = False
) -> List[Tuple[Action, ...]]:
    """Every pure-strategy Nash equilibrium, by complete enumeration."""
    source = game.active_profiles() if active_only else game.profiles()
    return [tuple(a) for a in source if game.nash_gap(a) <= 0]


def welfare_maximiser(
    game: TaskAllocationGame, active_only: bool = False
) -> Tuple[Tuple[Action, ...], object]:
    """``W* = max_a W(a)`` and an argmax (the social comparator of Section 4.2)."""
    best, best_value = None, None
    for profile in (game.active_profiles() if active_only else game.profiles()):
        value = game.welfare(profile)
        if best_value is None or value > best_value:
            best, best_value = tuple(profile), value
    return best, best_value


def potential_maximiser(
    game: TaskAllocationGame, active_only: bool = False
) -> Tuple[Tuple[Action, ...], object]:
    """A maximiser of Equation (5).  It is a pure Nash equilibrium (Corollary 1)."""
    best, best_value = None, None
    for profile in (game.active_profiles() if active_only else game.profiles()):
        value = game.potential(profile)
        if best_value is None or value > best_value:
            best, best_value = tuple(profile), value
    return best, best_value


def price_of_anarchy(
    game: TaskAllocationGame, active_only: bool = False
) -> Optional[object]:
    """``W* / min_{a in PNE} W(a)`` for the enumerated pure-equilibrium class.

    Returns ``None`` when the denominator is not strictly positive.  Section 6
    is explicit that this ratio is a property of the instance, never a
    universal bound for the model class; use :func:`welfare_gap` reasoning
    (the additive loss ``W* - W(a)``) when the denominator is nonpositive.
    """
    equilibria = pure_nash_equilibria(game, active_only=active_only)
    if not equilibria:
        return None
    worst = min(game.welfare(a) for a in equilibria)
    if worst <= 0:
        return None
    _, optimum = welfare_maximiser(game, active_only=active_only)
    return optimum / worst


@dataclass
class ImprovementPath:
    """Record of a strict unilateral improvement path (Corollary 1)."""

    profiles: List[Tuple[Action, ...]] = field(default_factory=list)
    potentials: List[object] = field(default_factory=list)
    switches: List[Tuple[int, Action, Action]] = field(default_factory=list)
    terminated: str = "certified"  # "certified" | "budget"
    sweeps: int = 0

    @property
    def length(self) -> int:
        return len(self.switches)

    @property
    def final(self) -> Tuple[Action, ...]:
        return self.profiles[-1]

    @property
    def certified(self) -> bool:
        """True only after a complete unchanged-context sweep found no deviation."""
        return self.terminated == "certified"


def improvement_path(
    game: TaskAllocationGame,
    start: Sequence[Action],
    max_switches: Optional[int] = None,
    order: Optional[Callable[[int], Sequence[int]]] = None,
) -> ImprovementPath:
    """Run strict payoff-improving unilateral switches to termination.

    One player revises at a time (assumption A4).  The potential strictly
    increases at every accepted switch, so no profile can recur and the path is
    finite; the crude bound is ``|A| - 1`` accepted switches, which is finite
    but *not* a claim of polynomial-time efficiency.

    Termination is reported honestly: ``terminated == "certified"`` only after a
    complete sweep over all agents found no profitable deviation.  Exhausting
    ``max_switches`` yields ``terminated == "budget"``, which certifies nothing.
    """
    profile = tuple(start)
    path = ImprovementPath(profiles=[profile], potentials=[game.potential(profile)])
    order = order or (lambda _: range(game.n_agents))
    while True:
        improved = False
        path.sweeps += 1
        for i in order(path.sweeps):
            u_i = game.payoff(i, profile)
            best_action, best_value = None, u_i
            for b_i, value in game.deviations(i, profile):
                if value > best_value:
                    best_action, best_value = b_i, value
            if best_action is None:
                continue
            if max_switches is not None and path.length >= max_switches:
                path.terminated = "budget"
                return path
            old = profile[i]
            profile = game.replace(profile, i, best_action)
            path.switches.append((i, old, best_action))
            path.profiles.append(profile)
            path.potentials.append(game.potential(profile))
            improved = True
        if not improved:
            path.terminated = "certified"
            return path
