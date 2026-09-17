"""Section 6: the constructed two-agent example.

Two agents, two tasks A and B, one controller mode, no congestion penalty.
``V_A = 8``, ``V_B = 6``, private costs ``d_1(A) = 1``, ``d_1(B) = 2``,
``d_2(A) = 2``, ``d_2(B) = 1``.

This is an exact arithmetic illustration, not a simulation study and not a
measurement.  It is built with :class:`fractions.Fraction` so that Table 2, the
Equation (6) identity and the price-of-anarchy ratio are reproduced exactly
rather than to floating-point tolerance.
"""

from __future__ import annotations

from fractions import Fraction
from typing import Dict, List, Tuple

from .game import Action, OUTSIDE, Task, TaskAllocationGame, zero_congestion
from .equilibria import (
    enumerate_profiles,
    price_of_anarchy,
    pure_nash_equilibria,
    verify_exact_potential,
    welfare_maximiser,
)
from .logit import stationary_distribution
from .traces import reference_distribution

__all__ = [
    "TASK_NAMES",
    "A1",
    "B1",
    "build_game",
    "table2",
    "format_table2",
    "equation15",
    "stationary_by_temperature",
    "summary",
]

TASK_NAMES = ("A", "B")

#: The two active actions.  A single controller mode is used, so the mode index
#: is fixed at 0 and plays no role in this example.
A1 = Action(0, 0)
B1 = Action(1, 0)


def build_game() -> TaskAllocationGame:
    """The stage game of Section 6, in exact rational arithmetic.

    The outside action has payoff zero.  It does not add an equilibrium,
    because every displayed active payoff is positive and an inactive agent can
    profitably enter.  Table 2 and Equation (15) concern the four-profile
    *active-action subgame*, obtained everywhere in this package by passing
    ``active_only=True``; adding the outside action changes the state space and
    therefore those probabilities.
    """
    tasks = [
        Task(value=Fraction(8), congestion=zero_congestion, name="A"),
        Task(value=Fraction(6), congestion=zero_congestion, name="B"),
    ]
    action_sets = [[A1, B1, OUTSIDE] for _ in range(2)]
    private_cost = {
        (0, A1): Fraction(1),
        (0, B1): Fraction(2),
        (1, A1): Fraction(2),
        (1, B1): Fraction(1),
    }
    return TaskAllocationGame(
        tasks=tasks,
        action_sets=action_sets,
        private_cost=private_cost,
        label="Section 6 constructed example",
    )


def _name(profile) -> str:
    return "(" + ", ".join("0" if a.is_outside else TASK_NAMES[a.task] for a in profile) + ")"


def table2() -> List[Dict[str, object]]:
    """Reproduce Table 2: exact enumeration of the four active profiles."""
    game = build_game()
    rows = []
    for record in enumerate_profiles(game, active_only=True):
        rows.append(
            {
                "profile": _name(record["profile"]),
                "u_1": record["payoffs"][0],
                "u_2": record["payoffs"][1],
                "welfare": record["welfare"],
                "potential": record["potential"],
                "nash_gap": record["nash_gap"],
                "is_pne": record["is_pne"],
            }
        )
    return rows


def format_table2() -> str:
    """Table 2 as plain text.  All values are hypothetical utility units."""
    rows = table2()
    header = f"{'Profile':>10} {'u_1':>6} {'u_2':>6} {'W(a)':>6} {'Phi(a)':>7} {'Gap':>5}  PNE"
    lines = [header, "-" * len(header)]
    for r in rows:
        lines.append(
            f"{r['profile']:>10} {str(r['u_1']):>6} {str(r['u_2']):>6} "
            f"{str(r['welfare']):>6} {str(r['potential']):>7} {str(r['nash_gap']):>5}"
            f"  {'Yes' if r['is_pne'] else 'No'}"
        )
    return "\n".join(lines)


def _uniform_references(game) -> List[Dict[Action, float]]:
    """Uniform references on the active subgame (``kappa = 0``, ``epsilon_z = 1``)."""
    return [
        reference_distribution([A1, B1], z=[0.0, 0.0], kappa=0.0, epsilon_z=1.0)
        for _ in range(game.n_agents)
    ]


def equation15(tau: float = 1.0) -> Dict[str, float]:
    """Equation (15): stationary probabilities of the active-action subgame.

    With uniform references and ``tau = 1`` these follow by normalising
    ``exp(9)``, ``exp(12)``, ``exp(10)`` and ``exp(6)``, giving approximately
    ``0.04192, 0.84203, 0.11396, 0.00209``.  Adding the outside action changes
    the state space and therefore these numbers.
    """
    game = build_game()
    pi = stationary_distribution(game, _uniform_references(game), tau, active_only=True)
    return {_name(a): p for a, p in pi.items()}


def stationary_by_temperature(taus) -> Dict[str, List[float]]:
    """Figure 3b: the Equation (12) law across temperatures.

    As ``tau`` decreases the mass concentrates on the potential maximiser
    ``(A, B)``; at larger ``tau`` every profile, including the two
    non-equilibria, retains appreciable probability.
    """
    game = build_game()
    refs = _uniform_references(game)
    series: Dict[str, List[float]] = {}
    for tau in taus:
        pi = stationary_distribution(game, refs, float(tau), active_only=True)
        for a, p in pi.items():
            series.setdefault(_name(a), []).append(p)
    return series


def summary() -> Dict[str, object]:
    """Every Section 6 claim, recomputed."""
    game = build_game()
    check = verify_exact_potential(game, active_only=False)
    equilibria = pure_nash_equilibria(game, active_only=True)
    _, optimum = welfare_maximiser(game, active_only=True)
    equilibrium_welfare = sorted(game.welfare(a) for a in equilibria)
    return {
        "table2": table2(),
        "potential_identity_exact": check.exact,
        "deviations_checked": check.deviations_checked,
        "pure_equilibria": [_name(a) for a in equilibria],
        "equilibrium_welfare": equilibrium_welfare,
        "welfare_optimum": optimum,
        "additive_welfare_loss": optimum - equilibrium_welfare[0],
        "price_of_anarchy": price_of_anarchy(game, active_only=True),
        "equation15": equation15(1.0),
    }
