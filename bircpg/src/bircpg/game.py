"""Formal model of Section 4: decision epochs, feasible actions, payoffs, welfare.

Notation follows the manuscript.  Agents ``N = {1, ..., n}``, tasks
``J = {1, ..., m}``, controller modes ``h in H``.  An action is either the
outside action ``0`` or a pair ``(j, h)``.

Symbols used throughout the package:

============  ==========================================================
``V_j``       nominal value of task ``j``                     (Section 4.2)
``g_j(k)``    congestion penalty per participant, ``k`` participants
``n_j(a)``    number of agents assigned to task ``j``
``d_i(a_i)``  agent-specific dimensionless cost               (Equation 2)
``u_i(a)``    payoff                                          (Equation 3)
``W(a)``      aggregate model welfare                         (Equation 4)
``Phi(a)``    exact potential                                 (Equation 5)
============  ==========================================================

Every quantity is computed with whatever numeric type the caller supplies.
Passing :class:`fractions.Fraction` inputs makes the whole Level I layer exact,
which is what Section 7.1 requires.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from fractions import Fraction
from itertools import product
from typing import Callable, Dict, Iterable, Iterator, Optional, Sequence, Tuple

__all__ = [
    "CONTROLLER_MODES",
    "Action",
    "OUTSIDE",
    "ResourceVector",
    "ResourceCaps",
    "CostModel",
    "Task",
    "TaskAllocationGame",
    "harmonic",
    "zero_congestion",
    "linear_congestion",
]

#: Controller modes of Section 4.1.  The mode affects private cost only; in the
#: proven model it does not change the value produced by other agents.
CONTROLLER_MODES: Tuple[str, ...] = ("reactive", "memory", "deliberative")


@dataclass(frozen=True, order=True)
class Action:
    """An element of ``A_i``: the outside action ``0`` or a pair ``(j, h)``."""

    task: Optional[int] = None
    mode: Optional[int] = None

    @property
    def is_outside(self) -> bool:
        return self.task is None

    def __str__(self) -> str:  # pragma: no cover - cosmetic
        if self.is_outside:
            return "0"
        if self.mode is None:
            return f"({self.task})"
        return f"({self.task},{self.mode})"


#: The outside action of Section 4.1: abstention or a predefined safe fallback.
#: It is feasible by modelling convention and has zero incremental payoff and
#: zero incremental cost (``d_i(0) = 0``).  The baseline power needed to execute
#: the physical fallback is *not* modelled here; see Section 4.1.
OUTSIDE = Action(None, None)


@dataclass(frozen=True)
class ResourceVector:
    """Per-action resource requirements entering Equations (1) and (2)."""

    energy: float = 0.0     # e_i(j, h)   predicted energy expenditure
    compute: float = 0.0    # c_i(j, h)   computation count / processing requirement
    memory: float = 0.0     # mu_i(h)     memory use
    latency: float = 0.0    # l_i(j, h)   decision or execution latency
    comm: float = 0.0       # k_i(j, h)   communication / trace access
    risk: float = 0.0       # r_i(j, h)   normalised expected execution-loss score


@dataclass(frozen=True)
class ResourceCaps:
    """Positive per-epoch limits ``E^cap, C^cap, M^cap, L^cap`` of Equation (1)."""

    energy: float = float("inf")
    compute: float = float("inf")
    memory: float = float("inf")
    latency: float = float("inf")

    def admits(self, rv: ResourceVector) -> bool:
        return (
            rv.energy <= self.energy
            and rv.compute <= self.compute
            and rv.memory <= self.memory
            and rv.latency <= self.latency
        )


@dataclass(frozen=True)
class CostModel:
    """Equation (2): the agent-specific dimensionless cost ``d_i(j, h)``.

    The nonnegative weights must sum to one.  The reference scales are fixed
    positive calibration values that have to be *common to all compared
    methods*; the risk term ``r_i`` is already normalised and has no reference
    scale.  Equation (2) is a preference model, not a physical-energy
    accounting identity.
    """

    w_E: float = 0.25
    w_C: float = 0.25
    w_K: float = 0.10
    w_L: float = 0.20
    w_R: float = 0.20
    E_ref: float = 1.0
    C_ref: float = 1.0
    K_ref: float = 1.0
    L_ref: float = 1.0

    def __post_init__(self) -> None:
        weights = (self.w_E, self.w_C, self.w_K, self.w_L, self.w_R)
        if any(w < 0 for w in weights):
            raise ValueError("cost weights must be nonnegative")
        if abs(sum(weights) - 1.0) > 1e-9:
            raise ValueError(f"cost weights must sum to one, got {sum(weights)}")
        for name in ("E_ref", "C_ref", "K_ref", "L_ref"):
            if getattr(self, name) <= 0:
                raise ValueError(f"{name} must be a positive calibration scale")

    def cost(self, rv: ResourceVector) -> float:
        return (
            self.w_E * rv.energy / self.E_ref
            + self.w_C * rv.compute / self.C_ref
            + self.w_K * rv.comm / self.K_ref
            + self.w_L * rv.latency / self.L_ref
            + self.w_R * rv.risk
        )


def harmonic(q: int) -> Fraction:
    """``H_q = sum_{k=1}^{q} 1/k`` with ``H_0 = 0`` (Section 5.1), exact."""
    if q < 0:
        raise ValueError("harmonic number requires q >= 0")
    total = Fraction(0)
    for k in range(1, q + 1):
        total += Fraction(1, k)
    return total


def zero_congestion(k: int):
    """``g_j(k) = 0``: the no-congestion case used by the Section 6 example."""
    return 0


def linear_congestion(gamma):
    """``g_j(k) = gamma * (k - 1)``, the family proposed in Section 7.2.

    ``gamma in {0, 0.05, 0.20}`` are the levels listed in Table 3.
    """

    def g(k: int):
        return gamma * (k - 1)

    return g


@dataclass(frozen=True)
class Task:
    """A task ``j`` with nominal value ``V_j >= 0`` and congestion ``g_j``."""

    value: object = 0
    congestion: Callable[[int], object] = zero_congestion
    name: str = ""

    def __post_init__(self) -> None:
        if self.value < 0:
            raise ValueError("task values V_j must be nonnegative (Section 4.2)")


@dataclass
class TaskAllocationGame:
    """The frozen-context stage game ``Gamma(x_t)`` of Section 4.

    Parameters
    ----------
    tasks:
        The task list ``J``.  ``tasks[j]`` carries ``V_j`` and ``g_j``.
    action_sets:
        ``action_sets[i]`` is the finite, nonempty feasible set ``A_i`` of
        Equation (1).  It must contain :data:`OUTSIDE`.
    private_cost:
        ``d_i(a_i)`` as a mapping ``(i, action) -> number``.  Missing entries
        default to zero; ``d_i(0) = 0`` always.

    Assumption A1 (finite independent feasibility) and A3 (common task
    interaction, separable private costs) are structural here: ``A_i`` cannot
    depend on ``a_{-i}``, and ``V_j``/``g_j`` are shared by all participants.
    A2 (frozen context) is the caller's responsibility -- a game object *is*
    one frozen context.
    """

    tasks: Sequence[Task]
    action_sets: Sequence[Sequence[Action]]
    private_cost: Dict[Tuple[int, Action], object] = field(default_factory=dict)
    label: str = ""

    def __post_init__(self) -> None:
        if not self.action_sets:
            raise ValueError("the game needs at least one agent")
        for i, acts in enumerate(self.action_sets):
            if not acts:
                raise ValueError(f"A_{i} is empty, violating assumption A1")
            if OUTSIDE not in acts:
                raise ValueError(
                    f"A_{i} must contain the outside action (Section 4.1)"
                )
            if len(set(acts)) != len(acts):
                raise ValueError(f"A_{i} contains duplicate actions")
            for a in acts:
                if not a.is_outside and not 0 <= a.task < len(self.tasks):
                    raise ValueError(f"A_{i} refers to unknown task {a.task}")
        for (i, a), value in self.private_cost.items():
            if a.is_outside and value != 0:
                raise ValueError("d_i(0) = 0 by definition (Section 4.2)")
            if value < 0:
                raise ValueError("private costs d_i must be nonnegative")

    # ------------------------------------------------------------------
    # basic accessors
    # ------------------------------------------------------------------
    @property
    def n_agents(self) -> int:
        return len(self.action_sets)

    @property
    def n_tasks(self) -> int:
        return len(self.tasks)

    @property
    def profile_count(self) -> int:
        """``K = |A|``, the size of the joint action set (Corollary 2)."""
        count = 1
        for acts in self.action_sets:
            count *= len(acts)
        return count

    def d(self, i: int, a_i: Action):
        """Equation (2) value ``d_i(a_i)``; zero for the outside action."""
        if a_i.is_outside:
            return 0
        return self.private_cost.get((i, a_i), 0)

    def occupancy(self, profile: Sequence[Action]) -> Tuple[int, ...]:
        """``n_j(a)`` for every task ``j``."""
        counts = [0] * self.n_tasks
        for a_i in profile:
            if not a_i.is_outside:
                counts[a_i.task] += 1
        return tuple(counts)

    # ------------------------------------------------------------------
    # Equations (3), (4), (5), (14)
    # ------------------------------------------------------------------
    def payoff(self, i: int, profile: Sequence[Action]):
        """Equation (3): ``u_i(a) = V_j/n_j - g_j(n_j) - d_i(a_i)``."""
        a_i = profile[i]
        if a_i.is_outside:
            return 0
        j = a_i.task
        n_j = self.occupancy(profile)[j]
        task = self.tasks[j]
        return task.value / n_j - task.congestion(n_j) - self.d(i, a_i)

    def payoffs(self, profile: Sequence[Action]) -> Tuple[object, ...]:
        counts = self.occupancy(profile)
        out = []
        for i, a_i in enumerate(profile):
            if a_i.is_outside:
                out.append(0)
                continue
            task = self.tasks[a_i.task]
            n_j = counts[a_i.task]
            out.append(task.value / n_j - task.congestion(n_j) - self.d(i, a_i))
        return tuple(out)

    def welfare(self, profile: Sequence[Action]):
        """Equation (4): ``W(a) = sum_i u_i(a)``.

        Computed from the closed form
        ``sum_{j: n_j>0} V_j - sum_j n_j g_j(n_j) - sum_i d_i(a_i)`` and equal
        to the sum of Equation (3) by construction.
        """
        counts = self.occupancy(profile)
        total = 0
        for j, n_j in enumerate(counts):
            if n_j > 0:
                total += self.tasks[j].value - n_j * self.tasks[j].congestion(n_j)
        for i, a_i in enumerate(profile):
            total -= self.d(i, a_i)
        return total

    def potential(self, profile: Sequence[Action]):
        """Equation (5): ``Phi(a) = sum_j [V_j H(n_j) - sum_{k<=n_j} g_j(k)] - sum_i d_i``."""
        counts = self.occupancy(profile)
        total = 0
        for j, n_j in enumerate(counts):
            if n_j == 0:
                continue
            task = self.tasks[j]
            total += task.value * harmonic(n_j)
            for k in range(1, n_j + 1):
                total -= task.congestion(k)
        for i, a_i in enumerate(profile):
            total -= self.d(i, a_i)
        return total

    def deviations(self, i: int, profile: Sequence[Action]) -> Iterator[Tuple[Action, object]]:
        """Yield ``(b_i, u_i(b_i, a_{-i}))`` for every ``b_i in A_i``."""
        for b_i in self.action_sets[i]:
            yield b_i, self.payoff(i, self.replace(profile, i, b_i))

    def best_response(self, i: int, profile: Sequence[Action]) -> Tuple[Action, object]:
        """A payoff-maximising ``b_i``; ties are broken by action order."""
        best_action, best_value = None, None
        for b_i, value in self.deviations(i, profile):
            if best_value is None or value > best_value:
                best_action, best_value = b_i, value
        return best_action, best_value

    def unilateral_gain(self, i: int, profile: Sequence[Action], b_i: Action):
        """``u_i(b_i, a_{-i}) - u_i(a)``."""
        return self.payoff(i, self.replace(profile, i, b_i)) - self.payoff(i, profile)

    def nash_gap(self, profile: Sequence[Action]):
        """Equation (14): ``Gap(a) = max_i max_{b_i} [u_i(b_i, a_-i) - u_i(a)]``.

        The current action is included among the deviations, so the value is
        nonnegative, and it is zero exactly at a pure Nash equilibrium.
        """
        gap = 0
        for i in range(self.n_agents):
            u_i = self.payoff(i, profile)
            for _, value in self.deviations(i, profile):
                gain = value - u_i
                if gain > gap:
                    gap = gain
        return gap

    def is_nash_equilibrium(self, profile: Sequence[Action]) -> bool:
        """Complete equilibrium certificate: *every* feasible deviation is checked."""
        return self.nash_gap(profile) <= 0

    # ------------------------------------------------------------------
    # enumeration helpers
    # ------------------------------------------------------------------
    @staticmethod
    def replace(profile: Sequence[Action], i: int, b_i: Action) -> Tuple[Action, ...]:
        out = list(profile)
        out[i] = b_i
        return tuple(out)

    def profiles(self) -> Iterator[Tuple[Action, ...]]:
        """Enumerate ``A = prod_i A_i``.  Only tractable at Level I."""
        return product(*self.action_sets)

    def active_profiles(self) -> Iterator[Tuple[Action, ...]]:
        """Profiles in which no agent takes the outside action."""
        sets = [[a for a in acts if not a.is_outside] for acts in self.action_sets]
        return product(*sets)
