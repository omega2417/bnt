"""Outcome measures and uncertainty (Section 3.8, Equation 5).

    Coverage(t) = [ sum_{c in S(t)} r(c, t) e(c) ] / [ sum_{c in C} r(c, t) ]   (5)

Coverage is a *modelled index* of capability demand met under encoded
assumptions.  It is not a probability of avoiding an incident and not a measure
of implementation depth or evidence truthfulness.

Results are aggregated within each complete trace first; the trace, not the
enterprise-day, is the independent statistical unit.
"""

from __future__ import annotations

from dataclasses import dataclass
from math import sqrt
from statistics import fmean, stdev
from typing import Dict, List, Mapping, Sequence, Tuple

from .capabilities import BY_CODE, cost_of
from .scenarios import BY_KEY
from .simulator import IRRELEVANCE_THRESHOLD, TraceResult

#: Normal-approximation multiplier for a 95% interval (Section 3.8).
Z95 = 1.96


def coverage(profile: Sequence[str], demand: Mapping[str, float]) -> float:
    """Equation (5) for one enterprise-day."""
    total = sum(demand.values())
    if total <= 0.0:
        return 1.0
    covered = sum(demand.get(code, 0.0) * BY_CODE[code].effectiveness for code in profile)
    return covered / total


def daily_coverage(trace: TraceResult, condition: str) -> List[float]:
    history = trace.conditions[condition].profiles
    return [
        coverage(history[day], trace.true_demand[day])
        for day in range(len(trace.true_demand))
    ]


def percentile(values: Sequence[float], q: float) -> float:
    """Linear-interpolation percentile (``q`` in [0, 100])."""
    if not values:
        raise ValueError("percentile of an empty sequence")
    ordered = sorted(values)
    if len(ordered) == 1:
        return ordered[0]
    position = (q / 100.0) * (len(ordered) - 1)
    lower = int(position)
    upper = min(lower + 1, len(ordered) - 1)
    frac = position - lower
    return ordered[lower] * (1.0 - frac) + ordered[upper] * frac


def adaptation_delay(trace: TraceResult, condition: str) -> float:
    """Mean days from a labelled event to inclusion of its target capabilities.

    One observation per event-capability pair.  A capability already selected
    when the event occurs contributes a delay of zero; a capability the profile
    never selects is censored at the remaining horizon.
    """
    archetype = BY_KEY[trace.archetype]
    history = trace.conditions[condition].profiles
    horizon = len(history)
    delays: List[float] = []
    for event in archetype.events:
        for code in event.targets():
            delay = None
            for day in range(event.day, horizon):
                if code in history[day]:
                    delay = day - event.day
                    break
            delays.append(float(horizon - event.day) if delay is None else float(delay))
    return fmean(delays) if delays else 0.0


def irrelevant_resource_units(trace: TraceResult, condition: str) -> float:
    """Mean daily resource units spent on capabilities of negligible relevance."""
    history = trace.conditions[condition].profiles
    per_day = []
    for day, demand in enumerate(trace.true_demand):
        wasted = [
            code
            for code in history[day]
            if demand.get(code, 0.0) < IRRELEVANCE_THRESHOLD
        ]
        per_day.append(float(cost_of(wasted)))
    return fmean(per_day)


@dataclass(frozen=True)
class TraceOutcome:
    """Per-trace aggregate of every reported outcome."""

    archetype: str
    replicate: int
    condition: str
    mean_coverage: float
    p10_coverage: float
    adaptation_delay: float
    review_hours: float
    false_alerts: float
    irrelevant_units: float
    reassessments: int

    def as_row(self) -> Dict[str, object]:
        return {
            "archetype": self.archetype,
            "replicate": self.replicate,
            "condition": self.condition,
            "mean_coverage_pct": round(100.0 * self.mean_coverage, 6),
            "p10_coverage_pct": round(100.0 * self.p10_coverage, 6),
            "adaptation_delay_days": round(self.adaptation_delay, 6),
            "review_hours": round(self.review_hours, 6),
            "false_alerts": self.false_alerts,
            "irrelevant_units": round(self.irrelevant_units, 6),
            "reassessments": self.reassessments,
        }


def summarise_trace(trace: TraceResult, condition: str) -> TraceOutcome:
    series = daily_coverage(trace, condition)
    ct = trace.conditions[condition]
    return TraceOutcome(
        archetype=trace.archetype,
        replicate=trace.replicate,
        condition=condition,
        mean_coverage=fmean(series),
        p10_coverage=percentile(series, 10.0),
        adaptation_delay=adaptation_delay(trace, condition),
        review_hours=ct.review_hours,
        false_alerts=float(ct.false_alerts),
        irrelevant_units=irrelevant_resource_units(trace, condition),
        reassessments=len(ct.reassessment_days),
    )


@dataclass(frozen=True)
class Interval:
    """Mean with a normal-approximation 95% confidence interval."""

    mean: float
    low: float
    high: float
    n: int

    def __str__(self) -> str:
        return f"{self.mean:.2f} [{self.low:.2f}, {self.high:.2f}]"

    def as_tuple(self) -> Tuple[float, float, float]:
        return (self.mean, self.low, self.high)


def mean_ci(values: Sequence[float]) -> Interval:
    """Mean and normal-approximation 95% CI over whole traces."""
    n = len(values)
    if n == 0:
        raise ValueError("no traces to aggregate")
    mean = fmean(values)
    if n < 2:
        return Interval(mean, mean, mean, n)
    sd = stdev(values)
    half = Z95 * sd / sqrt(n)
    return Interval(mean, mean - half, mean + half, n)


def paired_difference(
    left: Sequence[TraceOutcome],
    right: Sequence[TraceOutcome],
    attribute: str = "mean_coverage",
    scale: float = 100.0,
) -> Tuple[Interval, int, int]:
    """Paired comparison over matched scenario-replicate traces.

    Returns the interval of the mean difference (``left`` minus ``right``), the
    number of pairs in which the difference is positive, and the pair count.
    """
    index = {(o.archetype, o.replicate): o for o in right}
    diffs: List[float] = []
    for outcome in left:
        partner = index.get((outcome.archetype, outcome.replicate))
        if partner is None:
            raise ValueError(f"unmatched trace {outcome.archetype}/{outcome.replicate}")
        diffs.append(
            scale * (getattr(outcome, attribute) - getattr(partner, attribute))
        )
    positive = sum(1 for d in diffs if d > 0)
    return mean_ci(diffs), positive, len(diffs)
