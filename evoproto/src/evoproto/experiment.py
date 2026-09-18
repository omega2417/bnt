"""The three-arm protocol and its statistical analysis plan (Section 7).

Runner
------
``run_protocol`` executes arms x tasks x seeded replicates.  Arms B and C differ
only in the sampling prior and in the trade-off constraints taken from the
EE-KG; the evaluator, the budget and the seeds are shared, so any difference
between them is attributable to the evolutionary data.  Arm A is the
template-ratio stand-in of Section 7.7, matched in wall-clock time rather than
in evaluations.

Metrics (Section 7.4)
---------------------
Eq. (20) FSR, Eq. (21) normalised hypervolume, Eq. (22) design diversity,
Eq. (23) iterations to specification.

Analysis plan (Section 7.6)
---------------------------
Two-sided Wilcoxon signed-rank tests on the paired differences, Holm step-down
correction at family-wise 0.05, Cliff's delta with the conventional
interpretation, and median differences with bootstrap confidence intervals.
Eq. (24) gives the number of replicates a given effect size needs.

Every number produced here in demonstration mode carries the tag SYNTHETIC:
the dry run tests the pipeline, not the hypothesis.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, Iterable, List, Mapping, Optional, Sequence, Tuple

import numpy as np

from . import design as design_module
from . import optimize as optimize_module
from .data import PACKAGE_VERSION, CorpusSnapshot, Provenance, ProvenanceTag, stable_seed

__all__ = [
    "ARMS",
    "ArmConfig",
    "CellResult",
    "run_cell",
    "run_protocol",
    "aggregate",
    "wilcoxon_signed_rank",
    "holm_correction",
    "cliffs_delta",
    "cliffs_delta_magnitude",
    "bootstrap_ci",
    "required_replicates",
    "compare_arms",
    "dry_run",
    "ablation",
]

#: Arm labels of Section 7.2.
ARMS: Tuple[str, str, str] = ("A", "B", "C")

#: Metrics compared by the statistical plan; True when larger is better.
METRICS: Dict[str, bool] = {"FSR": True, "HV": True, "D": True, "ITS": False}


@dataclass(frozen=True)
class ArmConfig:
    """One arm of the protocol."""

    label: str
    description: str
    uses_knowledge_graph: bool
    prior: str

    def as_dict(self) -> Dict[str, Any]:
        return {
            "label": self.label,
            "description": self.description,
            "uses_knowledge_graph": self.uses_knowledge_graph,
            "prior": self.prior,
        }


ARM_CONFIGS: Dict[str, ArmConfig] = {
    "A": ArmConfig(
        "A",
        "expert biomimetic search (template-ratio stand-in in the dry run)",
        False,
        "template_ratio_prior",
    ),
    "B": ArmConfig(
        "B", "generative design without evolutionary data", False, "uniform_prior"
    ),
    "C": ArmConfig(
        "C", "proposed framework: analog-shaped prior and trade-off constraints", True, "analog_prior"
    ),
}


@dataclass
class CellResult:
    """One arm-task-replicate cell with the four metrics of Section 7.4."""

    task: str
    arm: str
    replicate: int
    seed: int
    FSR: float
    HV: float
    D: float
    ITS: float
    pareto_size: int
    evaluations: int
    tag: ProvenanceTag = ProvenanceTag.SYNTHETIC

    def as_dict(self) -> Dict[str, Any]:
        return {
            "task": self.task, "arm": self.arm, "replicate": self.replicate,
            "seed": self.seed, "FSR": self.FSR, "HV": self.HV, "D": self.D,
            "ITS": self.ITS, "pareto_size": self.pareto_size,
            "evaluations": self.evaluations, "tag": self.tag.value,
        }


def run_cell(
    task: str = "T1",
    arm: str = "C",
    replicate: int = 0,
    population_size: int = 40,
    generations: int = 25,
    spec: Optional[design_module.BracketSpec] = None,
    trade_off_constraints: bool = True,
    prior_kwargs: Optional[Mapping[str, Any]] = None,
) -> CellResult:
    """Run one cell of the factorial design.

    The seed is derived with :func:`evoproto.data.stable_seed` from
    ``(version, task, arm, replicate)``, so a cell is reproducible across
    machines and no two arms can silently share a seed stream.

    ``trade_off_constraints`` folds the EE-KG ``tradesOffWith`` edges into the
    evaluator for arm C; here the trade-off between stiffness and mass is
    already expressed by the specification, so the flag is carried through the
    result for the ablation of Section 7.5 rather than altering the evaluator.
    """
    if arm not in ARM_CONFIGS:
        raise ValueError(f"unknown arm {arm!r}; expected one of {ARMS}")
    if task != "T1":
        raise NotImplementedError(
            "only task T1 (the EOAT bracket) has a fully specified evaluator in the "
            "reference implementation; the T2 heat-exchanger fin and T3 compliant "
            "gripper evaluators are to be implemented with the partner's solvers "
            "(Section 7.3, NEEDS INPUT)"
        )
    spec = spec or design_module.EOAT_BRACKET
    seed = stable_seed(task, arm, replicate)
    lo, hi = design_module.design_bounds(spec)

    def evaluator(X: np.ndarray) -> Tuple[np.ndarray, np.ndarray]:
        out = design_module.evaluate_population(X, spec)
        return out["F"], out["G"]

    prior = design_module.PRIORS[arm]
    kwargs = dict(prior_kwargs or {})

    def sampler(n: int, rng: np.random.Generator) -> np.ndarray:
        return prior(n, spec, rng, **kwargs)

    projection = design_module.template_projection if arm == "A" else None
    result = optimize_module.search(
        evaluator,
        sampler,
        lo,
        hi,
        population_size=population_size,
        generations=generations,
        seed=seed,
        arm=arm,
        projection=projection,
    )

    if result.archive.shape[0]:
        hv = optimize_module.normalized_hypervolume(result.archive_objectives, spec.reference_point)
        diversity = (
            optimize_module.design_diversity(result.archive, lo, hi)
            if result.archive.shape[0] > 1
            else 0.0
        )
    else:
        hv, diversity = 0.0, 0.0

    return CellResult(
        task=task,
        arm=arm,
        replicate=replicate,
        seed=seed,
        FSR=float(result.feasible_solution_rate),
        HV=float(hv),
        D=float(diversity),
        ITS=float(result.iterations_to_specification),
        pareto_size=int(result.archive.shape[0]),
        evaluations=int(result.evaluations),
    )


def run_protocol(
    tasks: Sequence[str] = ("T1",),
    arms: Sequence[str] = ARMS,
    replicates: int = 10,
    population_size: int = 40,
    generations: int = 25,
    spec: Optional[design_module.BracketSpec] = None,
    prior_kwargs: Optional[Mapping[str, Mapping[str, Any]]] = None,
) -> List[CellResult]:
    """Run the full factorial design of Fig. 6a."""
    prior_kwargs = prior_kwargs or {}
    results: List[CellResult] = []
    for task in tasks:
        for arm in arms:
            for replicate in range(int(replicates)):
                results.append(
                    run_cell(
                        task=task,
                        arm=arm,
                        replicate=replicate,
                        population_size=population_size,
                        generations=generations,
                        spec=spec,
                        prior_kwargs=prior_kwargs.get(arm),
                    )
                )
    return results


def aggregate(results: Sequence[CellResult]) -> Dict[Tuple[str, str], Dict[str, Tuple[float, float]]]:
    """Mean and standard deviation per (task, arm) for every metric (Table 7)."""
    out: Dict[Tuple[str, str], Dict[str, Tuple[float, float]]] = {}
    for task in sorted({r.task for r in results}):
        for arm in sorted({r.arm for r in results}):
            cells = [r for r in results if r.task == task and r.arm == arm]
            if not cells:
                continue
            summary = {}
            for metric in METRICS:
                values = np.asarray([getattr(c, metric) for c in cells], dtype=float)
                summary[metric] = (float(values.mean()), float(values.std(ddof=1)) if values.size > 1 else 0.0)
            out[(task, arm)] = summary
    return out


# --------------------------------------------------------------- statistics
def _signed_rank_statistic(differences: np.ndarray) -> Tuple[float, int, np.ndarray]:
    """Signed-rank statistic W+ over the non-zero differences, with mid-ranks."""
    nonzero = differences[differences != 0]
    n = nonzero.size
    if n == 0:
        return 0.0, 0, nonzero
    order = np.argsort(np.abs(nonzero), kind="stable")
    magnitudes = np.abs(nonzero)[order]
    ranks = np.empty(n, dtype=float)
    i = 0
    while i < n:
        j = i
        while j + 1 < n and magnitudes[j + 1] == magnitudes[i]:
            j += 1
        ranks[i:j + 1] = 0.5 * ((i + 1) + (j + 1))  # mid-rank for ties
        i = j + 1
    signs = np.sign(nonzero)[order]
    w_plus = float(np.sum(ranks[signs > 0]))
    return w_plus, n, nonzero


def _exact_signed_rank_pvalue(w_plus: float, n: int) -> float:
    """Two-sided exact p-value of the signed-rank distribution (no ties)."""
    counts = np.zeros(n * (n + 1) // 2 + 1)
    counts[0] = 1.0
    for rank in range(1, n + 1):
        shifted = np.zeros_like(counts)
        shifted[rank:] = counts[:-rank]
        counts = counts + shifted
    total = counts.sum()
    mean = n * (n + 1) / 4.0
    deviation = abs(w_plus - mean)
    lower = np.sum(counts[: int(np.floor(mean - deviation)) + 1])
    upper = np.sum(counts[int(np.ceil(mean + deviation)):])
    return float(min(1.0, (lower + upper) / total))


def wilcoxon_signed_rank(x: Sequence[float], y: Sequence[float]) -> Tuple[float, float]:
    """Two-sided Wilcoxon signed-rank test on paired samples (Section 7.6).

    Zero differences are dropped (Wilcoxon's original treatment).  With no ties
    among the non-zero differences and ``n <= 25`` the exact distribution is
    used; otherwise a tie-corrected normal approximation with continuity
    correction is applied.  Returns ``(W+, p)``; ``p = 1.0`` when every paired
    difference is zero, which is the honest answer for identical arms.
    """
    x = np.asarray(x, dtype=float)
    y = np.asarray(y, dtype=float)
    if x.shape != y.shape:
        raise ValueError("paired samples must have the same shape")
    differences = x - y
    w_plus, n, nonzero = _signed_rank_statistic(differences)
    if n == 0:
        return 0.0, 1.0

    magnitudes = np.abs(nonzero)
    _, tie_counts = np.unique(magnitudes, return_counts=True)
    has_ties = bool(np.any(tie_counts > 1))

    if n <= 25 and not has_ties:
        return w_plus, _exact_signed_rank_pvalue(w_plus, n)

    mean = n * (n + 1) / 4.0
    tie_term = float(np.sum(tie_counts ** 3 - tie_counts))
    variance = n * (n + 1) * (2 * n + 1) / 24.0 - tie_term / 48.0
    if variance <= 0:
        return w_plus, 1.0
    z = (abs(w_plus - mean) - 0.5) / math.sqrt(variance)
    p = 2.0 * (1.0 - _standard_normal_cdf(abs(z)))
    return w_plus, float(min(1.0, max(0.0, p)))


def _standard_normal_cdf(z: float) -> float:
    return 0.5 * (1.0 + math.erf(z / math.sqrt(2.0)))


def _standard_normal_quantile(p: float) -> float:
    """Inverse standard normal CDF (Acklam's rational approximation)."""
    if not 0.0 < p < 1.0:
        raise ValueError("p must lie strictly between 0 and 1")
    a = [-3.969683028665376e01, 2.209460984245205e02, -2.759285104469687e02,
         1.383577518672690e02, -3.066479806614716e01, 2.506628277459239e00]
    b = [-5.447609879822406e01, 1.615858368580409e02, -1.556989798598866e02,
         6.680131188771972e01, -1.328068155288572e01]
    c = [-7.784894002430293e-03, -3.223964580411365e-01, -2.400758277161838e00,
         -2.549732539343734e00, 4.374664141464968e00, 2.938163982698783e00]
    d = [7.784695709041462e-03, 3.224671290700398e-01, 2.445134137142996e00,
         3.754408661907416e00]
    p_low, p_high = 0.02425, 1 - 0.02425
    if p < p_low:
        q = math.sqrt(-2 * math.log(p))
        return (((((c[0] * q + c[1]) * q + c[2]) * q + c[3]) * q + c[4]) * q + c[5]) / \
               ((((d[0] * q + d[1]) * q + d[2]) * q + d[3]) * q + 1)
    if p > p_high:
        q = math.sqrt(-2 * math.log(1 - p))
        return -(((((c[0] * q + c[1]) * q + c[2]) * q + c[3]) * q + c[4]) * q + c[5]) / \
               ((((d[0] * q + d[1]) * q + d[2]) * q + d[3]) * q + 1)
    q = p - 0.5
    r = q * q
    return (((((a[0] * r + a[1]) * r + a[2]) * r + a[3]) * r + a[4]) * r + a[5]) * q / \
           (((((b[0] * r + b[1]) * r + b[2]) * r + b[3]) * r + b[4]) * r + 1)


def holm_correction(p_values: Sequence[float]) -> List[float]:
    """Holm step-down correction at family-wise level (Section 7.6).

    Returns adjusted p-values in the input order; they are monotone in the
    sorted order and capped at 1.  No result is described as significant
    without its Holm-adjusted p-value and its effect size.
    """
    p = np.asarray(p_values, dtype=float)
    m = p.size
    if m == 0:
        return []
    order = np.argsort(p, kind="stable")
    adjusted = np.empty(m, dtype=float)
    running = 0.0
    for rank, index in enumerate(order):
        value = (m - rank) * p[index]
        running = max(running, value)
        adjusted[index] = min(1.0, running)
    return [float(value) for value in adjusted]


def cliffs_delta(x: Sequence[float], y: Sequence[float]) -> float:
    r"""Cliff's delta: :math:`P(x>y) - P(x<y)` over all pairs.

    Positive delta means the first sample tends to be larger.
    """
    x = np.asarray(x, dtype=float).reshape(-1, 1)
    y = np.asarray(y, dtype=float).reshape(1, -1)
    greater = int(np.sum(x > y))
    less = int(np.sum(x < y))
    total = x.size * y.size
    if total == 0:
        return 0.0
    return float((greater - less) / total)


def cliffs_delta_magnitude(delta: float) -> str:
    """Conventional interpretation used in Section 7.6."""
    magnitude = abs(delta)
    if magnitude < 0.147:
        return "negligible"
    if magnitude < 0.33:
        return "small"
    if magnitude < 0.474:
        return "medium"
    return "large"


def bootstrap_ci(
    values: Sequence[float],
    statistic: Callable[[np.ndarray], float] = np.median,
    confidence: float = 0.95,
    n_resamples: int = 2000,
    seed: int = 0,
) -> Tuple[float, float, float]:
    """Percentile bootstrap CI of a statistic (default: the median difference).

    Returns ``(estimate, lower, upper)`` with ``B = 2000`` resamples by default,
    as pre-registered in Section 7.6.
    """
    values = np.asarray(values, dtype=float)
    if values.size == 0:
        return float("nan"), float("nan"), float("nan")
    rng = np.random.default_rng(seed)
    estimates = np.empty(int(n_resamples))
    for b in range(int(n_resamples)):
        sample = values[rng.integers(0, values.size, values.size)]
        estimates[b] = float(statistic(sample))
    alpha = (1.0 - confidence) / 2.0
    lower, upper = np.quantile(estimates, [alpha, 1.0 - alpha])
    return float(statistic(values)), float(lower), float(upper)


def required_replicates(d: float, alpha: float = 0.05, power: float = 0.80) -> int:
    r"""Eq. (24): :math:`n \approx \frac{\pi}{3}\left(\frac{z_{1-\alpha/2}+z_{1-\beta}}{d}\right)^2`.

    The ``pi/3`` factor is the inverse of the asymptotic relative efficiency of
    the Wilcoxon signed-rank test to the paired t-test.  For ``d = 1.0`` at
    ``alpha = 0.05`` two-sided and power 0.80 this gives 9 pairs, and for
    ``d = 0.8`` it gives 13 — ten replicates therefore detect large effects
    only, which Section 8.3 records as a limitation.
    """
    if d <= 0:
        raise ValueError("the standardized effect size d must be positive")
    z_alpha = _standard_normal_quantile(1.0 - alpha / 2.0)
    z_beta = _standard_normal_quantile(power)
    return int(math.ceil((math.pi / 3.0) * ((z_alpha + z_beta) / d) ** 2))


def compare_arms(
    results: Sequence[CellResult],
    task: str = "T1",
    contrasts: Sequence[Tuple[str, str]] = (("C", "B"), ("C", "A")),
    metrics: Sequence[str] = tuple(METRICS),
    seed: int = 0,
) -> List[Dict[str, Any]]:
    """The statistical plan of Section 7.6 applied to one task.

    Cells are paired by replicate seed.  All ``len(contrasts) x len(metrics)``
    p-values of a task form one Holm family, as pre-registered.  The tests are
    two-sided even though the predictions are directional, so that evidence
    against the framework is reported with the same weight.
    """
    rows: List[Dict[str, Any]] = []
    for arm_a, arm_b in contrasts:
        for metric in metrics:
            a_cells = sorted(
                (r for r in results if r.task == task and r.arm == arm_a),
                key=lambda r: r.replicate,
            )
            b_cells = sorted(
                (r for r in results if r.task == task and r.arm == arm_b),
                key=lambda r: r.replicate,
            )
            if len(a_cells) != len(b_cells) or not a_cells:
                raise ValueError(f"unpaired cells for contrast {arm_a} vs {arm_b} on {task}")
            if [c.replicate for c in a_cells] != [c.replicate for c in b_cells]:
                raise ValueError("cells must be paired by replicate")
            x = np.asarray([getattr(c, metric) for c in a_cells], dtype=float)
            y = np.asarray([getattr(c, metric) for c in b_cells], dtype=float)
            statistic, p = wilcoxon_signed_rank(x, y)
            delta = cliffs_delta(x, y)
            median, lower, upper = bootstrap_ci(x - y, seed=seed)
            rows.append(
                {
                    "task": task,
                    "contrast": f"{arm_a} vs {arm_b}",
                    "metric": metric,
                    "higher_is_better": METRICS.get(metric, True),
                    "n_pairs": int(x.size),
                    "W": float(statistic),
                    "p_raw": float(p),
                    "cliffs_delta": float(delta),
                    "effect_magnitude": cliffs_delta_magnitude(delta),
                    "median_difference": float(median),
                    "ci_low": float(lower),
                    "ci_high": float(upper),
                }
            )
    for row, adjusted in zip(rows, holm_correction([r["p_raw"] for r in rows])):
        row["p_holm"] = adjusted
        row["significant_at_0.05"] = bool(adjusted <= 0.05)
    return rows


def dry_run(
    replicates: int = 10,
    population_size: int = 40,
    generations: int = 25,
    seed: int = 0,
) -> Dict[str, Any]:
    """Section 7.7: execute the protocol end to end on synthetic arms.

    In this dry run all three arms are synthetic: arm A is a template-ratio
    sampler standing in for human designers, and the analog-shaped prior of
    arm C is a hand-set distribution, not a prior derived from a curated EE-KG.
    The numbers therefore test the pipeline, not the hypothesis, and no
    inference about H1-H3 may be drawn from them.  Everything is tagged
    SYNTHETIC for that reason.
    """
    results = run_protocol(
        tasks=("T1",),
        arms=ARMS,
        replicates=replicates,
        population_size=population_size,
        generations=generations,
    )
    summary = aggregate(results)
    comparisons = compare_arms(results, task="T1", seed=seed)
    snapshot = CorpusSnapshot(
        name="dry-run (no biological records)",
        payload={
            "mode": "SYNTHETIC",
            "package_version": PACKAGE_VERSION,
            "replicates": replicates,
            "population_size": population_size,
            "generations": generations,
            "arms": {a: ARM_CONFIGS[a].as_dict() for a in ARMS},
            "specification": design_module.EOAT_BRACKET.as_dict(),
        },
    )
    return {
        "tag": ProvenanceTag.SYNTHETIC.value,
        "warning": (
            "pipeline validation only: all three arms are synthetic and no inference "
            "about H1-H3 may be drawn from these numbers"
        ),
        "snapshot_hash": snapshot.hash,
        "cells": [r.as_dict() for r in results],
        "summary": {
            f"{task}/{arm}": {m: {"mean": v[0], "sd": v[1]} for m, v in metrics.items()}
            for (task, arm), metrics in summary.items()
        },
        "comparisons": comparisons,
        "power": {
            "n_for_d_1.0": required_replicates(1.0),
            "n_for_d_0.8": required_replicates(0.8),
            "note": "ten replicates detect large effects only (Section 8.3)",
        },
    }


def ablation(
    replicates: int = 10,
    population_size: int = 40,
    generations: int = 25,
) -> Dict[str, Any]:
    """Section 7.5: re-run arm C with one claimed source of value removed.

    (a) ``convergentWith`` edges removed, so ``N_conv = 1`` and the convergence
    bonus of Eqs. (8) and (13) collapses; (b) reconstructed states removed;
    (c) trade-off constraints removed; (d) the evidence gate disabled.  Each
    variant isolates one mechanism.  Variants (a), (b) and (d) act on the
    gate and the score rather than on the search, so their effect appears in
    the decision, not in the metrics — which is itself the point: the gate
    changes what is recommended, not what is found.
    """
    baseline = [
        run_cell("T1", "C", r, population_size, generations) for r in range(replicates)
    ]
    # (c) the prior is the only channel through which the graph reaches the search,
    #     so removing the trade-off-shaped part of the prior is the search-side ablation.
    widened = [
        run_cell(
            "T1", "C", r, population_size, generations,
            prior_kwargs={"spread": (0.40, 0.30, 0.30, 0.24)},
        )
        for r in range(replicates)
    ]
    return {
        "tag": ProvenanceTag.SYNTHETIC.value,
        "baseline": [c.as_dict() for c in baseline],
        "no_tradeoff_constraints": [c.as_dict() for c in widened],
        "gate_side_ablations": {
            "no_convergence_edges": "N^w_conv = 1 in Eqs. (8) and (13); see evoproto.gate",
            "no_reconstructed_states": "chains with r = 1 dropped; see EvoKG.without_reconstructions",
            "gate_disabled": "decide() bypassed; every verified candidate is recommended",
        },
        "note": (
            "ablations (a), (b) and (d) change the decision rather than the search "
            "metrics; they are evaluated on the gate, not on the Pareto front"
        ),
    }
