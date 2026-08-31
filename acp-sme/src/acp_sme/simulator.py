"""Seeded synthetic simulator for the three experimental conditions.

Section 3.7 of the article: the experiment is a *component-level surrogate*.
It exercises the exact selector and the profile-update timing under a disclosed
event-level detector proxy.  It does not instantiate raw MNMM records and does
not exercise the full critical-predicate / persistence / periodic branches of
Equation (2); :mod:`acp_sme.detector` implements those and is verified by the
unit tests instead.

Every stochastic quantity below comes from Table A3.  All draws use the Python
standard-library Mersenne Twister with the documented seed schedule, so a run
is bit-for-bit reproducible on any platform without third-party dependencies.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from math import exp
from random import Random
from typing import Dict, List, Mapping, Optional, Sequence, Tuple

from .capabilities import ATTENUATED_CODES, BY_CODE, CODES
from .scenarios import Archetype, ARCHETYPE_INDEX, DEMAND_CAP, HORIZON_DAYS
from .selector import DEFAULT_LAMBDA, Selection, assert_invariants, select

# --------------------------------------------------------------------------
# Table A3 parameters
# --------------------------------------------------------------------------

PRIMARY_SEED = 27012026
SEED_REPLICATE_STRIDE = 101
SEED_ARCHETYPE_STRIDE = 10007
#: Sensitivity runs add this offset to the replicate index (Table A3).
SENSITIVITY_REPLICATE_OFFSET = 1000

INITIAL_NOISE_SIGMA = 0.04
REASSESSMENT_NOISE_SIGMA = 0.045
ATTENUATION_PROBABILITY = 0.02
ATTENUATION_FACTOR = 0.35

EVENT_SCORE_NOISE_SIGMA = 0.055
PRIMARY_TAU = 0.28

#: P(delay = 0, 1, 2, 3 days) for an above-threshold event.
TRIGGERED_DELAY_DAYS = (0, 1, 2, 3)
TRIGGERED_DELAY_WEIGHTS = (0.12, 0.44, 0.36, 0.08)
#: Discrete-uniform revisit window for a sub-threshold event.
SUBTHRESHOLD_DELAY_RANGE = (5, 8)

FALSE_TRIGGER_BASE = 0.0008
FALSE_TRIGGER_SCALE = 0.012
FALSE_TRIGGER_DECAY = 5.2

MONTHLY_REVIEW_DAYS = (30, 60, 90)

STATIC_REVIEW_HOURS = 4.0
MONTHLY_REVIEW_HOURS_EACH = 3.6
MONTHLY_REVIEW_COUNT = 4  # days 0, 30, 60 and 90
ACP_INITIAL_HOURS = 1.0
ACP_HOURS_PER_TRIGGER = 0.30
ACP_HOURS_PER_MEMBERSHIP_CHANGE = 0.12

#: A selected capability whose true relevance is below this value counts as
#: irrelevant resource expenditure (Section 4.2).
IRRELEVANCE_THRESHOLD = 0.20

#: Independent sub-streams keep each stochastic component reproducible when
#: another component is switched off (documented in docs/PARAMETERS.md).
_STREAM_OFFSET = {
    "initial": 0,
    "events": 1_000_003,
    "false_triggers": 2_000_003,
    "monthly": 3_000_003,
    "acp": 4_000_003,
}


def false_trigger_probability(tau: float) -> float:
    """Daily nuisance-trigger probability of Table A3."""
    return FALSE_TRIGGER_BASE + FALSE_TRIGGER_SCALE * exp(-FALSE_TRIGGER_DECAY * tau)


def trace_seed(archetype_key: str, replicate: int) -> int:
    """Seed schedule of Table A3."""
    return (
        PRIMARY_SEED
        + SEED_REPLICATE_STRIDE * replicate
        + SEED_ARCHETYPE_STRIDE * ARCHETYPE_INDEX[archetype_key]
    )


def _stream(seed: int, name: str) -> Random:
    return Random(seed + _STREAM_OFFSET[name])


# --------------------------------------------------------------------------
# Observation model
# --------------------------------------------------------------------------


def observe(
    true_demand: Mapping[str, float],
    rng: Random,
    sigma: float,
    attenuate: bool,
) -> Dict[str, float]:
    """Return a noisy observation of the true capability-demand vector.

    Gaussian noise is applied to every capability in canonical order.  When
    ``attenuate`` is set, each XR / digital-twin / AI signal is independently
    under-reported with probability ``ATTENUATION_PROBABILITY``; this models an
    SME that cannot see the new exposure clearly, not a hostile signal.
    Observations are clipped to ``[0, DEMAND_CAP]``.
    """
    observed: Dict[str, float] = {}
    for code in CODES:
        value = true_demand.get(code, 0.0) + rng.gauss(0.0, sigma)
        if attenuate and code in ATTENUATED_CODES:
            if rng.random() < ATTENUATION_PROBABILITY:
                value *= ATTENUATION_FACTOR
        observed[code] = min(DEMAND_CAP, max(0.0, value))
    return observed


# --------------------------------------------------------------------------
# Trace record
# --------------------------------------------------------------------------


@dataclass
class ConditionTrace:
    """Daily profile history of one condition on one trace."""

    name: str
    profiles: List[Tuple[str, ...]]
    reassessment_days: Tuple[int, ...]
    membership_changes: int
    review_hours: float
    false_alerts: int = 0

    def profile_on(self, day: int) -> Tuple[str, ...]:
        return self.profiles[day]


@dataclass
class TraceResult:
    """Everything one 120-day trace produces."""

    archetype: str
    replicate: int
    seed: int
    budget: int
    true_demand: List[Dict[str, float]]
    conditions: Dict[str, ConditionTrace]
    event_days: Tuple[int, ...] = ()
    triggered_review_days: Tuple[int, ...] = ()
    false_trigger_days: Tuple[int, ...] = ()
    above_threshold: Tuple[bool, ...] = ()
    extra: Dict[str, object] = field(default_factory=dict)


def _expand(profile: Tuple[str, ...], change_days: Sequence[Tuple[int, Tuple[str, ...]]],
            horizon: int) -> List[Tuple[str, ...]]:
    """Expand a list of (day, profile) changes into a per-day profile history."""
    history: List[Tuple[str, ...]] = []
    current = profile
    pending = {day: prof for day, prof in change_days}
    for day in range(horizon):
        if day in pending:
            current = pending[day]
        history.append(current)
    return history


def run_trace(
    archetype: Archetype,
    replicate: int,
    tau: float = PRIMARY_TAU,
    budget_factor: float = 1.0,
    lam: float = DEFAULT_LAMBDA,
    horizon: int = HORIZON_DAYS,
    seed: Optional[int] = None,
    conditions: Sequence[str] = ("static", "monthly", "acp"),
) -> TraceResult:
    """Simulate one complete 120-day trace under the requested conditions.

    All three conditions share the same day-0 profile, so any difference is
    attributable to reassessment timing and the resulting reallocation, not to
    a different starting point or a different sensing quality.
    """
    if seed is None:
        seed = trace_seed(archetype.key, replicate)
    budget = int(round(archetype.budget * budget_factor))

    true_demand = [archetype.demand_at(day) for day in range(horizon)]

    # --- shared day-0 profile ------------------------------------------------
    rng_initial = _stream(seed, "initial")
    day0_observation = observe(true_demand[0], rng_initial, INITIAL_NOISE_SIGMA, attenuate=False)
    initial: Selection = select(day0_observation, budget, lam=lam)
    assert_invariants(initial)
    initial_profile = initial.capabilities

    # --- event-score proxy and triggered review days -------------------------
    rng_events = _stream(seed, "events")
    triggered_days: List[int] = []
    above: List[bool] = []
    for event in archetype.events:
        score = event.proxy_score_base() + rng_events.gauss(0.0, EVENT_SCORE_NOISE_SIGMA)
        if score >= tau:
            delay = rng_events.choices(TRIGGERED_DELAY_DAYS, weights=TRIGGERED_DELAY_WEIGHTS)[0]
            above.append(True)
        else:
            delay = rng_events.randint(*SUBTHRESHOLD_DELAY_RANGE)
            above.append(False)
        review_day = event.day + delay
        if review_day < horizon:
            triggered_days.append(review_day)

    # --- nuisance triggers ---------------------------------------------------
    rng_false = _stream(seed, "false_triggers")
    p_false = false_trigger_probability(tau)
    false_days = [day for day in range(1, horizon) if rng_false.random() < p_false]

    result_conditions: Dict[str, ConditionTrace] = {}

    if "static" in conditions:
        result_conditions["static"] = ConditionTrace(
            name="static",
            profiles=[initial_profile] * horizon,
            reassessment_days=(),
            membership_changes=0,
            review_hours=STATIC_REVIEW_HOURS,
        )

    if "monthly" in conditions:
        rng_monthly = _stream(seed, "monthly")
        changes: List[Tuple[int, Tuple[str, ...]]] = []
        current = initial_profile
        membership_changes = 0
        for day in MONTHLY_REVIEW_DAYS:
            if day >= horizon:
                continue
            obs = observe(true_demand[day], rng_monthly, REASSESSMENT_NOISE_SIGMA, attenuate=True)
            chosen = select(obs, budget, lam=lam)
            assert_invariants(chosen)
            membership_changes += len(set(chosen.capabilities) ^ set(current))
            current = chosen.capabilities
            changes.append((day, current))
        result_conditions["monthly"] = ConditionTrace(
            name="monthly",
            profiles=_expand(initial_profile, changes, horizon),
            reassessment_days=tuple(d for d in MONTHLY_REVIEW_DAYS if d < horizon),
            membership_changes=membership_changes,
            review_hours=MONTHLY_REVIEW_HOURS_EACH * MONTHLY_REVIEW_COUNT,
        )

    if "acp" in conditions:
        rng_acp = _stream(seed, "acp")
        reassessment_days = sorted(set(triggered_days) | set(false_days))
        changes = []
        current = initial_profile
        membership_changes = 0
        for day in reassessment_days:
            obs = observe(true_demand[day], rng_acp, REASSESSMENT_NOISE_SIGMA, attenuate=True)
            chosen = select(obs, budget, lam=lam)
            assert_invariants(chosen)
            membership_changes += len(set(chosen.capabilities) ^ set(current))
            current = chosen.capabilities
            changes.append((day, current))
        review_hours = (
            ACP_INITIAL_HOURS
            + ACP_HOURS_PER_TRIGGER * len(reassessment_days)
            + ACP_HOURS_PER_MEMBERSHIP_CHANGE * membership_changes
        )
        result_conditions["acp"] = ConditionTrace(
            name="acp",
            profiles=_expand(initial_profile, changes, horizon),
            reassessment_days=tuple(reassessment_days),
            membership_changes=membership_changes,
            review_hours=review_hours,
            false_alerts=len([d for d in false_days if d not in set(triggered_days)]),
        )

    return TraceResult(
        archetype=archetype.key,
        replicate=replicate,
        seed=seed,
        budget=budget,
        true_demand=true_demand,
        conditions=result_conditions,
        event_days=tuple(e.day for e in archetype.events),
        triggered_review_days=tuple(sorted(triggered_days)),
        false_trigger_days=tuple(false_days),
        above_threshold=tuple(above),
    )
