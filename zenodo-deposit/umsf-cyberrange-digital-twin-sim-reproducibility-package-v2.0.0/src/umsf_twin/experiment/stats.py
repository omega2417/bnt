"""Statistics used by section 14, implemented without third-party packages.

Bootstrap confidence intervals, Wilson intervals for proportions, a cluster
bootstrap that respects the run as the unit of analysis, McNemar's test for
paired detector comparison and a simple power calculation.
"""

from __future__ import annotations

import math
import random
from statistics import fmean, pstdev
from typing import Any, Callable, Sequence

__all__ = ["mean_ci", "bootstrap_ci", "cluster_bootstrap_ci", "wilson_interval",
           "mcnemar", "required_replicates", "percentile"]


def percentile(values: Sequence[float], q: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    if len(ordered) == 1:
        return float(ordered[0])
    position = (len(ordered) - 1) * max(0.0, min(1.0, q))
    low = math.floor(position)
    high = math.ceil(position)
    if low == high:
        return float(ordered[int(position)])
    return float(ordered[low] + (ordered[high] - ordered[low]) * (position - low))


def mean_ci(values: Sequence[float], confidence: float = 0.95) -> dict[str, float | None]:
    """Normal-approximation interval; use the bootstrap for skewed metrics."""

    if not values:
        return {"mean": None, "low": None, "high": None, "n": 0}
    n = len(values)
    mean = fmean(values)
    if n == 1:
        return {"mean": mean, "low": mean, "high": mean, "n": 1}
    z = 1.959963985 if abs(confidence - 0.95) < 1e-9 else 2.575829304
    half = z * pstdev(values) / math.sqrt(n)
    return {"mean": mean, "low": mean - half, "high": mean + half, "n": n}


def bootstrap_ci(values: Sequence[float], statistic: Callable[[Sequence[float]], float] = fmean,
                 draws: int = 2000, confidence: float = 0.95,
                 seed: int = 12345) -> dict[str, float | None]:
    if not values:
        return {"estimate": None, "low": None, "high": None, "draws": 0}
    rng = random.Random(seed)
    n = len(values)
    samples = []
    for _ in range(draws):
        resample = [values[rng.randrange(n)] for _ in range(n)]
        samples.append(statistic(resample))
    alpha = (1.0 - confidence) / 2.0
    return {"estimate": statistic(values), "low": percentile(samples, alpha),
            "high": percentile(samples, 1.0 - alpha), "draws": draws}


def cluster_bootstrap_ci(clusters: Sequence[Sequence[float]], draws: int = 2000,
                         confidence: float = 0.95, seed: int = 12345) -> dict[str, Any]:
    """Resample whole runs, not individual steps (section 14.1)."""

    clusters = [list(cluster) for cluster in clusters if cluster]
    if not clusters:
        return {"estimate": None, "low": None, "high": None, "clusters": 0}
    rng = random.Random(seed)
    observed = fmean([fmean(cluster) for cluster in clusters])
    samples = []
    for _ in range(draws):
        picked = [clusters[rng.randrange(len(clusters))] for _ in range(len(clusters))]
        samples.append(fmean([fmean(cluster) for cluster in picked]))
    alpha = (1.0 - confidence) / 2.0
    return {"estimate": observed, "low": percentile(samples, alpha),
            "high": percentile(samples, 1.0 - alpha), "clusters": len(clusters)}


def wilson_interval(successes: int, total: int, confidence: float = 0.95) -> dict[str, float]:
    if total <= 0:
        return {"p": 0.0, "low": 0.0, "high": 0.0, "n": 0}
    z = 1.959963985 if abs(confidence - 0.95) < 1e-9 else 2.575829304
    p = successes / total
    denominator = 1.0 + z * z / total
    centre = (p + z * z / (2 * total)) / denominator
    half = z * math.sqrt(p * (1 - p) / total + z * z / (4 * total * total)) / denominator
    return {"p": p, "low": max(0.0, centre - half), "high": min(1.0, centre + half),
            "n": total}


def mcnemar(b: int, c: int) -> dict[str, float]:
    """Paired comparison of two detectors on the same windows.

    ``b`` = detector A right and B wrong, ``c`` = A wrong and B right.
    Uses the continuity-corrected chi-square with one degree of freedom.
    """

    if b + c == 0:
        return {"statistic": 0.0, "p_value": 1.0, "b": b, "c": c}
    statistic = (abs(b - c) - 1.0) ** 2 / (b + c)
    p_value = math.erfc(math.sqrt(max(0.0, statistic) / 2.0))
    return {"statistic": statistic, "p_value": p_value, "b": b, "c": c}


def required_replicates(sd: float, half_width: float, confidence: float = 0.95) -> int:
    """Replicates needed for a target half-width of the mean interval."""

    if half_width <= 0:
        raise ValueError("half_width must be positive")
    z = 1.959963985 if abs(confidence - 0.95) < 1e-9 else 2.575829304
    return max(1, math.ceil((z * sd / half_width) ** 2))
