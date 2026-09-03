"""Sim-to-real calibration and fidelity metrics (section 13).

Calibration never touches the holdout: the objective is evaluated on the
calibration split only, and :func:`evaluate_transfer` reports zero-shot and
adapted transfer separately so an improvement on the tuning data cannot be
presented as field accuracy.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from statistics import fmean, pstdev
from typing import Any, Callable, Sequence

from .stats import percentile

__all__ = ["ks_statistic", "wasserstein1", "coverage", "FidelityReport",
           "fidelity", "nelder_mead", "abc_rejection", "CalibrationTarget",
           "evaluate_transfer", "DEFAULT_GATES_SIM2REAL"]


def ks_statistic(a: Sequence[float], b: Sequence[float]) -> float:
    """Two-sample Kolmogorov-Smirnov distance."""

    if not a or not b:
        return 1.0
    x, y = sorted(a), sorted(b)
    merged = sorted(set(x) | set(y))
    worst = 0.0
    for value in merged:
        fx = sum(1 for item in x if item <= value) / len(x)
        fy = sum(1 for item in y if item <= value) / len(y)
        worst = max(worst, abs(fx - fy))
    return worst


def wasserstein1(a: Sequence[float], b: Sequence[float], bins: int = 100) -> float:
    """First Wasserstein distance approximated on matched quantiles."""

    if not a or not b:
        return float("inf")
    quantiles = [(index + 0.5) / bins for index in range(bins)]
    return fmean([abs(percentile(a, q) - percentile(b, q)) for q in quantiles])


def coverage(observed: Sequence[float], low: Sequence[float],
             high: Sequence[float]) -> float:
    """Share of real observations inside the simulated predictive band."""

    if not observed:
        return 0.0
    inside = sum(1 for value, lo, hi in zip(observed, low, high) if lo <= value <= hi)
    return inside / len(observed)


@dataclass
class FidelityReport:
    metric: str
    ks: float
    wasserstein: float
    mean_error: float
    relative_error: float
    passed: bool
    thresholds: dict[str, float] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {"metric": self.metric, "ks": round(self.ks, 5),
                "wasserstein": round(self.wasserstein, 5),
                "mean_error": round(self.mean_error, 5),
                "relative_error": round(self.relative_error, 5),
                "passed": self.passed, "thresholds": self.thresholds}


#: Initial sim-to-real gates. They are targets to be justified per metric, not
#: universal constants.
DEFAULT_GATES_SIM2REAL = {"ks_max": 0.20, "relative_error_max": 0.25}


def fidelity(metric: str, simulated: Sequence[float], measured: Sequence[float],
             gates: dict[str, float] | None = None) -> FidelityReport:
    gates = gates or DEFAULT_GATES_SIM2REAL
    ks = ks_statistic(simulated, measured)
    w1 = wasserstein1(simulated, measured)
    mean_error = (fmean(simulated) - fmean(measured)) if simulated and measured else float("nan")
    denominator = abs(fmean(measured)) if measured and fmean(measured) else 1.0
    relative = abs(mean_error) / denominator
    passed = ks <= gates["ks_max"] and relative <= gates["relative_error_max"]
    return FidelityReport(metric, ks, w1, mean_error, relative, passed, dict(gates))


def nelder_mead(objective: Callable[[list[float]], float], start: Sequence[float],
                step: float = 0.1, iterations: int = 200, tolerance: float = 1e-6
                ) -> dict[str, Any]:
    """Derivative-free optimiser used for small calibration problems."""

    n = len(start)
    simplex = [list(start)]
    for index in range(n):
        point = list(start)
        point[index] += step if point[index] == 0 else step * abs(point[index])
        simplex.append(point)
    scores = [objective(point) for point in simplex]
    evaluations = len(scores)

    for _ in range(iterations):
        order = sorted(range(len(simplex)), key=lambda i: scores[i])
        simplex = [simplex[i] for i in order]
        scores = [scores[i] for i in order]
        if abs(scores[-1] - scores[0]) < tolerance:
            break
        centroid = [fmean([point[dim] for point in simplex[:-1]]) for dim in range(n)]
        reflected = [centroid[dim] + (centroid[dim] - simplex[-1][dim]) for dim in range(n)]
        reflected_score = objective(reflected)
        evaluations += 1
        if reflected_score < scores[0]:
            expanded = [centroid[dim] + 2.0 * (centroid[dim] - simplex[-1][dim])
                        for dim in range(n)]
            expanded_score = objective(expanded)
            evaluations += 1
            simplex[-1], scores[-1] = ((expanded, expanded_score)
                                       if expanded_score < reflected_score
                                       else (reflected, reflected_score))
        elif reflected_score < scores[-2]:
            simplex[-1], scores[-1] = reflected, reflected_score
        else:
            contracted = [centroid[dim] + 0.5 * (simplex[-1][dim] - centroid[dim])
                          for dim in range(n)]
            contracted_score = objective(contracted)
            evaluations += 1
            if contracted_score < scores[-1]:
                simplex[-1], scores[-1] = contracted, contracted_score
            else:
                for index in range(1, len(simplex)):
                    simplex[index] = [simplex[0][dim] + 0.5 * (simplex[index][dim]
                                                               - simplex[0][dim])
                                      for dim in range(n)]
                    scores[index] = objective(simplex[index])
                    evaluations += 1
    best = min(range(len(simplex)), key=lambda i: scores[i])
    return {"x": simplex[best], "score": scores[best], "evaluations": evaluations}


def abc_rejection(simulate: Callable[[dict[str, float]], dict[str, Sequence[float]]],
                  observed: dict[str, Sequence[float]], priors: dict[str, tuple[float, float]],
                  draws: int = 200, quantile: float = 0.1, seed: int = 7
                  ) -> dict[str, Any]:
    """Approximate Bayesian Computation with a rejection threshold.

    Returns the accepted parameter sets, which are the posterior sample used
    for the nested uncertainty of section 12.5.
    """

    import random as _random

    rng = _random.Random(seed)
    samples = []
    for _ in range(draws):
        theta = {name: rng.uniform(low, high) for name, (low, high) in priors.items()}
        simulated = simulate(theta)
        distance = fmean([ks_statistic(simulated.get(key, []), values)
                          for key, values in observed.items()])
        samples.append((distance, theta))
    samples.sort(key=lambda item: item[0])
    keep = max(1, int(len(samples) * quantile))
    accepted = [theta for _, theta in samples[:keep]]
    posterior = {name: {"mean": fmean([theta[name] for theta in accepted]),
                        "sd": (pstdev([theta[name] for theta in accepted])
                               if len(accepted) > 1 else 0.0)}
                 for name in priors}
    return {"accepted": accepted, "posterior": posterior,
            "threshold_distance": samples[keep - 1][0], "draws": draws}


@dataclass
class CalibrationTarget:
    """One measured series the twin must reproduce."""

    metric: str
    measured: Sequence[float]
    weight: float = 1.0
    split: str = "calibration"       # calibration | holdout


def evaluate_transfer(targets: Sequence[CalibrationTarget],
                      simulated: dict[str, Sequence[float]],
                      gates: dict[str, float] | None = None) -> dict[str, Any]:
    """Report fidelity separately on the calibration and holdout splits."""

    output: dict[str, Any] = {"calibration": [], "holdout": [], "objective": 0.0}
    for target in targets:
        report = fidelity(target.metric, simulated.get(target.metric, []),
                          target.measured, gates)
        output[target.split].append(report.to_dict())
        if target.split == "calibration":
            output["objective"] += target.weight * (report.ks + report.relative_error)
    output["holdout_passed"] = all(item["passed"] for item in output["holdout"]) \
        if output["holdout"] else None
    return output
