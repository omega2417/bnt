"""Constrained multi-objective search and its quality measures (Section 4.5).

The module implements Algorithm 1 - an NSGA-II-style loop with Deb's
constraint-domination rule [11] - together with the indicators the protocol
reports: the exact two-objective hypervolume of Appendix A.3, the design
diversity of Eq. (22), the feasible-solution rate of Eq. (20) and the
iterations-to-specification of Eq. (23).

Production deployments may substitute pymoo [14] or any NSGA-II/NSGA-III
implementation without changing the protocol: the arms differ only in the
sampling prior and the constraints, never in the optimizer.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field
from typing import Any, Callable

import numpy as np

__all__ = [
    "ApproxSet",
    "constrained_search",
    "crowding_distance",
    "design_diversity",
    "dominates",
    "heuristic_refinement_search",
    "hypervolume_2d",
    "non_dominated_sort",
    "normalized_hypervolume",
    "pareto_front",
]

Evaluator = Callable[[np.ndarray], tuple[np.ndarray, np.ndarray]]
Sampler = Callable[[int, np.random.Generator], np.ndarray]


def dominates(f_a: Sequence[float], f_b: Sequence[float]) -> bool:
    """Pareto dominance for minimized objectives (Section 4.5)."""
    a, b = np.asarray(f_a, dtype=float), np.asarray(f_b, dtype=float)
    return bool(np.all(a <= b) and np.any(a < b))


def non_dominated_sort(f: np.ndarray, violation: np.ndarray | None = None) -> list[np.ndarray]:
    """Rank rows of ``f`` into non-dominated fronts (Deb's constraint domination).

    With ``violation`` supplied, a feasible design always dominates an
    infeasible one and, between two infeasible designs, the one with smaller
    total violation is preferred - which is exactly Deb's rule [11] and the
    reason the loop never needs a penalty parameter.
    """
    f = np.atleast_2d(np.asarray(f, dtype=float))
    n = f.shape[0]
    viol = np.zeros(n) if violation is None else np.asarray(violation, dtype=float)

    def better(i: int, j: int) -> bool:
        fi, fj = viol[i] <= 0, viol[j] <= 0
        if fi and not fj:
            return True
        if fj and not fi:
            return False
        if not fi and not fj:
            return viol[i] < viol[j]
        return dominates(f[i], f[j])

    dominated_by: list[list[int]] = [[] for _ in range(n)]
    counts = np.zeros(n, dtype=int)
    for i in range(n):
        for j in range(n):
            if i == j:
                continue
            if better(i, j):
                dominated_by[i].append(j)
            elif better(j, i):
                counts[i] += 1
    fronts: list[np.ndarray] = []
    current = [i for i in range(n) if counts[i] == 0]
    while current:
        fronts.append(np.array(sorted(current), dtype=int))
        nxt: list[int] = []
        for i in current:
            for j in dominated_by[i]:
                counts[j] -= 1
                if counts[j] == 0:
                    nxt.append(j)
        current = nxt
    return fronts


def crowding_distance(f: np.ndarray) -> np.ndarray:
    """NSGA-II crowding distance of a front (infinite at the extremes)."""
    f = np.atleast_2d(np.asarray(f, dtype=float))
    n, m = f.shape
    distance = np.zeros(n)
    if n <= 2:
        return np.full(n, np.inf)
    for k in range(m):
        order = np.argsort(f[:, k], kind="stable")
        values = f[order, k]
        spread = values[-1] - values[0]
        distance[order[0]] = distance[order[-1]] = np.inf
        if spread <= 0:
            continue
        distance[order[1:-1]] += (values[2:] - values[:-2]) / spread
    return distance


def pareto_front(f: np.ndarray) -> np.ndarray:
    """Indices of the non-dominated rows of ``f``."""
    f = np.atleast_2d(np.asarray(f, dtype=float))
    keep = np.ones(len(f), dtype=bool)
    for i in range(len(f)):
        if not keep[i]:
            continue
        for j in range(len(f)):
            if i != j and keep[j] and dominates(f[j], f[i]):
                keep[i] = False
                break
    return np.flatnonzero(keep)


def hypervolume_2d(front: np.ndarray, reference: Sequence[float]) -> float:
    """Exact two-objective hypervolume (Eq. 12, Appendix A.3).

    For a non-dominated set sorted ascending by the first objective with
    ``f_1^{(0)} <= ... <= f_1^{(K-1)}`` and reference point ``r``,

    .. math::  HV = \\sum_k (r_1 - f_1^{(k)})\\,(f_2^{(k-1)} - f_2^{(k)})

    with ``f_2^{(-1)} = r_2``.  Points that do not dominate the reference
    contribute nothing.  This is the quantity verified against a hand-computed
    case in ``tests/test_optimize.py``.
    """
    reference = np.asarray(reference, dtype=float)
    if reference.shape != (2,):
        raise ValueError("hypervolume_2d needs a two-dimensional reference point")
    points = np.atleast_2d(np.asarray(front, dtype=float))
    if points.size == 0:
        return 0.0
    if points.shape[1] != 2:
        raise ValueError("hypervolume_2d needs two objectives")
    points = points[np.all(points < reference, axis=1)]
    if points.size == 0:
        return 0.0
    points = points[pareto_front(points)]
    points = points[np.argsort(points[:, 0], kind="stable")]
    volume, previous_f2 = 0.0, reference[1]
    for f1, f2 in points:
        if f2 >= previous_f2:
            continue
        volume += (reference[0] - f1) * (previous_f2 - f2)
        previous_f2 = f2
    return float(volume)


def normalized_hypervolume(
    front: np.ndarray, reference: Sequence[float], nadir: Sequence[float] | None = None
) -> float:
    """Hypervolume normalized to ``[0, 1]`` by the reference box (Eq. 12).

    The reference point is set from the specification limits, so the normalizer
    is the volume of the box between the ideal point (the origin, both
    objectives being non-negative) and the reference.
    """
    reference = np.asarray(reference, dtype=float)
    ideal = np.zeros_like(reference) if nadir is None else np.asarray(nadir, dtype=float)
    box = float(np.prod(reference - ideal))
    if box <= 0:
        return 0.0
    return float(hypervolume_2d(front, reference) / box)


def design_diversity(x: np.ndarray, lower: np.ndarray, upper: np.ndarray) -> float:
    """Design diversity ``D`` of a set of designs (Eq. 22).

    The mean pairwise Euclidean distance in the unit-normalized design space,
    divided by ``sqrt(n_vars)`` so that ``D`` lies in ``[0, 1]`` and is
    comparable across tasks with different numbers of variables.
    """
    x = np.atleast_2d(np.asarray(x, dtype=float))
    if len(x) < 2:
        return 0.0
    span = np.where(np.asarray(upper) - np.asarray(lower) > 0,
                    np.asarray(upper) - np.asarray(lower), 1.0)
    unit = (x - np.asarray(lower)) / span
    diff = unit[:, None, :] - unit[None, :, :]
    distance = np.sqrt(np.sum(diff**2, axis=-1))
    n = len(unit)
    mean_pairwise = float(np.sum(distance) / (n * (n - 1)))
    return float(mean_pairwise / np.sqrt(unit.shape[1]))


@dataclass
class ApproxSet:
    """Result of one search run: the approximation set and its generation log."""

    x: np.ndarray
    f: np.ndarray
    g: np.ndarray
    feasible: np.ndarray
    log: list[dict[str, Any]] = field(default_factory=list)
    seed: int | None = None
    arm: str = ""
    evaluations: int = 0

    @property
    def feasible_x(self) -> np.ndarray:
        return self.x[self.feasible]

    @property
    def feasible_f(self) -> np.ndarray:
        return self.f[self.feasible]

    def pareto(self) -> tuple[np.ndarray, np.ndarray]:
        """Feasible non-dominated designs and their objectives (the set ``A``)."""
        if not np.any(self.feasible):
            return np.empty((0, self.x.shape[1])), np.empty((0, self.f.shape[1]))
        fx, ff = self.feasible_x, self.feasible_f
        idx = pareto_front(ff)
        return fx[idx], ff[idx]

    def iterations_to_specification(self, cap: int | None = None) -> int:
        """``ITS`` of Eq. (23): first generation with any feasible design."""
        for entry in self.log:
            if entry["feasible_fraction"] > 0:
                return int(entry["generation"])
        return int(cap if cap is not None else len(self.log))


def constrained_search(
    evaluator: Evaluator,
    sampler: Sampler,
    lower: np.ndarray,
    upper: np.ndarray,
    population: int = 40,
    generations: int = 25,
    seed: int = 0,
    sigma: float = 0.10,
    arm: str = "",
) -> ApproxSet:
    """Evolution-informed constrained multi-objective search (Algorithm 1).

    The loop is deliberately plain: uniform crossover in the normalized design
    space, Gaussian mutation with clipping, merge of parents and offspring,
    then selection by constraint-dominated fronts and crowding distance, with
    infeasible designs appended in order of total violation so that a
    population that starts entirely infeasible can still make progress.

    Arms differ only in ``sampler``: the analog-shaped prior ``p_c`` for arm C,
    a uniform prior on ``D`` for arm B.  Budget (``population``,
    ``generations``) and ``seed`` are shared, so any difference between the arms
    is attributable to the evolutionary data that shaped the prior.
    """
    rng = np.random.default_rng(seed)
    lower = np.asarray(lower, dtype=float)
    upper = np.asarray(upper, dtype=float)
    span = np.where(upper - lower > 0, upper - lower, 1.0)

    x = np.clip(sampler(population, rng), lower, upper)
    f, g = evaluator(x)
    evaluations = len(x)
    log: list[dict[str, Any]] = []

    for generation in range(1, int(generations) + 1):
        z = (x - lower) / span
        partner = rng.permutation(len(z))
        mask = rng.random(z.shape) < 0.5
        child = np.where(mask, z, z[partner])
        child = np.clip(child + rng.normal(0.0, sigma, child.shape), 0.0, 1.0)
        x_child = lower + child * span
        f_child, g_child = evaluator(x_child)
        evaluations += len(x_child)

        x_all = np.vstack([x, x_child])
        f_all = np.vstack([f, f_child])
        g_all = np.vstack([g, g_child])
        violation = np.sum(np.maximum(0.0, -g_all), axis=1)
        feasible = violation <= 0

        selected: list[int] = []
        if np.any(feasible):
            idx_feasible = np.flatnonzero(feasible)
            for front in non_dominated_sort(f_all[idx_feasible]):
                front_idx = idx_feasible[front]
                if len(selected) + len(front_idx) <= population:
                    selected.extend(front_idx.tolist())
                    continue
                room = population - len(selected)
                order = np.argsort(-crowding_distance(f_all[front_idx]), kind="stable")
                selected.extend(front_idx[order[:room]].tolist())
                break
        if len(selected) < population:
            idx_infeasible = np.flatnonzero(~feasible)
            order = idx_infeasible[np.argsort(violation[idx_infeasible], kind="stable")]
            selected.extend(order[: population - len(selected)].tolist())

        keep = np.array(selected[:population], dtype=int)
        x, f, g = x_all[keep], f_all[keep], g_all[keep]
        feasible_fraction = float(np.mean(np.all(g >= 0.0, axis=1)))
        log.append(
            {
                "generation": generation,
                "feasible_fraction": feasible_fraction,
                "best_mass": float(np.min(f[:, 0])) if len(f) else float("nan"),
                "evaluations": evaluations,
            }
        )

    feasible_mask = np.all(g >= 0.0, axis=1)
    return ApproxSet(
        x=x, f=f, g=g, feasible=feasible_mask, log=log, seed=seed, arm=arm,
        evaluations=evaluations,
    )


def heuristic_refinement_search(
    evaluator: Evaluator,
    sampler: Sampler,
    lower: np.ndarray,
    upper: np.ndarray,
    n_variants: int = 4,
    rounds: int = 25,
    seed: int = 0,
    step: float = 0.12,
    arm: str = "A",
) -> ApproxSet:
    """Time-matched stand-in for the expert arm (arm A of Section 7.2).

    Arm A is a *human* baseline: two engineers working with catalog-style
    resources and standard CAD produce designs within the same wall-clock
    budget as the computational arms, and their designs are evaluated with the
    same evaluator.  It is therefore matched in time, not in evaluations, and
    it is not Algorithm 1: a designer carries a handful of variants and edits
    them one dimension at a time in response to the constraint that hurts most.

    This routine models that process - a few template variants, one
    constraint-directed edit per round, no population-based selection - so that
    the protocol code can run end to end before the human arm is staffed.  It
    is a **stand-in, not a model of human designers**: results obtained with it
    say nothing about what engineers would produce, and the dry run of Section
    7.7 draws no inference from them.
    """
    rng = np.random.default_rng(seed)
    lower = np.asarray(lower, dtype=float)
    upper = np.asarray(upper, dtype=float)

    x = np.clip(sampler(int(n_variants), rng), lower, upper)
    evaluations = 0
    log: list[dict[str, Any]] = []
    f, g = evaluator(x)
    evaluations += len(x)

    # Which design variable a designer reaches for when a given margin is
    # negative: (variable index, multiplicative direction).  Order follows
    # constraint_names() of evoproto.design.
    edits = {
        0: (1, +1.0),   # deflection  -> deepen the section
        1: (1, +1.0),   # yield       -> deepen the section
        2: (2, +1.0),   # buckling    -> thicken the wall
        3: (3, -1.0),   # mass cap    -> lighten the core
        4: (0, +1.0),   # wall fit    -> widen the section
    }

    for round_index in range(1, int(rounds) + 1):
        feasible_fraction = float(np.mean(np.all(g >= 0.0, axis=1)))
        log.append(
            {
                "generation": round_index,
                "feasible_fraction": feasible_fraction,
                "best_mass": float(np.min(f[:, 0])) if len(f) else float("nan"),
                "evaluations": evaluations,
            }
        )
        if round_index == int(rounds):
            break
        x_next = x.copy()
        for i in range(len(x)):
            if np.all(g[i] >= 0.0):
                variable, direction = 3, -1.0      # feasible: trim the core mass
            else:
                worst = int(np.argmin(g[i]))
                variable, direction = edits.get(worst, (3, -1.0))
            noise = float(rng.normal(1.0, 0.25))
            x_next[i, variable] *= 1.0 + direction * step * max(noise, 0.1)
        x = np.clip(x_next, lower, upper)
        f, g = evaluator(x)
        evaluations += len(x)

    feasible_mask = np.all(g >= 0.0, axis=1)
    return ApproxSet(
        x=x, f=f, g=g, feasible=feasible_mask, log=log, seed=seed, arm=arm,
        evaluations=evaluations,
    )
