"""Section 5.3: frozen-trace, reference-biased logit learning.

Equation (11) is the revision rule, Equation (12) its stationary law, and
Corollary 2 (Equation 13) the potential-loss bound.  Proposition 3 holds under
A1-A4 with *positive fixed* player-selection probabilities, *exact* payoffs and
*frozen full-support* references.  Every one of those conditions is checked or
made explicit below, because dropping any of them removes the guarantee.

A stationary law is not a finite-time mixing bound, and the joint stationary
distribution is not automatically a quantal-response or correlated equilibrium;
at positive temperature, profiles that are not Nash equilibria keep positive
mass.  :func:`stationary_distribution` therefore returns a distribution, never a
"converged equilibrium".
"""

from __future__ import annotations

import math
import random
from dataclasses import dataclass
from typing import Callable, Dict, List, Mapping, Optional, Sequence, Tuple

from .game import Action, TaskAllocationGame

__all__ = [
    "logit_choice_probabilities",
    "sample_logit_action",
    "transition_matrix",
    "stationary_distribution",
    "detailed_balance_residual",
    "potential_loss_bound",
    "expected_potential",
    "LogitRun",
    "run_logit_episode",
]


def logit_choice_probabilities(
    game: TaskAllocationGame,
    i: int,
    profile: Sequence[Action],
    reference: Mapping[Action, float],
    tau: float,
    payoff: Optional[Callable[[int, Sequence[Action]], float]] = None,
) -> Dict[Action, float]:
    """Equation (11), the reference-biased logit rule for the selected agent ``i``.

    ``tau > 0`` is a *behavioural* temperature, not processor temperature.  A
    uniform reference recovers the standard conditional logit form.

    ``payoff`` supplies the values the agent actually revises on.  It defaults to
    the true ``u_i``, which is what Proposition 3 assumes; a deployed agent under
    observation noise must pass its own estimator here instead, or it would be
    querying the evaluator as a hidden oracle.  Proposition 3 does **not** cover
    that case -- with estimated payoffs the stationary law of Equation (12) is no
    longer the chain's invariant distribution.
    """
    if tau <= 0:
        raise ValueError("Equation (11) requires tau > 0")
    actions = list(game.action_sets[i])
    scores = []
    for b in actions:
        q_b = reference[b]
        if q_b <= 0:
            raise ValueError(
                "Proposition 3 requires full-support references; "
                f"q_i({b}) = {q_b}"
            )
        deviated = game.replace(profile, i, b)
        u_b = float(payoff(i, deviated)) if payoff else float(game.payoff(i, deviated))
        scores.append(math.log(q_b) + u_b / tau)
    shift = max(scores)
    weights = [math.exp(s - shift) for s in scores]
    total = sum(weights)
    return {a: w / total for a, w in zip(actions, weights)}


def sample_logit_action(
    game: TaskAllocationGame,
    i: int,
    profile: Sequence[Action],
    reference: Mapping[Action, float],
    tau: float,
    rng: random.Random,
    payoff: Optional[Callable[[int, Sequence[Action]], float]] = None,
) -> Action:
    """Draw one action from Equation (11)."""
    probs = logit_choice_probabilities(game, i, profile, reference, tau, payoff)
    items = list(probs.items())
    r = rng.random()
    acc = 0.0
    for action, p in items:
        acc += p
        if r <= acc:
            return action
    return items[-1][0]


def transition_matrix(
    game: TaskAllocationGame,
    references: Sequence[Mapping[Action, float]],
    tau: float,
    selection: Optional[Sequence[float]] = None,
    active_only: bool = False,
):
    """Exact asynchronous transition matrix of the Equation (11) chain.

    ``selection[i]`` are the *positive, state-independent* player-selection
    probabilities required by A4; they default to uniform.  Section 7.1 asks for
    this construction on sufficiently small state spaces only.

    Returns ``(profiles, P)`` where ``P`` is a list of rows.
    """
    n = game.n_agents
    if selection is None:
        selection = [1.0 / n] * n
    if len(selection) != n or any(p <= 0 for p in selection):
        raise ValueError("player-selection probabilities must be positive, one per agent")
    total = sum(selection)
    selection = [p / total for p in selection]

    profiles = [tuple(a) for a in (game.active_profiles() if active_only else game.profiles())]
    index = {p: k for k, p in enumerate(profiles)}
    size = len(profiles)
    P = [[0.0] * size for _ in range(size)]
    for row, profile in enumerate(profiles):
        for i in range(n):
            probs = logit_choice_probabilities(game, i, profile, references[i], tau)
            for b, p_b in probs.items():
                target = game.replace(profile, i, b)
                if target not in index:  # restricted subgame
                    continue
                P[row][index[target]] += selection[i] * p_b
    return profiles, P


def stationary_distribution(
    game: TaskAllocationGame,
    references: Sequence[Mapping[Action, float]],
    tau: float,
    active_only: bool = False,
) -> Dict[Tuple[Action, ...], float]:
    """Equation (12): ``pi_tau(a) = Z^-1 exp(Phi(a)/tau) prod_i q_i(a_i|z)``.

    Evaluated in closed form from the potential, so it is exact up to floating
    point.  :func:`detailed_balance_residual` checks it against the transition
    matrix independently, which is the Level I cross-check of Section 7.1.
    """
    if tau <= 0:
        raise ValueError("Equation (12) requires tau > 0")
    profiles = [tuple(a) for a in (game.active_profiles() if active_only else game.profiles())]
    log_weights = []
    for profile in profiles:
        log_w = float(game.potential(profile)) / tau
        for i, a_i in enumerate(profile):
            q = references[i][a_i]
            if q <= 0:
                raise ValueError("Equation (12) requires full-support references")
            log_w += math.log(q)
        log_weights.append(log_w)
    shift = max(log_weights)
    weights = [math.exp(w - shift) for w in log_weights]
    Z = sum(weights)
    return {p: w / Z for p, w in zip(profiles, weights)}


def detailed_balance_residual(
    profiles: Sequence[Tuple[Action, ...]],
    P: Sequence[Sequence[float]],
    pi: Mapping[Tuple[Action, ...], float],
) -> Dict[str, float]:
    """Check stochasticity, detailed balance and the stationary residual.

    Returns the three residuals separately, as Section 7.1 requires:
    ``row_sum`` (rows sum to one), ``detailed_balance``
    (``pi(a) P(a,b) = pi(b) P(b,a)``) and ``stationary`` (``pi P = pi``).
    """
    size = len(profiles)
    row_residual = max(abs(sum(P[r]) - 1.0) for r in range(size))
    db_residual = 0.0
    for r in range(size):
        for c in range(size):
            lhs = pi[profiles[r]] * P[r][c]
            rhs = pi[profiles[c]] * P[c][r]
            db_residual = max(db_residual, abs(lhs - rhs))
    stat_residual = 0.0
    for c in range(size):
        flow = sum(pi[profiles[r]] * P[r][c] for r in range(size))
        stat_residual = max(stat_residual, abs(flow - pi[profiles[c]]))
    return {
        "row_sum": row_residual,
        "detailed_balance": db_residual,
        "stationary": stat_residual,
    }


def expected_potential(
    game: TaskAllocationGame, pi: Mapping[Tuple[Action, ...], float]
) -> float:
    """``E_pi[Phi(a)]``."""
    return sum(p * float(game.potential(a)) for a, p in pi.items())


def potential_loss_bound(
    game: TaskAllocationGame,
    references: Sequence[Mapping[Action, float]],
    tau: float,
    active_only: bool = False,
) -> Dict[str, float]:
    """Corollary 2 / Equation (13): ``max_a Phi(a) - E_pi[Phi] <= tau (log K + R_q)``.

    ``K = |A|`` and ``R_q = sum_i log(q_i^max / q_i^min)``.  The bound is
    conservative and concerns the *potential*, not welfare; very concentrated
    references (large ``R_q``) weaken it.
    """
    profiles = [tuple(a) for a in (game.active_profiles() if active_only else game.profiles())]
    K = len(profiles)
    R_q = 0.0
    for i, ref in enumerate(references):
        feasible = [ref[a] for a in game.action_sets[i]]
        R_q += math.log(max(feasible) / min(feasible))
    pi = stationary_distribution(game, references, tau, active_only=active_only)
    phi_max = max(float(game.potential(a)) for a in profiles)
    realised = phi_max - expected_potential(game, pi)
    bound = tau * (math.log(K) + R_q)
    return {
        "K": float(K),
        "R_q": R_q,
        "phi_max": phi_max,
        "expected_potential": phi_max - realised,
        "realised_loss": realised,
        "bound": bound,
        "satisfied": bool(realised <= bound + 1e-9),
    }


@dataclass
class LogitRun:
    """A sampled trajectory of Equation (11).

    A trajectory at positive temperature is *not* a converged pure equilibrium,
    so the record keeps the visit frequencies and the gap series rather than a
    single "final" answer.
    """

    profiles: List[Tuple[Action, ...]]
    gaps: List[float]
    visits: Dict[Tuple[Action, ...], int]
    updates: int

    def frequencies(self) -> Dict[Tuple[Action, ...], float]:
        total = sum(self.visits.values())
        return {a: c / total for a, c in self.visits.items()}

    def mean_gap(self, burn_in: int = 0) -> float:
        tail = self.gaps[burn_in:]
        return sum(tail) / len(tail) if tail else float("nan")


def run_logit_episode(
    game: TaskAllocationGame,
    start: Sequence[Action],
    references: Sequence[Mapping[Action, float]],
    tau: float,
    updates: int,
    rng: random.Random,
    selection: Optional[Sequence[float]] = None,
    payoff: Optional[Callable[[int, Sequence[Action]], float]] = None,
) -> LogitRun:
    """The logit branch of Algorithm 1, step 3.

    The robust and logit branches are alternatives and must not be combined:
    the robust branch seeks a terminal certificate, whereas logit exploration
    deliberately permits payoff-decreasing moves.

    ``payoff`` is the agent-side value function (see
    :func:`logit_choice_probabilities`).  The recorded Nash gaps are always
    evaluator-side truth, so an estimator's error shows up in the metrics rather
    than being hidden by it.
    """
    n = game.n_agents
    if selection is None:
        selection = [1.0 / n] * n
    cumulative = []
    acc = 0.0
    for p in selection:
        acc += p
        cumulative.append(acc)
    profile = tuple(start)
    visits: Dict[Tuple[Action, ...], int] = {}
    trajectory = [profile]
    gaps = [float(game.nash_gap(profile))]
    for _ in range(updates):
        r = rng.random() * cumulative[-1]
        i = next(k for k, c in enumerate(cumulative) if r <= c)
        b = sample_logit_action(game, i, profile, references[i], tau, rng, payoff)
        profile = game.replace(profile, i, b)
        visits[profile] = visits.get(profile, 0) + 1
        trajectory.append(profile)
        gaps.append(float(game.nash_gap(profile)))
    return LogitRun(trajectory, gaps, visits, updates)
