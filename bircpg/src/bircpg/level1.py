"""Level I (Section 7.1): exact verification of the finite-game identities.

Level I enumerates all feasible profiles for ``n in {2,...,6}`` and ``m in {2,3}``
with one active mode per task, including the outside action.  The largest
unrestricted combination in the manuscript contains ``4^6 = 4096`` profiles.
Thirty independently seeded cost/value instances per size combination are the
proposed starting set -- a starting set, not a completed experiment.

Instances are generated in exact rational arithmetic, so the Equation (6)
residual is either identically zero or a genuine defect; there is no tolerance
to hide behind.  Deliberate edge cases are included: ties, a single feasible
action, zero task value and heterogeneous resource masks.
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field
from fractions import Fraction
from typing import Dict, Iterator, List, Optional, Tuple

from .equilibria import (
    potential_maximiser,
    price_of_anarchy,
    pure_nash_equilibria,
    verify_exact_potential,
    welfare_maximiser,
)
from .game import Action, OUTSIDE, Task, TaskAllocationGame, linear_congestion, zero_congestion
from .logit import (
    detailed_balance_residual,
    potential_loss_bound,
    stationary_distribution,
    transition_matrix,
)
from .seeds import stream
from .traces import reference_distribution

__all__ = ["random_instance", "InstanceReport", "check_instance", "level1_sweep", "EDGE_CASES"]


def _fraction(rng: random.Random, low: int, high: int, denominator: int = 4) -> Fraction:
    return Fraction(rng.randint(low * denominator, high * denominator), denominator)


def random_instance(
    n_agents: int,
    n_tasks: int,
    seed: int,
    gamma_choices: Tuple[Fraction, ...] = (Fraction(0), Fraction(1, 20), Fraction(1, 5)),
    mask_probability: float = 0.0,
) -> TaskAllocationGame:
    """One seeded exact-arithmetic instance with one active mode per task.

    ``mask_probability`` removes individual actions from ``A_i``, producing the
    heterogeneous resource masks that Section 7.1 asks to be included.  The
    outside action is always retained, so ``A_i`` is never empty (assumption A1).
    """
    rng = stream("level1", n_agents, n_tasks, seed)
    tasks = [
        Task(
            value=_fraction(rng, 1, 3),
            congestion=(
                zero_congestion
                if (g := rng.choice(gamma_choices)) == 0
                else linear_congestion(g)
            ),
            name=f"T{j}",
        )
        for j in range(n_tasks)
    ]
    action_sets: List[List[Action]] = []
    private_cost: Dict[Tuple[int, Action], Fraction] = {}
    for i in range(n_agents):
        feasible: List[Action] = [OUTSIDE]
        for j in range(n_tasks):
            if mask_probability and rng.random() < mask_probability:
                continue
            action = Action(j, 0)
            feasible.append(action)
            private_cost[(i, action)] = _fraction(rng, 0, 1, denominator=8)
        action_sets.append(feasible)
    return TaskAllocationGame(
        tasks=tasks,
        action_sets=action_sets,
        private_cost=private_cost,
        label=f"level1/n={n_agents}/m={n_tasks}/seed={seed}",
    )


EDGE_CASES: Tuple[str, ...] = (
    "ties",              # identical agents and tasks: many equal-payoff profiles
    "single_action",     # an agent whose only feasible action is the fallback
    "zero_value",        # a task with V_j = 0
    "masked",            # heterogeneous resource masks
)


def edge_case_instance(kind: str) -> TaskAllocationGame:
    """Deliberate edge cases required by Section 7.1."""
    if kind == "ties":
        tasks = [Task(Fraction(2), zero_congestion, "T0"), Task(Fraction(2), zero_congestion, "T1")]
        acts = [Action(0, 0), Action(1, 0)]
        action_sets = [list(acts) + [OUTSIDE] for _ in range(3)]
        cost = {(i, a): Fraction(1, 2) for i in range(3) for a in acts}
    elif kind == "single_action":
        tasks = [Task(Fraction(3), linear_congestion(Fraction(1, 10)), "T0")]
        action_sets = [[Action(0, 0), OUTSIDE], [OUTSIDE]]
        cost = {(0, Action(0, 0)): Fraction(1, 4)}
    elif kind == "zero_value":
        tasks = [Task(Fraction(0), zero_congestion, "T0"), Task(Fraction(5, 2), zero_congestion, "T1")]
        acts = [Action(0, 0), Action(1, 0)]
        action_sets = [list(acts) + [OUTSIDE] for _ in range(2)]
        cost = {(i, a): Fraction(1, 8) for i in range(2) for a in acts}
    elif kind == "masked":
        tasks = [
            Task(Fraction(4), linear_congestion(Fraction(1, 5)), "T0"),
            Task(Fraction(3), zero_congestion, "T1"),
        ]
        action_sets = [
            [Action(0, 0), OUTSIDE],
            [Action(1, 0), OUTSIDE],
            [Action(0, 0), Action(1, 0), OUTSIDE],
        ]
        cost = {
            (0, Action(0, 0)): Fraction(1, 2),
            (1, Action(1, 0)): Fraction(1, 4),
            (2, Action(0, 0)): Fraction(3, 4),
            (2, Action(1, 0)): Fraction(1, 8),
        }
    else:
        raise ValueError(f"unknown edge case {kind!r}")
    return TaskAllocationGame(tasks, action_sets, cost, label=f"level1/edge/{kind}")


@dataclass
class InstanceReport:
    """Everything Level I asks to be computed for one instance."""

    label: str
    n_agents: int
    n_tasks: int
    profiles: int
    potential_residual: object
    potential_exact: bool
    n_pure_equilibria: int
    welfare_optimum: object
    best_equilibrium_welfare: Optional[object]
    worst_equilibrium_welfare: Optional[object]
    additive_welfare_loss: Optional[object]
    price_of_anarchy: Optional[object]
    potential_maximiser_is_pne: bool
    max_nash_gap: object
    chain: Optional[Dict[str, float]] = None
    notes: Dict[str, object] = field(default_factory=dict)


def check_instance(
    game: TaskAllocationGame,
    chain_tau: Optional[float] = None,
    chain_limit: int = 256,
) -> InstanceReport:
    """Run the full Level I battery on one instance.

    When ``chain_tau`` is given and the state space is small enough, the exact
    transition matrix of Equation (11) is built and checked for stochasticity,
    detailed balance and the stationary residual -- reported separately, as
    Section 7.1 requires.  A stationary-law check is not a finite-time
    convergence study.
    """
    check = verify_exact_potential(game)
    equilibria = pure_nash_equilibria(game)
    _, optimum = welfare_maximiser(game)
    phi_argmax, _ = potential_maximiser(game)
    eq_welfare = sorted(game.welfare(a) for a in equilibria)
    report = InstanceReport(
        label=game.label,
        n_agents=game.n_agents,
        n_tasks=game.n_tasks,
        profiles=game.profile_count,
        potential_residual=check.max_residual,
        potential_exact=check.exact,
        n_pure_equilibria=len(equilibria),
        welfare_optimum=optimum,
        best_equilibrium_welfare=eq_welfare[-1] if eq_welfare else None,
        worst_equilibrium_welfare=eq_welfare[0] if eq_welfare else None,
        additive_welfare_loss=(optimum - eq_welfare[0]) if eq_welfare else None,
        price_of_anarchy=price_of_anarchy(game),
        potential_maximiser_is_pne=game.nash_gap(phi_argmax) <= 0,
        max_nash_gap=max((game.nash_gap(a) for a in game.profiles()), default=0),
    )
    if chain_tau is not None and game.profile_count <= chain_limit:
        refs = [
            reference_distribution(game.action_sets[i], [0.0] * game.n_tasks, 0.0, 1.0)
            for i in range(game.n_agents)
        ]
        profiles, P = transition_matrix(game, refs, chain_tau)
        pi = stationary_distribution(game, refs, chain_tau)
        residuals = detailed_balance_residual(profiles, P, pi)
        residuals.update(potential_loss_bound(game, refs, chain_tau))
        report.chain = residuals
    return report


def level1_sweep(
    agent_counts: Tuple[int, ...] = (2, 3, 4, 5),
    task_counts: Tuple[int, ...] = (2, 3),
    seeds: int = 30,
    mask_probability: float = 0.25,
    chain_tau: Optional[float] = 0.5,
) -> List[InstanceReport]:
    """The Level I study: seeded instances plus the deliberate edge cases.

    The manuscript proposes ``n in {2,...,6}`` and 30 seeds per size; the
    defaults here stop at ``n = 5`` so that a full sweep stays interactive in a
    notebook.  Raising ``agent_counts`` is the only change needed to run the
    proposed set -- the cost is enumeration, which grows multiplicatively.
    """
    reports: List[InstanceReport] = []
    for n in agent_counts:
        for m in task_counts:
            for seed in range(seeds):
                game = random_instance(n, m, seed, mask_probability=mask_probability)
                reports.append(check_instance(game, chain_tau=chain_tau))
    for kind in EDGE_CASES:
        reports.append(check_instance(edge_case_instance(kind), chain_tau=chain_tau))
    return reports
