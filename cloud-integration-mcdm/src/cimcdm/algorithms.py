"""NSGA-II, a reference-direction (NSGA-III-type) variant, and the weighted sum.

The two evolutionary methods share initialization, variation, repair, selection
and generation budget; they differ only in how survivors are chosen from the
critical front. NSGA-II uses crowding distance, the NSGA-III-type variant uses
Das-Dennis reference directions with min-max normalization.

As the article notes, the reference-direction method is labelled "NSGA-III" for
brevity but is not a full reproduction of every normalization step of the
canonical algorithm.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from itertools import combinations_with_replacement

import numpy as np

from .config import DEFAULT_ALGORITHM, AlgorithmConfig
from .metrics import hypervolume
from .model import PortfolioModel
from .operators import (
    binary_tournament,
    bit_flip_mutation,
    initialize_population,
    repair,
    uniform_crossover,
)
from .pareto import ParetoArchive, nondominated_mask, nondominated_sort


@dataclass
class RunResult:
    """One replication of one evolutionary method."""

    method: str
    seed: int
    X: np.ndarray
    F: np.ndarray
    hypervolume_history: np.ndarray
    """Archive hypervolume after generation 0, 1, ..., ``generations``."""
    cpu_time: float
    generations: int

    @property
    def front_size(self) -> int:
        return len(self.F)


def das_dennis_directions(n_objectives: int, divisions: int) -> np.ndarray:
    """Das-Dennis simplex lattice.

    Returns ``C(divisions + n_objectives - 1, n_objectives - 1)`` points; for
    three objectives and H = 9 that is 55 directions, and H = 20 gives 231.
    """
    points = []
    for cuts in combinations_with_replacement(range(n_objectives), divisions):
        weight = np.zeros(n_objectives)
        for c in cuts:
            weight[c] += 1.0
        points.append(weight / divisions)
    return np.unique(np.array(points), axis=0)


def crowding_distance(F: np.ndarray) -> np.ndarray:
    """Standard NSGA-II crowding distance within one front."""
    size, n_obj = F.shape
    if size <= 2:
        return np.full(size, np.inf)
    distance = np.zeros(size)
    for m in range(n_obj):
        order = np.argsort(F[:, m], kind="stable")
        values = F[order, m]
        distance[order[0]] = distance[order[-1]] = np.inf
        span = values[-1] - values[0]
        if span <= 0:
            continue
        distance[order[1:-1]] += (values[2:] - values[:-2]) / span
    return distance


def _normalize(F: np.ndarray) -> np.ndarray:
    """Min-max normalization used by the reference-direction survival step."""
    ideal, nadir = F.min(axis=0), F.max(axis=0)
    span = np.where(nadir - ideal > 1e-12, nadir - ideal, 1.0)
    return (F - ideal) / span


def _reference_association(F: np.ndarray, directions: np.ndarray):
    """Associate each solution with its nearest reference direction.

    Distance is the perpendicular distance to the line through the origin along
    the (unit-normalized) direction, as in NSGA-III.
    """
    unit = directions / np.maximum(
        np.linalg.norm(directions, axis=1, keepdims=True), 1e-12
    )
    projection = F @ unit.T
    perpendicular = np.sqrt(
        np.maximum((F ** 2).sum(axis=1)[:, None] - projection ** 2, 0.0)
    )
    nearest = perpendicular.argmin(axis=1)
    return nearest, perpendicular[np.arange(len(F)), nearest]


def _niching_survival(
    F_all: np.ndarray,
    fronts: list[np.ndarray],
    n_survivors: int,
    directions: np.ndarray,
    rng: np.random.Generator,
) -> np.ndarray:
    """NSGA-III-type survival: fill by front, then niche on the critical front.

    Ties are broken randomly, both when choosing the least-crowded niche and when
    choosing among the members of an already-occupied one. That randomness is not
    cosmetic: with deterministic tie-breaks the survival step becomes a fixed
    point, the same individuals survive every generation, and the nondominated
    archive stops growing well before the generation budget is spent.
    """
    survivors: list[int] = []
    critical: np.ndarray | None = None
    for front in fronts:
        if len(survivors) + len(front) <= n_survivors:
            survivors.extend(front.tolist())
        else:
            critical = front
            break
    if critical is None or len(survivors) >= n_survivors:
        return np.array(survivors[:n_survivors], dtype=int)

    pool = np.array(survivors + critical.tolist(), dtype=int)
    normalized = _normalize(F_all[pool])
    association, distance = _reference_association(normalized, directions)

    n_directions = len(directions)
    counts = np.zeros(n_directions, dtype=int)
    for i in range(len(survivors)):
        counts[association[i]] += 1

    # Candidates grouped by the niche they are associated with.
    members: dict[int, list[int]] = {}
    for i in range(len(survivors), len(pool)):
        members.setdefault(int(association[i]), []).append(i)

    chosen = list(range(len(survivors)))
    while len(chosen) < n_survivors and members:
        occupancy = min(counts[niche] for niche in members)
        least_crowded = [niche for niche in members if counts[niche] == occupancy]
        niche = int(rng.choice(least_crowded))

        pool_members = members[niche]
        if counts[niche] == 0:
            # Empty niche: take the solution closest to the reference direction.
            pick = min(pool_members, key=lambda i: distance[i])
        else:
            pick = int(rng.choice(pool_members))

        chosen.append(pick)
        pool_members.remove(pick)
        if not pool_members:
            del members[niche]
        counts[niche] += 1

    return pool[np.array(sorted(chosen), dtype=int)]


def _evolve(
    model: PortfolioModel,
    method: str,
    seed: int,
    config: AlgorithmConfig = DEFAULT_ALGORITHM,
) -> RunResult:
    """Shared generational loop; ``method`` selects the survival operator."""
    rng = np.random.default_rng(seed)
    n = model.instance.n
    mutation_p = (
        config.mutation_probability
        if config.mutation_probability is not None
        else 1.0 / n
    )
    directions = das_dennis_directions(3, config.das_dennis_divisions)
    reference_point = model.scenario.reference_point

    start = time.process_time()

    population = initialize_population(
        model, config.population, rng, config.repair_max_iterations
    )
    F = model.objectives(population)

    archive = ParetoArchive().update(population, F)
    history = [hypervolume(archive.front, reference_point)]

    for _ in range(config.generations):
        fronts = nondominated_sort(F)
        rank = np.empty(len(F), dtype=int)
        for level, front in enumerate(fronts):
            rank[front] = level
        diversity = np.empty(len(F))
        for front in fronts:
            diversity[front] = crowding_distance(F[front])

        parents_index = binary_tournament(rank, diversity, config.population, rng)
        children = uniform_crossover(
            population[parents_index], config.crossover_probability, rng
        )
        children = bit_flip_mutation(children, mutation_p, rng)
        children = np.array(
            [repair(model, child, rng, config.repair_max_iterations) for child in children]
        )
        feasible = model.is_feasible(children)
        if not np.all(feasible):
            children = children[feasible] if np.any(feasible) else population[:1]

        merged = np.vstack([population, children])
        F_merged = model.objectives(merged)

        merged_fronts = nondominated_sort(F_merged)
        if method == "NSGA-II":
            survivors = _crowding_survival(F_merged, merged_fronts, config.population)
        else:
            survivors = _niching_survival(
                F_merged, merged_fronts, config.population, directions, rng
            )

        population, F = merged[survivors], F_merged[survivors]
        archive.update(population, F)
        history.append(hypervolume(archive.front, reference_point))

    cpu_time = time.process_time() - start

    return RunResult(
        method=method,
        seed=seed,
        X=archive.X,
        F=archive.front,
        hypervolume_history=np.array(history),
        cpu_time=cpu_time,
        generations=config.generations,
    )


def _crowding_survival(
    F_all: np.ndarray, fronts: list[np.ndarray], n_survivors: int
) -> np.ndarray:
    """NSGA-II survival: fill by front, truncate the critical front by crowding."""
    survivors: list[int] = []
    for front in fronts:
        if len(survivors) + len(front) <= n_survivors:
            survivors.extend(front.tolist())
        else:
            remaining = n_survivors - len(survivors)
            distance = crowding_distance(F_all[front])
            order = np.argsort(-distance, kind="stable")
            survivors.extend(front[order[:remaining]].tolist())
            break
    return np.array(survivors[:n_survivors], dtype=int)


def run_nsga2(model, seed, config=DEFAULT_ALGORITHM) -> RunResult:
    """NSGA-II with nondominated sorting and crowding distance."""
    return _evolve(model, "NSGA-II", seed, config)


def run_nsga3(model, seed, config=DEFAULT_ALGORITHM) -> RunResult:
    """Reference-direction survival on Das-Dennis directions (labelled NSGA-III)."""
    return _evolve(model, "NSGA-III", seed, config)


def run_weighted_sum(
    model: PortfolioModel,
    F_feasible: np.ndarray,
    X_feasible: np.ndarray,
    config: AlgorithmConfig = DEFAULT_ALGORITHM,
):
    """Deterministic weighted-sum baseline over the enumerated feasible set.

    Scores every feasible portfolio under each of the simplex-lattice weight
    vectors and keeps the per-weight minimizers, then filters them for dominance.

    The reported time covers scalar scoring only: the feasible matrix is assumed
    already available, so this is *not* an end-to-end runtime comparable with the
    evolutionary methods.
    """
    weights = das_dennis_directions(3, config.wsm_divisions)
    start = time.process_time()
    scores = F_feasible @ weights.T
    winners = np.unique(scores.argmin(axis=0))
    cpu_time = time.process_time() - start

    X, F = X_feasible[winners], F_feasible[winners]
    mask = nondominated_mask(F)
    X, F = X[mask], F[mask]

    return RunResult(
        method="WSM",
        seed=-1,
        X=X,
        F=F,
        hypervolume_history=np.array([hypervolume(F, model.scenario.reference_point)]),
        cpu_time=cpu_time,
        generations=0,
    ), len(weights)
