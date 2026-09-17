"""Sections 7.4 and 7.5: outcome definitions and the statistical plan.

The independent statistical unit is an *environmental seed-condition run*.
Agents and successive epochs within a run are dependent observations, not
independent replicates, so :func:`paired_bootstrap` resamples whole
trajectories.  Methods are paired on identical environmental seeds.

Two habits from Section 7.4 are enforced by the data structures rather than by
convention: a run that never reaches the tolerance is *censored*, not recorded
as zero convergence time; and a budget-limited exit is stored separately from a
certified stop.
"""

from __future__ import annotations

import math
import random
from dataclasses import dataclass
from typing import Callable, Dict, List, Optional, Sequence, Tuple

from .protocol import RunResult

__all__ = [
    "Endpoints",
    "endpoints",
    "time_to_threshold",
    "recovery_epoch",
    "paired_bootstrap",
    "holm_adjust",
    "summarise",
]


@dataclass
class Endpoints:
    """The prespecified endpoints of Section 7.4 for one run."""

    method: str
    seed: int
    condition: str
    terminal_nash_gap: float
    mean_nash_gap: float
    evaluations_to_threshold: Optional[int]   # None == censored, never reached
    reached_threshold: bool
    cumulative_realised_value: float
    cumulative_welfare: float
    total_energy: float
    inference_energy: float
    latency_median: float
    latency_p95: float
    payoff_evaluations: int
    bytes_moved: float
    certified_fraction: float
    budget_limited_fraction: float
    uses_true_payoffs: bool

    def as_dict(self) -> Dict[str, object]:
        return dict(self.__dict__)


def _percentile(values: Sequence[float], q: float) -> float:
    if not values:
        return float("nan")
    ordered = sorted(values)
    if len(ordered) == 1:
        return ordered[0]
    pos = q * (len(ordered) - 1)
    low = math.floor(pos)
    high = math.ceil(pos)
    if low == high:
        return ordered[int(pos)]
    return ordered[low] + (ordered[high] - ordered[low]) * (pos - low)


def time_to_threshold(
    run: RunResult, tolerance: float
) -> Tuple[Optional[int], bool]:
    """Payoff evaluations needed to reach a predeclared Nash-gap tolerance.

    Returns ``(evaluations, reached)``.  Failure to reach the tolerance before
    the cap is a *censored* observation -- ``(None, False)`` -- and must not be
    analysed as zero convergence time.
    """
    cumulative = 0
    for record in run.records:
        cumulative += record.evaluations
        if record.true_nash_gap <= tolerance:
            return cumulative, True
    return None, False


def recovery_epoch(
    run: RunResult,
    change_epoch: int,
    reference: float,
    tolerance: float,
    window: int = 5,
) -> Optional[int]:
    """First epoch after ``change_epoch`` at which a rolling outcome returns to
    within ``tolerance`` of ``reference`` and *stays there* for ``window`` epochs.

    The reference must be declared before evaluation; it must not be chosen
    retrospectively because it happens to flatter a method.
    """
    series = run.series("realised_value")
    for start in range(change_epoch, len(series) - window + 1):
        if all(abs(series[k] - reference) <= tolerance for k in range(start, start + window)):
            return start
    return None


def endpoints(run: RunResult, gap_tolerance: float = 0.05) -> Endpoints:
    """Extract every Section 7.4 endpoint from one run."""
    gaps = run.series("true_nash_gap")
    latencies = run.series("latency_max")
    evals, reached = time_to_threshold(run, gap_tolerance)
    n = max(1, run.epochs)
    return Endpoints(
        method=run.method,
        seed=run.seed,
        condition=run.condition,
        terminal_nash_gap=gaps[-1] if gaps else float("nan"),
        mean_nash_gap=sum(gaps) / len(gaps) if gaps else float("nan"),
        evaluations_to_threshold=evals,
        reached_threshold=reached,
        cumulative_realised_value=run.total("realised_value"),
        cumulative_welfare=run.total("welfare"),
        total_energy=run.total("energy"),
        inference_energy=run.total("inference_energy"),
        latency_median=_percentile(latencies, 0.5),
        latency_p95=_percentile(latencies, 0.95),
        payoff_evaluations=int(run.total("evaluations")),
        bytes_moved=run.total("bytes_moved"),
        certified_fraction=run.certified_fraction(),
        budget_limited_fraction=sum(
            1 for r in run.records if r.terminated == "budget"
        ) / n,
        uses_true_payoffs=run.uses_true_payoffs,
    )


@dataclass
class BootstrapResult:
    """Paired bootstrap over complete runs (Section 7.5)."""

    n_pairs: int
    mean_difference: float
    median_difference: float
    ci_low: float
    ci_high: float
    resamples: int
    censored_pairs: int = 0

    @property
    def excludes_zero(self) -> bool:
        return self.ci_low > 0.0 or self.ci_high < 0.0


def paired_bootstrap(
    a: Sequence[float],
    b: Sequence[float],
    resamples: int = 10_000,
    alpha: float = 0.05,
    rng: Optional[random.Random] = None,
    censored: Optional[Sequence[bool]] = None,
) -> BootstrapResult:
    """Paired bootstrap of ``a - b`` over whole runs, with a ``1 - alpha`` interval.

    ``a`` and ``b`` must be aligned on identical environmental seeds.  Pairs
    flagged in ``censored`` are dropped from the interval and counted
    separately, because substituting a favourable value for a censored run is
    exactly the analysis Section 7.4 forbids.

    The default of 10,000 resamples and a 95% interval follows the proposed
    primary analysis.  This reports a difference and its uncertainty; it is not
    a claim of adequate statistical power, which has to be reassessed from an
    independent pilot.
    """
    if len(a) != len(b):
        raise ValueError("paired bootstrap requires aligned samples")
    rng = rng or random.Random(0)
    keep = [
        (x, y)
        for k, (x, y) in enumerate(zip(a, b))
        if not (censored and censored[k])
    ]
    dropped = len(a) - len(keep)
    if not keep:
        raise ValueError("every pair is censored; no interval can be formed")
    diffs = [x - y for x, y in keep]
    n = len(diffs)
    means = []
    for _ in range(resamples):
        total = 0.0
        for _ in range(n):
            total += diffs[rng.randrange(n)]
        means.append(total / n)
    means.sort()
    lo = means[int((alpha / 2) * resamples)]
    hi = means[min(resamples - 1, int((1 - alpha / 2) * resamples))]
    ordered = sorted(diffs)
    median = (
        ordered[n // 2]
        if n % 2
        else 0.5 * (ordered[n // 2 - 1] + ordered[n // 2])
    )
    return BootstrapResult(
        n_pairs=n,
        mean_difference=sum(diffs) / n,
        median_difference=median,
        ci_low=lo,
        ci_high=hi,
        resamples=resamples,
        censored_pairs=dropped,
    )


def holm_adjust(p_values: Sequence[float], labels: Optional[Sequence[str]] = None) -> List[dict]:
    """Holm's sequentially rejective procedure for the confirmatory family.

    Apply it to the *prespecified* primary outcomes only (H1, H2, H3).  Every
    additional comparison is exploratory and must be labelled as such.
    """
    m = len(p_values)
    labels = list(labels) if labels is not None else [f"H{i + 1}" for i in range(m)]
    order = sorted(range(m), key=lambda k: p_values[k])
    adjusted = [0.0] * m
    running = 0.0
    for rank, k in enumerate(order):
        value = min(1.0, (m - rank) * p_values[k])
        running = max(running, value)
        adjusted[k] = running
    return [
        {"label": labels[k], "p_raw": p_values[k], "p_holm": adjusted[k]}
        for k in range(m)
    ]


def summarise(runs: Sequence[RunResult], gap_tolerance: float = 0.05) -> List[Dict[str, object]]:
    """Endpoint table for a collection of runs, one row per run."""
    return [endpoints(r, gap_tolerance).as_dict() for r in runs]
