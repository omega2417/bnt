"""Algorithm 1: the outer physical loop and the inner coordination episode.

The six steps of Algorithm 1 are implemented literally:

1. read observations, residual resources and trace timestamps; apply the safety
   filter and build the finite feasible set including the fallback;
2. freeze the episode context and preserve the incumbent assignment where it
   remains feasible;
3. run **one** inner branch -- robust (Equation 8) or logit (Equation 11), never
   both -- charging computation and communication to the episode budget;
4. stop on budget exhaustion or, in the robust branch, on a complete
   unchanged-context sweep, *recording which of the two occurred*;
5. execute through the reactive safety pathway and record realised outcomes;
6. update traces and local modules between episodes, debit budgets, begin the
   next epoch.  A material context change invalidates the previous certificate.

The field deployment this produces is a *sequence of frozen-context games
embedded in a changing environment*.  It is not a solved stochastic game, and
nothing here borrows a stationary convergence guarantee for the dynamic loop --
the tracking error is measured instead (Section 5.4).
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Sequence, Tuple

from .baselines import CoordinationMethod, EpisodeContext, EpisodeOutcome
from .environments import Environment
from .estimation import BoundedNoiseEstimator, ExactEstimator, PayoffEstimator
from .game import Action, OUTSIDE, TaskAllocationGame
from .seeds import stream
from .traces import TraceField

__all__ = ["EpochRecord", "RunResult", "run_epoch", "run_trial"]


@dataclass
class EpochRecord:
    """One row of the run log required by Section 7.6.

    Estimated values and evaluator-side truth are stored separately, so later
    analysis can detect oracle leakage.
    """

    epoch: int
    profile: Tuple[Action, ...]
    true_nash_gap: float           # evaluator-side, Equation (14)
    welfare: float                 # evaluator-side, Equation (4)
    potential: float               # evaluator-side, Equation (5)
    realised_value: float          # realised task value this epoch
    updates: int
    evaluations: int
    terminated: str                # "certified" | "budget" | "single-pass"
    true_gap_bound: Optional[float]
    energy: float
    inference_energy: float
    latency_max: float
    bytes_moved: float
    trace_age: int
    lost_reports: int
    active_agents: int
    context_events: List[str] = field(default_factory=list)
    notes: Dict[str, object] = field(default_factory=dict)


@dataclass
class RunResult:
    """A complete trial: one method, one environment seed, one condition."""

    method: str
    seed: int
    condition: str
    records: List[EpochRecord] = field(default_factory=list)
    uses_true_payoffs: bool = False

    @property
    def epochs(self) -> int:
        return len(self.records)

    def series(self, field_name: str) -> List[float]:
        return [getattr(r, field_name) for r in self.records]

    def total(self, field_name: str) -> float:
        return float(sum(self.series(field_name)))

    def certified_fraction(self) -> float:
        if not self.records:
            return float("nan")
        return sum(1 for r in self.records if r.terminated == "certified") / len(self.records)


def _carry_incumbent(
    game: TaskAllocationGame, previous: Optional[Sequence[Action]]
) -> Tuple[Action, ...]:
    """Algorithm 1, step 2: preserve the incumbent where it remains feasible."""
    if previous is None:
        return tuple(OUTSIDE for _ in range(game.n_agents))
    return tuple(
        previous[i] if i < len(previous) and previous[i] in game.action_sets[i] else OUTSIDE
        for i in range(game.n_agents)
    )


def _realised_value(env: Environment, game: TaskAllocationGame, profile) -> float:
    """Realised task value: a task pays ``V_j`` once when at least one agent runs it.

    This is the *model* accounting of Equation (4) without private costs.  Actual
    robot mission value, completion probability and failure severity are
    additional empirical outcomes and are not equal to this number.
    """
    counts = game.occupancy(profile)
    return float(sum(game.tasks[j].value for j, n in enumerate(counts) if n > 0))


def run_epoch(
    env: Environment,
    method: CoordinationMethod,
    trace: TraceField,
    estimator: PayoffEstimator,
    method_rng: random.Random,
    incumbent: Optional[Sequence[Action]],
) -> Tuple[EpochRecord, Tuple[Action, ...]]:
    """One iteration of Algorithm 1."""
    cfg = env.config
    # Steps 1-2: safety filter, feasible sets, frozen context.
    game = env.stage_game()
    start = _carry_incumbent(game, incumbent)
    z = trace.frozen()

    ctx = EpisodeContext(
        trace=z,
        rng=method_rng,
        estimator=estimator,
        update_budget=cfg.inner_cap,
        evaluation_budget=cfg.inner_cap * max(len(a) for a in game.action_sets),
        epoch=env.epoch,
        kappa=cfg.trace_kappa,
        epsilon_z=cfg.epsilon_z,
        trace_age=trace.age,
    )
    # Steps 3-4: exactly one inner branch, with its termination reason recorded.
    outcome: EpisodeOutcome = method.coordinate(game, start, ctx)
    profile = outcome.profile

    # Step 5: execute and record.  Occupancy visible to the method is subject to
    # communication loss; the evaluator keeps the truth for Equation (14).
    _, lost = env.observed_occupancy(game.occupancy(profile), method_rng)
    energy = inference_energy = 0.0
    latency_max = 0.0
    bytes_moved = 0.0
    for i, a_i in enumerate(profile):
        if a_i.is_outside:
            continue
        rv = env.resources(i, a_i)
        energy += rv.energy
        inference_energy += cfg.modes[a_i.mode].energy
        latency_max = max(latency_max, rv.latency)
        bytes_moved += rv.comm
    # Inner-loop evaluations are charged to the coordination allowance, not free.
    bytes_moved += 0.001 * outcome.evaluations

    record = EpochRecord(
        epoch=env.epoch,
        profile=profile,
        true_nash_gap=float(game.nash_gap(profile)),
        welfare=float(game.welfare(profile)),
        potential=float(game.potential(profile)),
        realised_value=_realised_value(env, game, profile),
        updates=outcome.updates,
        evaluations=outcome.evaluations,
        terminated=outcome.terminated,
        true_gap_bound=outcome.true_gap_bound,
        energy=energy,
        inference_energy=inference_energy,
        latency_max=latency_max,
        bytes_moved=bytes_moved,
        trace_age=trace.age,
        lost_reports=lost,
        active_agents=sum(env.active),
        notes=dict(outcome.notes),
    )

    # Step 6: trace update between episodes, then the next epoch.
    counts = game.occupancy(profile)
    max_value = max((float(t.value) for t in game.tasks), default=1.0) or 1.0
    reports = {
        j: min(1.0, float(game.tasks[j].value) / max_value) for j, n in enumerate(counts) if n > 0
    }
    trace.update(reports)
    record.context_events = env.advance()
    return record, profile


def run_trial(
    env: Environment,
    method: CoordinationMethod,
    seed: int,
    condition: str = "nominal",
    epochs: Optional[int] = None,
) -> RunResult:
    """Run one method on one environment for the declared horizon.

    Random streams are separated by role: the environment stream is fixed by the
    environment seed, while method-dependent random choices draw from their own
    stream, so differing control flow cannot accidentally change the environment.
    """
    cfg = env.config
    horizon = epochs if epochs is not None else cfg.epochs
    method_rng = stream("method", method.name, seed)
    estimator_rng = stream("estimator", seed)
    if method.uses_true_payoffs or cfg.observation_noise <= 0:
        estimator: PayoffEstimator = ExactEstimator(env.n_agents)
    else:
        estimator = BoundedNoiseEstimator(
            cfg.observation_noise, env.n_agents, rng=estimator_rng
        )
    trace = TraceField(env.n_tasks, rho=cfg.trace_rho, delay=cfg.trace_delay)
    result = RunResult(
        method=method.name,
        seed=seed,
        condition=condition,
        uses_true_payoffs=method.uses_true_payoffs,
    )
    incumbent: Optional[Tuple[Action, ...]] = None
    for _ in range(horizon):
        record, incumbent = run_epoch(env, method, trace, estimator, method_rng, incumbent)
        result.records.append(record)
    return result
