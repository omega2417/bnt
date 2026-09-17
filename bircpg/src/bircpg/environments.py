"""Section 7.2: Level II synthetic environments with declared generative assumptions.

Abstract monitoring sites on a unit-square workspace.  Agent and task
coordinates are drawn from a declared distribution -- the simplest initial
generator, independent uniform placement, is the default here.  Travel-related
costs depend on Euclidean distance.  Nominal task values are sampled uniformly
between 0.5 and 1.5.  The congestion family is ``g_j(k) = gamma_j (k - 1)`` with
``gamma_j in {0, 0.05, 0.20}``.

These numbers are dimensionless experimental settings.  They are not biological
measurements and not calibrated robot parameters.  Nothing in this generator
hard-codes a lower cost or a higher accuracy for any particular controller: the
mode cost multipliers below are declared once and applied to every method
identically, which is the failure mode Section 7.2 warns about.

Random streams are separated by role (environment, estimator, method) so that
differing control flow in a method cannot change the environment it faces.
"""

from __future__ import annotations

import math
import random
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Sequence, Tuple

from .seeds import stream
from .game import (
    Action,
    CONTROLLER_MODES,
    CostModel,
    OUTSIDE,
    ResourceCaps,
    ResourceVector,
    Task,
    TaskAllocationGame,
    linear_congestion,
)

__all__ = [
    "ModeProfile",
    "EnvironmentConfig",
    "Environment",
    "make_environment",
    "task_count_for",
]

#: Per-mode multipliers on the shared profiling procedure of Section 7.2.
#: Deliberative inference costs more energy, computation, memory and latency
#: but carries less execution risk; reactive is the cheap, riskier pathway.
#: These are *declared synthetic settings*, applied identically to every method.
@dataclass(frozen=True)
class ModeProfile:
    name: str
    energy: float
    compute: float
    memory: float
    latency: float
    risk: float


DEFAULT_MODE_PROFILES: Tuple[ModeProfile, ...] = (
    ModeProfile("reactive", energy=0.20, compute=0.10, memory=0.10, latency=0.05, risk=0.30),
    ModeProfile("memory", energy=0.45, compute=0.40, memory=0.45, latency=0.15, risk=0.15),
    ModeProfile("deliberative", energy=0.90, compute=1.00, memory=0.90, latency=0.40, risk=0.05),
)


def task_count_for(n_agents: int, density: str = "nominal") -> int:
    """Table 3 task density: nominal ``m = ceil(n/5)``, sensitivity at ``n/2``, ``n/10``."""
    if density == "nominal":
        return max(1, math.ceil(n_agents / 5))
    if density == "scarce":       # m = n/10: many agents per task, strong congestion
        return max(1, math.ceil(n_agents / 10))
    if density == "abundant":     # m = n/2: tasks plentiful relative to agents
        return max(1, math.ceil(n_agents / 2))
    raise ValueError(f"unknown task density {density!r}")


@dataclass(frozen=True)
class EnvironmentConfig:
    """Declared generative assumptions for one Level II instance."""

    n_agents: int = 10
    density: str = "nominal"
    gamma: float = 0.05                    # congestion slope, Table 3 {0, 0.05, 0.20}
    value_range: Tuple[float, float] = (0.5, 1.5)
    travel_cost_scale: float = 1.0
    heterogeneous_caps: bool = False
    observation_noise: float = 0.0         # Table 3 {0, 0.05, 0.15}
    comm_loss: float = 0.0                 # Table 3 {0, 0.1, 0.3}
    trace_rho: float = 0.2                 # Table 3 {0.05, 0.2, 0.5}
    trace_delay: int = 0                   # Table 3 {0, 1, 5} epochs
    trace_kappa: float = 1.0               # Table 3 {0, 1, 3}
    epsilon_z: float = 0.1
    tau: float = 0.1                       # Table 3 {0.02, 0.1, 0.5}
    epochs: int = 100                      # Section 7.2 preregisters 1000
    inner_updates_per_epoch: Optional[int] = None   # default 5n
    value_change_period: Optional[int] = None       # e.g. 100 epochs
    value_change_fraction: float = 0.25
    dropout_epoch: Optional[int] = None             # e.g. epoch 500
    dropout_fraction: float = 0.10
    cost_model: CostModel = field(default_factory=CostModel)
    modes: Tuple[ModeProfile, ...] = DEFAULT_MODE_PROFILES

    def __post_init__(self) -> None:
        if self.n_agents < 1:
            raise ValueError("at least one agent is required")
        if not 0.0 <= self.comm_loss <= 1.0:
            raise ValueError("communication loss is a probability")
        if self.observation_noise < 0:
            raise ValueError("observation perturbation must be nonnegative")
        if self.gamma < 0:
            raise ValueError("congestion slope gamma must be nonnegative")

    @property
    def inner_cap(self) -> int:
        """Inner-update cap; Table 3 sets ``5n`` initially."""
        return self.inner_updates_per_epoch or 5 * self.n_agents


@dataclass
class Environment:
    """One generated Level II instance plus the epoch dynamics of Table 3."""

    config: EnvironmentConfig
    agent_xy: List[Tuple[float, float]]
    task_xy: List[Tuple[float, float]]
    values: List[float]
    caps: List[ResourceCaps]
    active: List[bool]
    seed: int
    epoch: int = 0
    _env_rng: random.Random = field(default_factory=random.Random, repr=False)
    _resources: Dict[Tuple[int, Action], ResourceVector] = field(default_factory=dict, repr=False)

    # ------------------------------------------------------------------
    @property
    def n_agents(self) -> int:
        return len(self.agent_xy)

    @property
    def n_tasks(self) -> int:
        return len(self.task_xy)

    def distance(self, i: int, j: int) -> float:
        (x1, y1), (x2, y2) = self.agent_xy[i], self.task_xy[j]
        return math.hypot(x1 - x2, y1 - y2)

    def resources(self, i: int, action: Action) -> ResourceVector:
        """Resource vector for ``(i, (j, h))`` from the shared profiling procedure."""
        if action.is_outside:
            return ResourceVector()
        key = (i, action)
        if key not in self._resources:
            mode = self.config.modes[action.mode]
            travel = self.config.travel_cost_scale * self.distance(i, action.task)
            self._resources[key] = ResourceVector(
                energy=mode.energy + travel,
                compute=mode.compute,
                memory=mode.memory,
                latency=mode.latency + 0.5 * travel,
                comm=0.05,  # reading or writing a trace is not free communication
                risk=mode.risk,
            )
        return self._resources[key]

    # ------------------------------------------------------------------
    def stage_game(self) -> TaskAllocationGame:
        """Build the frozen-context stage game ``Gamma(x_t)`` for this epoch (A2)."""
        cfg = self.config
        tasks = [
            Task(value=v, congestion=linear_congestion(cfg.gamma), name=f"T{j}")
            for j, v in enumerate(self.values)
        ]
        action_sets: List[List[Action]] = []
        private_cost: Dict[Tuple[int, Action], float] = {}
        for i in range(self.n_agents):
            feasible: List[Action] = [OUTSIDE]
            if self.active[i]:
                for j in range(self.n_tasks):
                    for h in range(len(cfg.modes)):
                        action = Action(j, h)
                        rv = self.resources(i, action)
                        if self.caps[i].admits(rv):
                            feasible.append(action)
                            private_cost[(i, action)] = cfg.cost_model.cost(rv)
            action_sets.append(feasible)
        return TaskAllocationGame(
            tasks=tasks,
            action_sets=action_sets,
            private_cost=private_cost,
            label=f"level2/seed={self.seed}/epoch={self.epoch}",
        )

    # ------------------------------------------------------------------
    def advance(self) -> List[str]:
        """Apply the scheduled dynamics of Section 7.2 and start the next epoch.

        Returns the list of context changes applied, so that a run log can mark
        the epoch at which a previous episode's certificate was invalidated.
        """
        cfg = self.config
        self.epoch += 1
        events: List[str] = []
        if cfg.value_change_period and self.epoch % cfg.value_change_period == 0:
            k = max(1, int(round(cfg.value_change_fraction * self.n_tasks)))
            for j in self._env_rng.sample(range(self.n_tasks), k):
                self.values[j] = self._env_rng.uniform(*cfg.value_range)
            events.append(f"value_change:{k}")
        if cfg.dropout_epoch and self.epoch == cfg.dropout_epoch:
            k = max(1, int(round(cfg.dropout_fraction * self.n_agents)))
            live = [i for i in range(self.n_agents) if self.active[i]]
            for i in self._env_rng.sample(live, min(k, len(live))):
                self.active[i] = False
            events.append(f"dropout:{k}")
        return events

    def observed_occupancy(
        self, occupancy: Sequence[int], method_rng: random.Random
    ) -> Tuple[List[int], int]:
        """Apply communication loss to the occupancy counts visible to a method.

        Loss is applied to the *information the method can see*.  The evaluator
        retains true occupancy and the declared true payoff function for
        computing Equation (14); algorithms may not query that as a hidden
        oracle.  Returns the visible counts and the number of lost reports.
        """
        visible = list(occupancy)
        lost = 0
        for j in range(len(visible)):
            if method_rng.random() < self.config.comm_loss:
                visible[j] = 0  # the report did not arrive; stale/absent count
                lost += 1
        return visible, lost


def make_environment(config: EnvironmentConfig, seed: int) -> Environment:
    """Generate one instance.  ``seed`` drives the *environment* stream only."""
    env_rng = stream("environment", seed, config.n_agents, config.density)
    n = config.n_agents
    m = task_count_for(n, config.density)
    agent_xy = [(env_rng.random(), env_rng.random()) for _ in range(n)]
    task_xy = [(env_rng.random(), env_rng.random()) for _ in range(m)]
    values = [env_rng.uniform(*config.value_range) for _ in range(m)]
    if config.heterogeneous_caps:
        caps = [
            ResourceCaps(
                energy=env_rng.uniform(0.9, 2.2),
                compute=env_rng.choice([0.2, 0.5, 1.1]),
                memory=env_rng.uniform(0.3, 1.1),
                latency=env_rng.uniform(0.3, 1.2),
            )
            for _ in range(n)
        ]
    else:
        caps = [ResourceCaps(energy=2.0, compute=1.1, memory=1.0, latency=1.0) for _ in range(n)]
    env = Environment(
        config=config,
        agent_xy=agent_xy,
        task_xy=task_xy,
        values=values,
        caps=caps,
        active=[True] * n,
        seed=seed,
    )
    env._env_rng = env_rng
    return env
