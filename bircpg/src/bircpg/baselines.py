"""Coordination methods: the two proposed branches and baselines B1-B5 (Section 7.3).

Every method implements the same interface and is handed the same frozen stage
game, the same feasible action sets, the same player scheduler, the same
evaluation budget and the same trace access.  That is the point of Section 7.3:
the comparators differ in *one* declared respect each, so an observed difference
can be attributed to the component whose removal changed it.

Informational advantages are labelled, not hidden.  ``B4`` is given correct
current payoff differences and reports ``uses_true_payoffs = True``; it is
useful for measuring the price of uncertainty, not as a deployable
low-communication method under packet loss.  ``B5`` reports whether its answer
is an exact optimum or a heuristic, and a heuristic answer must never be used to
manufacture an exact price of anarchy.
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field
from typing import Dict, List, Mapping, Optional, Sequence, Tuple

from .equilibria import improvement_path, welfare_maximiser
from .estimation import PayoffEstimator, uncertainty_gated_sweep
from .game import Action, OUTSIDE, TaskAllocationGame
from .logit import run_logit_episode
from .traces import reference_distribution

__all__ = [
    "EpisodeContext",
    "EpisodeOutcome",
    "CoordinationMethod",
    "RobustImprovement",
    "ReferenceBiasedLogit",
    "IndependentGreedy",
    "TraceHeuristic",
    "ExactBestResponse",
    "CentralisedWelfare",
    "default_methods",
]


@dataclass
class EpisodeContext:
    """Everything an inner coordination episode is allowed to see."""

    trace: Sequence[float]            # frozen trace snapshot z (A2)
    rng: random.Random                # method-specific stream
    estimator: PayoffEstimator        # u_hat with its declared allowance delta
    update_budget: int                # inner-update cap, Table 3 default 5n
    evaluation_budget: Optional[int] = None
    epoch: int = 0
    kappa: float = 1.0
    epsilon_z: float = 0.1
    trace_age: int = 0


@dataclass
class EpisodeOutcome:
    """Result of one inner coordination episode."""

    profile: Tuple[Action, ...]
    updates: int = 0
    evaluations: int = 0
    terminated: str = "budget"        # "certified" | "budget" | "single-pass"
    true_gap_bound: Optional[float] = None
    notes: Dict[str, object] = field(default_factory=dict)

    @property
    def certified(self) -> bool:
        return self.terminated == "certified"


class CoordinationMethod:
    """Common interface.  ``uses_true_payoffs`` labels an oracle advantage."""

    name: str = "method"
    uses_true_payoffs: bool = False
    uses_trace: bool = False
    occupancy_sensitive: bool = True

    def references(
        self, game: TaskAllocationGame, ctx: EpisodeContext
    ) -> List[Mapping[Action, float]]:
        """Equation (10) references, frozen for the whole episode."""
        kappa = ctx.kappa if self.uses_trace else 0.0
        return [
            reference_distribution(game.action_sets[i], ctx.trace, kappa, ctx.epsilon_z)
            for i in range(game.n_agents)
        ]

    def coordinate(
        self, game: TaskAllocationGame, incumbent: Sequence[Action], ctx: EpisodeContext
    ) -> EpisodeOutcome:
        raise NotImplementedError


# ----------------------------------------------------------------------
# The two proposed branches of Algorithm 1, step 3.  They are alternatives
# and must not be combined without a fresh analysis.
# ----------------------------------------------------------------------
class RobustImprovement(CoordinationMethod):
    """Robust branch: uncertainty-gated improvement, Equation (8).

    Seeks a terminal certificate.  On a complete unchanged-context sweep with no
    accepted switch, the true unilateral gain is at most ``4 delta_i + theta``.
    """

    def __init__(self, theta: float = 0.0, use_trace: bool = False) -> None:
        self.theta = theta
        self.uses_trace = use_trace
        self.name = "proposed-robust"

    def coordinate(self, game, incumbent, ctx) -> EpisodeOutcome:
        sweep = uncertainty_gated_sweep(
            game,
            incumbent,
            ctx.estimator,
            theta=self.theta,
            evaluation_budget=ctx.evaluation_budget,
        )
        return EpisodeOutcome(
            profile=sweep.profile,
            updates=len(sweep.switches),
            evaluations=sweep.evaluations,
            terminated=sweep.terminated,
            true_gap_bound=sweep.true_gap_bound,
            notes={"sweeps": sweep.sweeps},
        )


class ReferenceBiasedLogit(CoordinationMethod):
    """Logit branch: Equation (11) with trace-derived references (Equation 10).

    Deliberately permits payoff-decreasing moves, so it never returns a
    certificate.  With ``use_trace=False`` this is exactly baseline B2
    (uniform-reference logit), the primary comparator for the incremental effect
    of Equation (10).
    """

    def __init__(self, tau: float = 0.1, use_trace: bool = True) -> None:
        self.tau = tau
        self.uses_trace = use_trace
        self.name = "proposed-logit" if use_trace else "B2-uniform-logit"

    def coordinate(self, game, incumbent, ctx) -> EpisodeOutcome:
        refs = self.references(game, ctx)
        # The agent revises on its own estimates, never on evaluator-side truth.
        estimate = lambda i, profile: ctx.estimator.evaluate(game, i, profile)
        run = run_logit_episode(
            game, incumbent, refs, self.tau, ctx.update_budget, ctx.rng,
            payoff=estimate,
        )
        # Each logit update evaluates every feasible action of the selected agent;
        # those evaluations are charged to the episode's coordination allowance.
        mean_actions = sum(len(a) for a in game.action_sets) / game.n_agents
        evaluations = int(round(ctx.update_budget * mean_actions))
        return EpisodeOutcome(
            profile=run.profiles[-1],
            updates=ctx.update_budget,
            evaluations=evaluations,
            terminated="budget",
            notes={"mean_gap": run.mean_gap(burn_in=len(run.gaps) // 2)},
        )


# ----------------------------------------------------------------------
# Baselines B1-B5
# ----------------------------------------------------------------------
class IndependentGreedy(CoordinationMethod):
    """B1: each agent takes the best feasible action assuming it alone gets ``V_j``.

    Deliberately omits strategic occupancy.  A diagnostic baseline, not the sole
    comparator.
    """

    name = "B1-independent-greedy"
    occupancy_sensitive = False

    def coordinate(self, game, incumbent, ctx) -> EpisodeOutcome:
        profile: List[Action] = []
        evaluations = 0
        for i in range(game.n_agents):
            best, best_score = OUTSIDE, 0.0
            for a in game.action_sets[i]:
                evaluations += 1
                if a.is_outside:
                    continue
                task = game.tasks[a.task]
                score = float(task.value) - float(task.congestion(1)) - float(game.d(i, a))
                if score > best_score:
                    best, best_score = a, score
            profile.append(best)
        return EpisodeOutcome(
            profile=tuple(profile),
            updates=game.n_agents,
            evaluations=evaluations,
            terminated="single-pass",
        )


class TraceHeuristic(CoordinationMethod):
    """B3: trace-guided selection without the congestion game.

    Retains the same trace access and resource accounting, but scores tasks by
    trace strength and private cost with no occupancy-sensitive reward sharing.
    Isolates the game-theoretic component from environmental signalling alone.
    """

    name = "B3-trace-heuristic"
    uses_trace = True
    occupancy_sensitive = False

    def coordinate(self, game, incumbent, ctx) -> EpisodeOutcome:
        profile: List[Action] = []
        evaluations = 0
        for i in range(game.n_agents):
            best, best_score = OUTSIDE, 0.0
            for a in game.action_sets[i]:
                evaluations += 1
                if a.is_outside:
                    continue
                task = game.tasks[a.task]
                score = (
                    float(task.value)
                    - float(task.congestion(1))
                    + ctx.kappa * float(ctx.trace[a.task])
                    - float(game.d(i, a))
                )
                if score > best_score:
                    best, best_score = a, score
            profile.append(best)
        return EpisodeOutcome(
            profile=tuple(profile),
            updates=game.n_agents,
            evaluations=evaluations,
            terminated="single-pass",
        )


class ExactBestResponse(CoordinationMethod):
    """B4: asynchronous best response with exact payoff differences.

    An oracle-information comparator.  Its informational advantage is declared
    through ``uses_true_payoffs``; under packet loss it is not a deployable
    low-communication method.
    """

    name = "B4-exact-best-response"
    uses_true_payoffs = True

    def coordinate(self, game, incumbent, ctx) -> EpisodeOutcome:
        path = improvement_path(game, incumbent, max_switches=ctx.update_budget)
        evaluations = sum(len(game.action_sets[i]) for i in range(game.n_agents)) * path.sweeps
        return EpisodeOutcome(
            profile=path.final,
            updates=path.length,
            evaluations=evaluations,
            terminated=path.terminated,
            true_gap_bound=0.0 if path.certified else None,
            notes={"sweeps": path.sweeps},
        )


class CentralisedWelfare(CoordinationMethod):
    """B5: centralised welfare benchmark, Equation (4).

    Exhaustive enumeration while ``|A|`` stays within ``max_profiles``; otherwise
    a greedy marginal-welfare heuristic whose optimality status is reported as
    ``"heuristic"``.  A heuristic solution is not ``W*`` and must not be used to
    manufacture an exact price of anarchy.
    """

    name = "B5-centralised-welfare"
    uses_true_payoffs = True

    def __init__(self, max_profiles: int = 200_000) -> None:
        self.max_profiles = max_profiles

    def coordinate(self, game, incumbent, ctx) -> EpisodeOutcome:
        if game.profile_count <= self.max_profiles:
            profile, _ = welfare_maximiser(game)
            return EpisodeOutcome(
                profile=profile,
                updates=1,
                evaluations=game.profile_count,
                terminated="single-pass",
                notes={"optimality": "exact", "profiles_enumerated": game.profile_count},
            )
        profile = [OUTSIDE] * game.n_agents
        evaluations = 0
        improved = True
        while improved:
            improved = False
            best = None
            base = game.welfare(profile)
            for i in range(game.n_agents):
                for a in game.action_sets[i]:
                    if a == profile[i]:
                        continue
                    evaluations += 1
                    gain = game.welfare(game.replace(profile, i, a)) - base
                    if gain > 0 and (best is None or gain > best[0]):
                        best = (gain, i, a)
            if best is not None:
                _, i, a = best
                profile = list(game.replace(profile, i, a))
                improved = True
        return EpisodeOutcome(
            profile=tuple(profile),
            updates=1,
            evaluations=evaluations,
            terminated="single-pass",
            notes={"optimality": "heuristic", "profiles_enumerated": 0},
        )


def default_methods(tau: float = 0.1, theta: float = 0.0) -> List[CoordinationMethod]:
    """The comparison set of Section 7.3, with both proposed branches."""
    return [
        RobustImprovement(theta=theta),
        ReferenceBiasedLogit(tau=tau, use_trace=True),
        IndependentGreedy(),
        ReferenceBiasedLogit(tau=tau, use_trace=False),   # B2
        TraceHeuristic(),
        ExactBestResponse(),
        CentralisedWelfare(),
    ]
