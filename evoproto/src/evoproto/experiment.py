"""Three-arm protocol runner and statistical analysis plan (Section 7).

The runner executes the factorial design of Section 7.5 - arms x tasks x
seeded replicates - and computes the four metrics of Section 7.4:

* ``FSR``  feasible-solution rate of the final population (Eq. 20);
* ``HV``   normalized hypervolume of the feasible Pareto set (Eq. 21);
* ``D``    design diversity on the Pareto set (Eq. 22);
* ``ITS``  iterations to specification, capped at ``T`` (Eq. 23).

The analysis plan of Section 7.6 is implemented alongside: cells are paired by
``(task, replicate seed)``; each contrast is tested with the two-sided Wilcoxon
signed-rank test [60]; p-values are corrected with the Holm step-down procedure
[61]; effect sizes are reported as Cliff's delta [62] and as median paired
differences with bootstrap confidence intervals [63].  No result is described
as significant without its Holm-adjusted p-value and its effect size.

Arms B and C differ only in the sampling prior and the constraints derived from
evolutionary data; the evaluator, the budget and the seeds are shared.  Arm A
is a human baseline matched in wall-clock time rather than in evaluations, and
in this package it is a **synthetic stand-in** (see
:func:`evoproto.optimize.heuristic_refinement_search`).
"""

from __future__ import annotations

import json
import platform
import sys
from collections.abc import Iterable, Sequence
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

import numpy as np

from evoproto.data import Tag, stable_seed
from evoproto.design import (
    BracketSpec,
    analog_prior_sampler,
    bounds_array,
    evaluate_population,
    template_ratio_sampler,
    uniform_sampler,
)
from evoproto.optimize import (
    ApproxSet,
    constrained_search,
    design_diversity,
    heuristic_refinement_search,
    normalized_hypervolume,
)

__all__ = [
    "ARMS",
    "TASKS",
    "CellResult",
    "ProtocolResult",
    "bootstrap_ci",
    "cliffs_delta",
    "environment_record",
    "holm_correction",
    "metrics_from_result",
    "paired_contrast",
    "required_pairs",
    "run_cell",
    "run_protocol",
    "wilcoxon_signed_rank",
]

#: Arm labels and what distinguishes them (Section 7.2).
ARMS: dict[str, str] = {
    "A": "expert biomimetic search (human baseline; SYNTHETIC stand-in here)",
    "B": "generative design without evolutionary data (uniform prior on D)",
    "C": "proposed framework (analog-shaped prior p_c and trade-off constraints)",
}


# --------------------------------------------------------------------- metrics
def metrics_from_result(
    result: ApproxSet,
    lower: np.ndarray,
    upper: np.ndarray,
    reference: Sequence[float],
    generations: int,
) -> dict[str, float]:
    """The four metrics of Eqs. (20)-(23) for one arm-task-replicate cell."""
    pareto_x, pareto_f = result.pareto()
    return {
        "FSR": float(np.mean(result.feasible)) if len(result.feasible) else 0.0,
        "HV": float(normalized_hypervolume(pareto_f, reference)),
        "D": float(design_diversity(pareto_x, lower, upper)) if len(pareto_x) > 1 else 0.0,
        "ITS": float(result.iterations_to_specification(cap=generations)),
        "evaluations": float(result.evaluations),
        "n_pareto": float(len(pareto_x)),
    }


# ----------------------------------------------------------------------- tasks
@dataclass(frozen=True)
class Task:
    """One task family of Section 7.3."""

    identifier: str
    description: str
    implemented: bool = True
    spec: Any = None


TASKS: dict[str, Task] = {
    "T1": Task(
        "T1",
        "EOAT bracket, LPBF AlSi10Mg; analytic evaluator of Section 6.2",
        implemented=True,
        spec=BracketSpec(),
    ),
    "T2": Task(
        "T2",
        "heat-exchanger fin; objectives heat-transfer rate and pressure drop "
        "[NEEDS INPUT: CFD evaluator, to be implemented with the partner's solver]",
        implemented=False,
    ),
    "T3": Task(
        "T3",
        "compliant gripper finger; objectives grasp-force uniformity and actuation "
        "energy [NEEDS INPUT: contact-mechanics evaluator]",
        implemented=False,
    ),
}


@dataclass
class CellResult:
    """Result of one (task, arm, replicate) cell, with its provenance tag."""

    task: str
    arm: str
    replicate: int
    seed: int
    metrics: dict[str, float]
    tag: str = Tag.SYNTHETIC.value
    log: list[dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class ProtocolResult:
    """Every cell of a protocol run plus the statistics computed over them."""

    cells: list[CellResult]
    statistics: dict[str, Any]
    configuration: dict[str, Any]
    environment: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return {
            "cells": [c.to_dict() for c in self.cells],
            "statistics": self.statistics,
            "configuration": self.configuration,
            "environment": self.environment,
        }

    def table(
        self, metrics: Sequence[str] = ("FSR", "HV", "D", "ITS")
    ) -> dict[str, dict[str, str]]:
        """Mean +- SD per arm and metric, in the layout of Table 7."""
        out: dict[str, dict[str, str]] = {}
        for arm in sorted({c.arm for c in self.cells}):
            values = {
                m: np.array([c.metrics[m] for c in self.cells if c.arm == arm], dtype=float)
                for m in metrics
            }
            out[arm] = {
                m: f"{v.mean():.3f} ± {v.std(ddof=1) if len(v) > 1 else 0.0:.3f}"
                for m, v in values.items()
            }
        return out

    def save(self, directory: str | Path) -> Path:
        """Write ``results.json`` and ``cells.csv`` into ``directory``."""
        directory = Path(directory)
        directory.mkdir(parents=True, exist_ok=True)
        (directory / "results.json").write_text(
            json.dumps(self.to_dict(), indent=2, sort_keys=True), encoding="utf-8"
        )
        header = ["task", "arm", "replicate", "seed", "tag", "FSR", "HV", "D", "ITS",
                  "evaluations", "n_pareto"]
        lines = [",".join(header)]
        for cell in self.cells:
            lines.append(
                ",".join(
                    [cell.task, cell.arm, str(cell.replicate), str(cell.seed), cell.tag]
                    + [f"{cell.metrics[k]:.6g}" for k in header[5:]]
                )
            )
        (directory / "cells.csv").write_text("\n".join(lines) + "\n", encoding="utf-8")
        return directory


# ------------------------------------------------------------------ statistics
def wilcoxon_signed_rank(differences: Sequence[float]) -> dict[str, float]:
    """Two-sided Wilcoxon signed-rank test on paired differences [60].

    SciPy performs the test; zero differences are discarded by the ``wilcox``
    convention and, when every difference is zero, the test is undefined and a
    p-value of 1.0 is reported with ``n_effective = 0`` - a case that occurs in
    the dry run whenever two arms saturate a metric.
    """
    d = np.asarray(list(differences), dtype=float)
    nonzero = d[d != 0]
    if nonzero.size == 0:
        return {"statistic": float("nan"), "p_value": 1.0, "n_effective": 0.0}
    from scipy.stats import wilcoxon

    statistic, p_value = wilcoxon(nonzero, alternative="two-sided", zero_method="wilcox")
    return {
        "statistic": float(statistic),
        "p_value": float(p_value),
        "n_effective": float(nonzero.size),
    }


def holm_correction(p_values: Sequence[float]) -> list[float]:
    """Holm step-down adjusted p-values [61], in the input order.

    Adjusted values are made monotone non-decreasing along the sorted order and
    clipped at 1, which is the standard reporting convention.
    """
    p = np.asarray(list(p_values), dtype=float)
    n = p.size
    if n == 0:
        return []
    order = np.argsort(p, kind="stable")
    adjusted = np.empty(n)
    running = 0.0
    for rank, index in enumerate(order):
        value = (n - rank) * p[index]
        running = max(running, value)
        adjusted[index] = min(1.0, running)
    return [float(v) for v in adjusted]


def cliffs_delta(a: Sequence[float], b: Sequence[float]) -> dict[str, Any]:
    """Cliff's delta with the conventional magnitude labels [62].

    ``|delta| < 0.147`` negligible, ``< 0.33`` small, ``< 0.474`` medium,
    otherwise large.
    """
    x = np.asarray(list(a), dtype=float)
    y = np.asarray(list(b), dtype=float)
    if x.size == 0 or y.size == 0:
        return {"delta": float("nan"), "magnitude": "undefined"}
    greater = float(np.sum(x[:, None] > y[None, :]))
    less = float(np.sum(x[:, None] < y[None, :]))
    delta = (greater - less) / (x.size * y.size)
    magnitude = (
        "negligible" if abs(delta) < 0.147
        else "small" if abs(delta) < 0.33
        else "medium" if abs(delta) < 0.474
        else "large"
    )
    return {"delta": float(delta), "magnitude": magnitude}


def bootstrap_ci(
    differences: Sequence[float],
    n_resamples: int = 2000,
    confidence: float = 0.95,
    seed: int = 0,
) -> dict[str, float]:
    """Percentile bootstrap CI of the median paired difference [63]."""
    d = np.asarray(list(differences), dtype=float)
    if d.size == 0:
        return {"median": float("nan"), "low": float("nan"), "high": float("nan")}
    rng = np.random.default_rng(seed)
    draws = rng.integers(0, d.size, size=(int(n_resamples), d.size))
    medians = np.median(d[draws], axis=1)
    alpha = (1.0 - confidence) / 2.0
    return {
        "median": float(np.median(d)),
        "low": float(np.quantile(medians, alpha)),
        "high": float(np.quantile(medians, 1.0 - alpha)),
        "n_resamples": float(n_resamples),
        "confidence": float(confidence),
    }


def paired_contrast(
    cells: Sequence[CellResult],
    task: str,
    arm_x: str,
    arm_y: str,
    metric: str,
    n_resamples: int = 2000,
    seed: int = 0,
) -> dict[str, Any]:
    """One contrast (``arm_x`` versus ``arm_y``) on one metric of one task.

    Cells are paired by replicate index, as required by Section 7.6: the arms
    share the seed derivation, so replicate ``k`` of arm C faces the same
    randomness as replicate ``k`` of arm B.
    """
    by_replicate_x = {c.replicate: c.metrics[metric] for c in cells
                      if c.task == task and c.arm == arm_x}
    by_replicate_y = {c.replicate: c.metrics[metric] for c in cells
                      if c.task == task and c.arm == arm_y}
    shared = sorted(set(by_replicate_x) & set(by_replicate_y))
    x = [by_replicate_x[r] for r in shared]
    y = [by_replicate_y[r] for r in shared]
    differences = [xi - yi for xi, yi in zip(x, y)]
    test = wilcoxon_signed_rank(differences)
    return {
        "task": task,
        "contrast": f"{arm_x} vs {arm_y}",
        "metric": metric,
        "n_pairs": len(shared),
        "p_value": test["p_value"],
        "statistic": test["statistic"],
        "cliffs_delta": cliffs_delta(x, y),
        "bootstrap": bootstrap_ci(differences, n_resamples, seed=seed),
        "mean_x": float(np.mean(x)) if x else float("nan"),
        "mean_y": float(np.mean(y)) if y else float("nan"),
    }


# --------------------------------------------------------------------- runner
def run_cell(
    task: str,
    arm: str,
    replicate: int,
    population: int = 40,
    generations: int = 25,
    spec: BracketSpec | None = None,
    n_variants: int = 4,
) -> CellResult:
    """Run one (task, arm, replicate) cell with its derived seed.

    The seed comes from :func:`evoproto.data.stable_seed`, so the cell is
    reproducible across machines and cannot collide with another arm's stream.
    """
    task_def = TASKS.get(task)
    if task_def is None:
        raise KeyError(f"unknown task {task!r}; known tasks: {sorted(TASKS)}")
    if not task_def.implemented:
        raise NotImplementedError(
            f"task {task} has no evaluator in this reference implementation: "
            f"{task_def.description}"
        )
    if arm not in ARMS:
        raise KeyError(f"unknown arm {arm!r}; known arms: {sorted(ARMS)}")

    spec = spec or task_def.spec or BracketSpec()
    lower, upper = bounds_array(spec)
    reference = np.array([spec.mass_max, spec.delta_max], dtype=float)
    seed = stable_seed(task, arm, replicate)

    def evaluator(x: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
        f, g, _ = evaluate_population(x, spec)
        return f, g

    if arm == "A":
        result = heuristic_refinement_search(
            evaluator, template_ratio_sampler(spec), lower, upper,
            n_variants=n_variants, rounds=generations, seed=seed, arm=arm,
        )
    else:
        sampler = uniform_sampler(spec) if arm == "B" else analog_prior_sampler(spec)
        result = constrained_search(
            evaluator, sampler, lower, upper,
            population=population, generations=generations, seed=seed, arm=arm,
        )

    return CellResult(
        task=task,
        arm=arm,
        replicate=replicate,
        seed=seed,
        metrics=metrics_from_result(result, lower, upper, reference, generations),
        tag=Tag.SYNTHETIC.value,
        log=result.log,
    )


def run_protocol(
    tasks: Iterable[str] = ("T1",),
    arms: Iterable[str] = ("A", "B", "C"),
    replicates: int = 10,
    population: int = 40,
    generations: int = 25,
    metrics: Sequence[str] = ("FSR", "HV", "D", "ITS"),
    contrasts: Sequence[tuple[str, str]] = (("C", "B"), ("C", "A")),
    n_resamples: int = 2000,
    alpha: float = 0.05,
    spec: BracketSpec | None = None,
) -> ProtocolResult:
    """Run the factorial design and the analysis plan (Sections 7.5-7.6).

    Holm correction is applied *within a task* over the family of
    ``len(contrasts) x len(metrics)`` tests, which for the default two
    contrasts and four metrics is the family of eight p-values per task named
    in Section 7.6.

    Every cell produced by this function is tagged SYNTHETIC: the bundled
    evaluator is analytic and arms A and C use stand-in and hand-set priors, so
    the run tests the pipeline, not the hypotheses H1-H3 (Section 7.7).
    """
    tasks = list(tasks)
    arms = list(arms)
    cells = [
        run_cell(task, arm, replicate, population, generations, spec)
        for task in tasks
        for arm in arms
        for replicate in range(int(replicates))
    ]

    statistics: dict[str, Any] = {"alpha": alpha, "correction": "Holm (within task)"}
    for task in tasks:
        rows = [
            paired_contrast(cells, task, x, y, metric, n_resamples)
            for x, y in contrasts
            for metric in metrics
            if x in arms and y in arms
        ]
        adjusted = holm_correction([row["p_value"] for row in rows])
        for row, p_adj in zip(rows, adjusted):
            row["p_holm"] = p_adj
            row["significant"] = bool(p_adj <= alpha)
        statistics[task] = rows

    configuration = {
        "tasks": tasks,
        "arms": {a: ARMS[a] for a in arms},
        "replicates": int(replicates),
        "population": int(population),
        "generations": int(generations),
        "metrics": list(metrics),
        "contrasts": [f"{x} vs {y}" for x, y in contrasts],
        "bootstrap_resamples": int(n_resamples),
        "alpha": float(alpha),
        "specification": (spec or BracketSpec()).to_dict(),
        "provenance_tag": Tag.SYNTHETIC.value,
    }
    return ProtocolResult(
        cells=cells,
        statistics=statistics,
        configuration=configuration,
        environment=environment_record(),
    )


def environment_record() -> dict[str, Any]:
    """Machine-readable environment capture for the reproducibility appendix."""
    import importlib

    versions: dict[str, str] = {}
    for name in ("numpy", "scipy", "networkx", "matplotlib"):
        try:
            versions[name] = importlib.import_module(name).__version__
        except Exception:  # pragma: no cover - reporting must never fail a run
            versions[name] = "not installed"
    from evoproto import __version__

    return {
        "evoproto": __version__,
        "python": sys.version.split()[0],
        "platform": platform.platform(),
        "machine": platform.machine(),
        "packages": versions,
    }


def required_pairs(effect_size: float, power: float = 0.80, alpha: float = 0.05,
                   efficiency: float = 0.955) -> float:
    """Replicates needed for a paired Wilcoxon test at a given effect (Eq. 24).

    .. math:: n \\approx \\frac{(z_{1-\\alpha/2} + z_{1-\\beta})^2}{\\text{ARE}\\,\\Delta^2}

    With ``alpha = 0.05`` two-sided (before correction), power 0.8 and ARE
    0.955, an effect of ``Delta = 1.0`` needs about 9 pairs and ``Delta = 0.8``
    about 14.  Ten replicates therefore detect large effects only - recorded as
    a limitation in Section 8.3.
    """
    from scipy.stats import norm

    if effect_size <= 0:
        raise ValueError("effect_size must be positive")
    z_alpha = float(norm.ppf(1.0 - alpha / 2.0))
    z_beta = float(norm.ppf(power))
    return float((z_alpha + z_beta) ** 2 / (efficiency * effect_size**2))
