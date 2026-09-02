"""Variation and constraint-handling operators shared by NSGA-II and NSGA-III.

Both evolutionary methods use identical initialization, crossover, mutation,
selection and repair, so any difference between them comes from the survival
step alone. That is what makes the paired comparison in ``experiment.py`` fair.
"""

from __future__ import annotations

import numpy as np

from .model import PortfolioModel


def repair(model: PortfolioModel, x: np.ndarray, rng: np.random.Generator,
           max_iterations: int = 200) -> np.ndarray:
    """Greedily push one portfolio into the feasible set.

    The loop drops the least efficient selected system while a resource
    constraint is violated, and adds the most useful unselected system while
    criticality coverage falls short. It terminates either at a feasible
    portfolio or after ``max_iterations`` steps; callers must still check
    feasibility, because some instances admit no repair from some starting points.
    """
    inst = model.instance
    x = np.asarray(x, dtype=float).copy()

    if x.sum() == 0:
        x[rng.integers(inst.n)] = 1.0

    # Efficiency score: benefit per unit of combined pressure on the two
    # resource constraints, each expressed as a fraction of its own bound so
    # that cost and effort are commensurate. Used to pick what to drop.
    pressure = inst.cost / model.budget + inst.effort / model.time_cap
    value = model.benefit / np.maximum(pressure, 1e-12)

    for _ in range(max_iterations):
        if model.is_feasible(x):
            return x

        over_cost = x @ inst.cost - model.budget
        over_time = x @ inst.effort - model.time_cap
        low_reliability = -(x @ model.reliability_slack)
        low_technical = -(x @ model.technical_slack)
        low_coverage = model.coverage_minimum - x @ inst.criticality

        selected = np.flatnonzero(x > 0.5)
        unselected = np.flatnonzero(x < 0.5)

        if low_reliability > 0 or low_technical > 0:
            # Remove the selected system that hurts the binding average most.
            if len(selected) == 0:
                break
            harm = np.zeros(len(selected))
            if low_reliability > 0:
                harm += -model.reliability_slack[selected]
            if low_technical > 0:
                harm += -model.technical_slack[selected]
            candidates = selected[harm > 0]
            if len(candidates) == 0:
                break
            worst = candidates[np.argmin(value[candidates])]
            x[worst] = 0.0
        elif over_cost > 0 or over_time > 0:
            if len(selected) <= 1:
                break
            x[selected[np.argmin(value[selected])]] = 0.0
        elif low_coverage > 0:
            if len(unselected) == 0:
                break
            # Prefer systems that close the coverage gap without pushing the
            # portfolio back over a resource bound.
            affordable = (
                (x @ inst.cost + inst.cost[unselected] <= model.budget)
                & (x @ inst.effort + inst.effort[unselected] <= model.time_cap)
            )
            pool = unselected[affordable] if np.any(affordable) else unselected
            gain = inst.criticality[pool]
            x[pool[np.argmax(gain)]] = 1.0
        else:
            break

    if x.sum() == 0:
        x[rng.integers(inst.n)] = 1.0
    return x


def initialize_population(
    model: PortfolioModel,
    size: int,
    rng: np.random.Generator,
    max_iterations: int = 200,
) -> np.ndarray:
    """Feasible initial population.

    Random bit strings are drawn with a moderate inclusion probability and then
    repaired. Individuals that repair fails to fix are resampled; after a bounded
    number of attempts the routine falls back to a greedy feasible seed so that
    a run never starts empty.
    """
    n = model.instance.n
    population: list[np.ndarray] = []
    attempts = 0
    while len(population) < size and attempts < size * 50:
        attempts += 1
        x = (rng.random(n) < rng.uniform(0.3, 0.7)).astype(float)
        x = repair(model, x, rng, max_iterations)
        if model.is_feasible(x):
            population.append(x)

    if len(population) < size:
        seed = _greedy_feasible(model)
        while len(population) < size:
            population.append(seed.copy())

    return np.array(population, dtype=float)


def _greedy_feasible(model: PortfolioModel) -> np.ndarray:
    """Deterministic feasible fallback: add systems by benefit-to-cost order."""
    inst = model.instance
    x = np.zeros(inst.n, dtype=float)
    order = np.argsort(-(model.benefit / np.maximum(inst.cost, 1e-12)))
    for i in order:
        trial = x.copy()
        trial[i] = 1.0
        if (
            trial @ inst.cost <= model.budget
            and trial @ inst.effort <= model.time_cap
        ):
            x = trial
        if model.is_feasible(x):
            return x
    return x


def binary_tournament(
    rank: np.ndarray, diversity: np.ndarray, count: int, rng: np.random.Generator
) -> np.ndarray:
    """Binary tournament on (rank asc, diversity desc)."""
    a = rng.integers(len(rank), size=count)
    b = rng.integers(len(rank), size=count)
    better = np.where(
        rank[a] != rank[b], rank[a] < rank[b], diversity[a] > diversity[b]
    )
    return np.where(better, a, b)


def uniform_crossover(
    parents: np.ndarray, probability: float, rng: np.random.Generator
) -> np.ndarray:
    """Uniform crossover over consecutive parent pairs."""
    children = parents.copy()
    for i in range(0, len(children) - 1, 2):
        if rng.random() < probability:
            swap = rng.random(children.shape[1]) < 0.5
            children[i, swap], children[i + 1, swap] = (
                children[i + 1, swap].copy(),
                children[i, swap].copy(),
            )
    return children


def bit_flip_mutation(
    children: np.ndarray, probability: float, rng: np.random.Generator
) -> np.ndarray:
    """Independent bit-flip mutation; p = 1/n gives one expected flip per child."""
    flip = rng.random(children.shape) < probability
    return np.where(flip, 1.0 - children, children)
