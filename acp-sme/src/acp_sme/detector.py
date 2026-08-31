"""Material-change detector (Equations 1 and 2).

Approved-profile distance::

    D_t = sum_j w_j * delta_{j,t},   w_j >= 0,   sum_j w_j = 1              (1)

Material-change indicator::

    M_t = 1{ C_t = 1  or  P_{2,3}(D_t >= tau)  or  Q_t = 1 }                (2)

where ``C_t`` is the critical deterministic predicate, ``P_{2,3}`` the
two-of-three persistence rule, ``Q_t`` the scheduled-review timer and ``tau``
the approved distance threshold.

Thresholds and weights are *configuration values* approved by a human owner.
They are not parameters fitted to the reported test traces.

Note on scope: the synthetic experiment of :mod:`acp_sme.simulator` uses the
disclosed event-score proxy of Section 3.7 rather than this detector.  This
module is the artifact's actual detection logic and is verified by unit tests,
not by the reported experiment.
"""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Deque, Dict, Iterable, List, Mapping, Optional, Sequence, Tuple

from .metadata_model import EvidenceState, Observation

#: Version of the detection rule pack (R7).
RULE_PACK_VERSION = "rule-pack-0.1.0"

#: Default approved distance threshold.
DEFAULT_TAU = 0.28

#: Persistence window and required hits for the P_{2,3} rule.
PERSISTENCE_WINDOW = 3
PERSISTENCE_HITS = 2


class FeatureType(Enum):
    NUMERIC = "numeric"
    CATEGORY = "category"
    SET = "set"


@dataclass(frozen=True)
class FeatureSpec:
    """One feature of the business-state vector used by Equation (1)."""

    name: str
    type: FeatureType
    weight: float
    #: Scale used to normalise a numeric difference before clipping to [0, 1].
    scale: float = 1.0


def normalise_weights(specs: Sequence[FeatureSpec]) -> Tuple[FeatureSpec, ...]:
    """Rescale weights so that they are non-negative and sum to one (Eq. 1)."""
    if any(spec.weight < 0 for spec in specs):
        raise ValueError("feature weights must be non-negative")
    total = sum(spec.weight for spec in specs)
    if total <= 0:
        raise ValueError("feature weights must sum to a positive value")
    return tuple(
        FeatureSpec(s.name, s.type, s.weight / total, s.scale) for s in specs
    )


def distance(spec: FeatureSpec, current: Any, baseline: Any) -> float:
    """Type-specific distance ``delta_{j,t}``, bounded in [0, 1]."""
    if current is None or baseline is None:
        # R6: unknown evidence contributes maximum uncertainty, not zero change.
        return 1.0
    if spec.type is FeatureType.NUMERIC:
        if isinstance(baseline, (tuple, list)) and len(baseline) == 2:
            low, high = float(baseline[0]), float(baseline[1])
            value = float(current)
            if low <= value <= high:
                return 0.0
            gap = low - value if value < low else value - high
            return min(1.0, abs(gap) / spec.scale)
        return min(1.0, abs(float(current) - float(baseline)) / spec.scale)
    if spec.type is FeatureType.CATEGORY:
        return 0.0 if current == baseline else 1.0
    if spec.type is FeatureType.SET:
        a, b = set(current), set(baseline)
        union = a | b
        if not union:
            return 0.0
        return 1.0 - len(a & b) / len(union)
    raise ValueError(f"unsupported feature type {spec.type}")


def profile_distance(
    specs: Sequence[FeatureSpec],
    current: Mapping[str, Any],
    baseline: Mapping[str, Any],
) -> float:
    """Equation (1): weighted approved-profile distance ``D_t``."""
    specs = normalise_weights(specs)
    return sum(
        spec.weight * distance(spec, current.get(spec.name), baseline.get(spec.name))
        for spec in specs
    )


# --------------------------------------------------------------------------
# Critical deterministic predicates (Section 3.4)
# --------------------------------------------------------------------------

CriticalPredicate = Callable[[Mapping[str, Any], Mapping[str, Any]], bool]


def _grew(current: Mapping[str, Any], baseline: Mapping[str, Any], key: str) -> bool:
    now, before = current.get(key), baseline.get(key)
    return now is not None and before is not None and now > before


def _dropped(
    current: Mapping[str, Any], baseline: Mapping[str, Any], key: str, margin: float
) -> bool:
    now, before = current.get(key), baseline.get(key)
    return now is not None and before is not None and (before - now) >= margin


#: The five critical predicates named in Section 3.4.  Each fires deterministically:
#: no threshold, no persistence rule, no probability.
CRITICAL_PREDICATES: Tuple[Tuple[str, CriticalPredicate], ...] = (
    (
        "new internet-facing critical service",
        lambda cur, base: _grew(cur, base, "internet_facing_critical_count"),
    ),
    (
        "persistent privileged supplier access",
        lambda cur, base: cur.get("supplier_access_type") == "privileged"
        and base.get("supplier_access_type") != "privileged",
    ),
    (
        "new restricted-data flow",
        lambda cur, base: cur.get("new_restricted_flow") == "yes",
    ),
    (
        "digital twin connected to operational telemetry",
        lambda cur, base: cur.get("twin_operational_link") == "yes"
        and base.get("twin_operational_link") != "yes",
    ),
    (
        "material loss of MFA, backup or logging coverage",
        lambda cur, base: any(
            _dropped(cur, base, key, 0.10)
            for key in ("mfa_coverage", "backup_coverage", "logging_coverage")
        ),
    ),
)


@dataclass(frozen=True)
class Decision:
    """Outcome of one decision window."""

    window: int
    distance: float
    material: bool
    critical: Tuple[str, ...]
    persistent: bool
    scheduled: bool
    verification_tasks: Tuple[str, ...] = ()

    @property
    def trigger(self) -> str:
        if self.critical:
            return "critical: " + "; ".join(self.critical)
        if self.persistent:
            return f"persistent distance >= threshold in {PERSISTENCE_HITS} of {PERSISTENCE_WINDOW} windows"
        if self.scheduled:
            return "scheduled periodic review"
        return "no material change"


@dataclass
class MaterialChangeDetector:
    """Hybrid periodic and event-driven detector implementing Equation (2)."""

    features: Sequence[FeatureSpec]
    tau: float = DEFAULT_TAU
    review_period_days: Optional[int] = 90
    rule_pack_version: str = RULE_PACK_VERSION
    _history: Deque[bool] = field(default_factory=lambda: deque(maxlen=PERSISTENCE_WINDOW))
    _window: int = 0

    def evaluate(
        self,
        current: Mapping[str, Any],
        baseline: Mapping[str, Any],
        observations: Iterable[Observation] = (),
        scheduled: Optional[bool] = None,
    ) -> Decision:
        """Evaluate one decision window and return the material-change decision."""
        window = self._window
        self._window += 1

        d = profile_distance(self.features, current, baseline)
        self._history.append(d >= self.tau)
        persistent = sum(self._history) >= PERSISTENCE_HITS

        critical = tuple(
            label for label, predicate in CRITICAL_PREDICATES if predicate(current, baseline)
        )

        if scheduled is None:
            scheduled = bool(
                self.review_period_days
                and window > 0
                and window % self.review_period_days == 0
            )

        tasks = tuple(
            f"{obs.field}: evidence state {obs.state.value}; verify before use"
            for obs in observations
            if obs.state is not EvidenceState.OBSERVED
        )

        return Decision(
            window=window,
            distance=d,
            material=bool(critical) or persistent or scheduled,
            critical=critical,
            persistent=persistent,
            scheduled=scheduled,
            verification_tasks=tasks,
        )

    def reset(self) -> None:
        self._history.clear()
        self._window = 0


#: A worked default feature set for an SME business-state vector.  Weights are
#: approved configuration, not fitted parameters; they are renormalised to sum
#: to one by Equation (1).
DEFAULT_FEATURES: Tuple[FeatureSpec, ...] = (
    FeatureSpec("cloud_service_count", FeatureType.NUMERIC, 0.10, scale=10.0),
    FeatureSpec("xr_asset_count", FeatureType.NUMERIC, 0.12, scale=5.0),
    FeatureSpec("digital_twin_count", FeatureType.NUMERIC, 0.12, scale=3.0),
    FeatureSpec("ai_service_count", FeatureType.NUMERIC, 0.12, scale=5.0),
    FeatureSpec("iot_asset_count", FeatureType.NUMERIC, 0.08, scale=50.0),
    FeatureSpec("privileged_account_count", FeatureType.NUMERIC, 0.08, scale=10.0),
    FeatureSpec("mfa_coverage", FeatureType.NUMERIC, 0.10, scale=1.0),
    FeatureSpec("end_of_support_ratio", FeatureType.NUMERIC, 0.06, scale=1.0),
    FeatureSpec("residency_class", FeatureType.CATEGORY, 0.06),
    FeatureSpec("supplier_access_type", FeatureType.CATEGORY, 0.08),
    FeatureSpec("headcount_band", FeatureType.CATEGORY, 0.04),
    FeatureSpec("sector", FeatureType.CATEGORY, 0.04),
)
