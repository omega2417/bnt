"""Constrained multi-objective search and front-quality metrics (Section 4.5).

* non-dominated sorting and crowding distance (NSGA-II, Deb et al.);
* Deb's constraint-domination rule: a feasible design always dominates an
  infeasible one, and between two infeasible designs the one with the smaller
  total violation is preferred;
* Eq. (12)/(A.3) the exact two-objective hypervolume, and its normalisation by
  the reference point so that ``HV in [0, 1]`` (Eq. 21);
* Eq. (22) design diversity on the Pareto set;
* Algorithm 1, the evolution-informed search loop, which differs between arms
  B and C only in the sampling prior and the trade-off constraints.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Sequence, Tuple

import numpy as np

__all__ = [
    "dominates",
    "non_dominated_sort",
    "crowding_distance",
    "constraint_violation",
    "hypervolume_2d",
    "normalized_hypervolume",
    "design_diversity",
    "SearchResult",
    "search",
]


def constraint_violation(G: np.ndarray) -> np.ndarray:
    r"""Total constraint violation :math:`\sum_j \max(0, -g_j)` (Algorithm 1, line 7)."""
    return np.sum(np.clip(-np.asarray(G, dtype=float), 0.0, None), axis=1)


def dominates(f1: Sequence[float], f2: Sequence[float]) -> bool:
    """Pareto domination for minimised objectives: ``f1 <= f2`` and ``f1 < f2`` somewhere."""
    a = np.asarray(f1, dtype=float)
    b = np.asarray(f2, dtype=float)
    return bool(np.all(a <= b) and np.any(a < b))


def _constrained_dominates(i: int, j: int, F: np.ndarray, viol: np.ndarray) -> bool:
    """Deb's constraint-domination rule."""
    vi, vj = viol[i], viol[j]
    if vi <= 0 and vj > 0:
        return True
    if vi > 0 and vj <= 0:
        return False
    if vi > 0 and vj > 0:
        return bool(vi < vj)
    return dominates(F[i], F[j])


def non_dominated_sort(F: np.ndarray, violation: Optional[np.ndarray] = None) -> List[List[int]]:
    """Fast non-dominated sorting; returns fronts as lists of indices.

    When ``violation`` is given, Deb's constraint-domination rule replaces plain
    Pareto domination, so feasibility is resolved before objective quality.
    """
    F = np.atleast_2d(np.asarray(F, dtype=float))
    n = F.shape[0]
    viol = np.zeros(n) if violation is None else np.asarray(violation, dtype=float)
    dominated_by: List[List[int]] = [[] for _ in range(n)]
    domination_count = np.zeros(n, dtype=int)
    fronts: List[List[int]] = [[]]
    for p in range(n):
        for q in range(p + 1, n):
            if _constrained_dominates(p, q, F, viol):
                dominated_by[p].append(q)
                domination_count[q] += 1
            elif _constrained_dominates(q, p, F, viol):
                dominated_by[q].append(p)
                domination_count[p] += 1
    fronts[0] = [i for i in range(n) if domination_count[i] == 0]
    current = 0
    while fronts[current]:
        nxt: List[int] = []
        for p in fronts[current]:
            for q in dominated_by[p]:
                domination_count[q] -= 1
                if domination_count[q] == 0:
                    nxt.append(q)
        current += 1
        fronts.append(sorted(nxt))
    return [f for f in fronts if f]


def crowding_distance(F: np.ndarray) -> np.ndarray:
    """NSGA-II crowding distance within one front (boundary points get ``inf``)."""
    F = np.atleast_2d(np.asarray(F, dtype=float))
    n, m = F.shape
    distance = np.zeros(n)
    if n <= 2:
        return np.full(n, np.inf)
    for obj in range(m):
        order = np.argsort(F[:, obj], kind="stable")
        values = F[order, obj]
        distance[order[0]] = distance[order[-1]] = np.inf
        spread = values[-1] - values[0]
        if spread <= 0:
            continue
        distance[order[1:-1]] += (values[2:] - values[:-2]) / spread
    return distance


def hypervolume_2d(F: np.ndarray, reference: Sequence[float]) -> float:
    r"""Eq. (A.3): exact hypervolume of a two-objective set.

    For a non-dominated set sorted by the first objective,
    :math:`HV = \sum_i (r_1 - f_1^{(i)})(f_2^{(i-1)} - f_2^{(i)})` with
    :math:`f_2^{(0)} = r_2`.  Points that do not dominate the reference point
    contribute nothing and are dropped.
    """
    F = np.atleast_2d(np.asarray(F, dtype=float))
    if F.size == 0:
        return 0.0
    if F.shape[1] != 2:
        raise ValueError("hypervolume_2d requires exactly two objectives")
    r = np.asarray(reference, dtype=float)
    keep = np.all(F < r, axis=1)
    F = F[keep]
    if F.shape[0] == 0:
        return 0.0
    fronts = non_dominated_sort(F)
    F = F[fronts[0]]
    order = np.argsort(F[:, 0], kind="stable")
    F = F[order]
    volume = 0.0
    previous_f2 = float(r[1])
    for f1, f2 in F:
        if f2 >= previous_f2:
            continue  # dominated in the sorted sweep
        volume += (float(r[0]) - float(f1)) * (previous_f2 - float(f2))
        previous_f2 = float(f2)
    return float(volume)


def normalized_hypervolume(F: np.ndarray, reference: Sequence[float]) -> float:
    r"""Eq. (21): :math:`HV(\mathcal P; r) / \prod_i r_i`, hence in ``[0, 1]``."""
    r = np.asarray(reference, dtype=float)
    denominator = float(np.prod(r))
    if denominator <= 0:
        raise ValueError("reference point components must be positive for normalisation")
    return float(hypervolume_2d(F, r) / denominator)


def design_diversity(X: np.ndarray, lo: Sequence[float], hi: Sequence[float]) -> float:
    r"""Eq. (22): mean pairwise distance on the normalised Pareto set.

    :math:`D = q^{-1/2}\,\frac{2}{|\mathcal P|(|\mathcal P|-1)}\sum_{i<j}
    \|\tilde d_i - \tilde d_j\|_2` with
    :math:`\tilde d = (d - d^{lo})/(d^{hi} - d^{lo})`.  The ``1/sqrt(q)`` factor
    makes ``D`` comparable across design spaces of different dimension.
    """
    X = np.atleast_2d(np.asarray(X, dtype=float))
    lo = np.asarray(lo, dtype=float)
    hi = np.asarray(hi, dtype=float)
    n, q = X.shape
    if n < 2:
        return 0.0
    span = np.where(hi - lo > 0, hi - lo, 1.0)
    Z = (X - lo) / span
    total = 0.0
    for i in range(n - 1):
        total += float(np.sum(np.linalg.norm(Z[i + 1:] - Z[i], axis=1)))
    mean_distance = 2.0 * total / (n * (n - 1))
    return float(mean_distance / np.sqrt(q))


@dataclass
class SearchResult:
    """Output of Algorithm 1."""

    archive: np.ndarray                 # A: non-dominated feasible designs
    archive_objectives: np.ndarray
    population: np.ndarray
    objectives: np.ndarray
    constraints: np.ndarray
    feasible_fraction_per_generation: List[float] = field(default_factory=list)
    evaluations: int = 0
    seed: int = 0
    arm: str = ""

    @property
    def iterations_to_specification(self) -> float:
        r"""Eq. (23): ``ITS = min{g : FSR_g > 0}``, capped at ``T`` if never reached."""
        for generation, fraction in enumerate(self.feasible_fraction_per_generation, start=1):
            if fraction > 0:
                return float(generation)
        return float(len(self.feasible_fraction_per_generation))

    @property
    def feasible_solution_rate(self) -> float:
        """Eq. (20): ``FSR = |X_feas| / N`` in the final population."""
        if self.feasible_fraction_per_generation:
            return float(self.feasible_fraction_per_generation[-1])
        return 0.0


def search(
    evaluator: Callable[[np.ndarray], Tuple[np.ndarray, np.ndarray]],
    sampler: Callable[[int, np.random.Generator], np.ndarray],
    lo: Sequence[float],
    hi: Sequence[float],
    population_size: int = 40,
    generations: int = 25,
    seed: int = 0,
    sigma: float = 0.10,
    arm: str = "",
    projection: Optional[Callable[[np.ndarray], np.ndarray]] = None,
) -> SearchResult:
    """Algorithm 1: evolution-informed constrained multi-objective search.

    Parameters
    ----------
    evaluator:
        Maps a population ``X`` to ``(F, G)``: objectives to minimise and
        constraint margins (``>= 0`` feasible).
    sampler:
        Draws the initial population from the analog-shaped prior ``p_c``
        (arm C) or uniformly on ``D`` (arm B).  This, together with the
        trade-off constraints folded into ``evaluator``, is the *only*
        difference between the computational arms.
    projection:
        Optional map applied to every offspring, used by the arm-A stand-in to
        keep its designs on a template family.  Arms B and C never use it, so
        their comparison remains attributable to the prior alone.
    """
    rng = np.random.default_rng(seed)
    lo = np.asarray(lo, dtype=float)
    hi = np.asarray(hi, dtype=float)
    span = np.where(hi - lo > 0, hi - lo, 1.0)

    X = np.clip(np.asarray(sampler(population_size, rng), dtype=float), lo, hi)
    F, G = evaluator(X)
    evaluations = X.shape[0]
    feasible_log: List[float] = []

    for _ in range(int(generations)):
        # lines 4-5: uniform crossover in normalised space, then Gaussian mutation
        Z = (X - lo) / span
        partner = Z[rng.permutation(Z.shape[0])]
        mask = rng.random(Z.shape) < 0.5
        child = np.where(mask, Z, partner)
        child = np.clip(child + rng.normal(0.0, sigma, size=child.shape), 0.0, 1.0)
        X_new = lo + child * span
        if projection is not None:
            X_new = np.clip(np.asarray(projection(X_new), dtype=float), lo, hi)

        F_new, G_new = evaluator(X_new)
        evaluations += X_new.shape[0]

        # lines 7-9: merge, rank by constrained non-domination, fill by violation
        X_all = np.vstack([X, X_new])
        F_all = np.vstack([F, F_new])
        G_all = np.vstack([G, G_new])
        violation = constraint_violation(G_all)
        feasible_mask = violation <= 0

        selected: List[int] = []
        feasible_idx = np.flatnonzero(feasible_mask)
        if feasible_idx.size:
            for front in non_dominated_sort(F_all[feasible_idx]):
                front_idx = feasible_idx[front]
                if len(selected) + len(front_idx) <= population_size:
                    selected.extend(int(i) for i in front_idx)
                else:
                    room = population_size - len(selected)
                    distances = crowding_distance(F_all[front_idx])
                    order = np.argsort(-distances, kind="stable")
                    selected.extend(int(front_idx[i]) for i in order[:room])
                    break
                if len(selected) >= population_size:
                    break
        if len(selected) < population_size:  # line 9
            infeasible_idx = np.flatnonzero(~feasible_mask)
            order = np.argsort(violation[infeasible_idx], kind="stable")
            room = population_size - len(selected)
            selected.extend(int(infeasible_idx[i]) for i in order[:room])

        selected_arr = np.asarray(selected[:population_size], dtype=int)
        X, F, G = X_all[selected_arr], F_all[selected_arr], G_all[selected_arr]
        feasible_log.append(float(np.mean(constraint_violation(G) <= 0)))  # line 10

    # lines 12-13: the archive is the non-dominated feasible part of X
    feasible_mask = constraint_violation(G) <= 0
    if np.any(feasible_mask):
        idx = np.flatnonzero(feasible_mask)
        fronts = non_dominated_sort(F[idx])
        archive_idx = idx[fronts[0]]
    else:
        archive_idx = np.asarray([], dtype=int)

    return SearchResult(
        archive=X[archive_idx],
        archive_objectives=F[archive_idx],
        population=X,
        objectives=F,
        constraints=G,
        feasible_fraction_per_generation=feasible_log,
        evaluations=evaluations,
        seed=seed,
        arm=arm,
    )
