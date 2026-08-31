"""Minimum Necessary Metadata Model (MNMM) and the local metadata guard.

Implements Table 2 and requirements R1 (metadata minimization), R2
(local-first processing) and R6 (fail-safe uncertainty).

Design rules enforced here:

* only allowlisted fields are accepted; anything else fails closed;
* exact values are converted to bands where precision is unnecessary;
* free text and payloads are rejected outright;
* stable source identifiers are replaced by tenant-keyed pseudonyms - the
  result is *pseudonymous*, never "anonymous";
* a missing or stale connector produces an ``UNKNOWN`` evidence state and a
  verification task, never a zero-risk value.

Nothing in this module transmits data anywhere.  Derivation, storage and
decision logic stay inside the SME boundary by construction.
"""

from __future__ import annotations

import hmac
import re
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from enum import Enum
from hashlib import sha256
from typing import Any, Dict, FrozenSet, Iterable, List, Mapping, Optional, Sequence, Tuple

SCHEMA_VERSION = "mnmm-0.1.0"


class FieldKind(Enum):
    COUNT = "count"
    BAND = "band"
    RATIO = "ratio"
    CATEGORY = "category"
    EVENT = "event"


class EvidenceState(Enum):
    """R6: absence of evidence is never evidence of security."""

    OBSERVED = "observed"
    STALE = "stale"
    UNKNOWN = "unknown"


@dataclass(frozen=True)
class FieldSpec:
    """One allowlisted MNMM field."""

    name: str
    group: str
    kind: FieldKind
    purpose: str
    categories: Tuple[str, ...] = ()
    bands: Tuple[Tuple[float, str], ...] = ()
    max_staleness_days: int = 30


def _band(*edges: Tuple[float, str]) -> Tuple[Tuple[float, str], ...]:
    return edges


#: Table 2, expressed as an executable allowlist.  Adding a field is a
#: versioned change to the schema pack, not a configuration tweak.
ALLOWLIST: Tuple[FieldSpec, ...] = (
    # Business context
    FieldSpec("headcount_band", "business_context", FieldKind.BAND,
              "interpret exposure and delivery capacity",
              bands=_band((10, "micro"), (50, "small"), (250, "medium"), (float("inf"), "large"))),
    FieldSpec("remote_work_band", "business_context", FieldKind.BAND,
              "interpret exposure and delivery capacity",
              bands=_band((0.2, "low"), (0.6, "mixed"), (1.01, "high"))),
    FieldSpec("sector", "business_context", FieldKind.CATEGORY, "interpret exposure",
              categories=("retail", "manufacturing", "services", "public", "other")),
    FieldSpec("jurisdiction_count", "business_context", FieldKind.COUNT, "interpret exposure"),
    FieldSpec("critical_process_count", "business_context", FieldKind.COUNT,
              "prioritize continuity"),
    # Processes
    FieldSpec("process_token", "processes", FieldKind.CATEGORY, "prioritize continuity"),
    FieldSpec("process_criticality", "processes", FieldKind.CATEGORY, "prioritize continuity",
              categories=("low", "moderate", "high", "critical")),
    FieldSpec("rto_band", "processes", FieldKind.BAND, "prioritize recovery",
              bands=_band((4, "hours"), (24, "day"), (72, "days"), (float("inf"), "extended"))),
    FieldSpec("rpo_band", "processes", FieldKind.BAND, "prioritize recovery",
              bands=_band((1, "near-zero"), (24, "day"), (float("inf"), "extended"))),
    # Assets and services
    FieldSpec("it_asset_count", "assets", FieldKind.COUNT, "inventory and hardening"),
    FieldSpec("iot_asset_count", "assets", FieldKind.COUNT, "inventory and hardening"),
    FieldSpec("xr_asset_count", "assets", FieldKind.COUNT, "inventory and hardening"),
    FieldSpec("ai_service_count", "assets", FieldKind.COUNT, "AI service governance"),
    FieldSpec("digital_twin_count", "assets", FieldKind.COUNT, "twin integrity"),
    FieldSpec("cloud_service_count", "assets", FieldKind.COUNT, "cloud-edge governance"),
    FieldSpec("end_of_support_ratio", "assets", FieldKind.RATIO, "lifecycle management"),
    FieldSpec("internet_facing_critical_count", "assets", FieldKind.COUNT, "exposure"),
    # Identity posture
    FieldSpec("privileged_account_count", "identity", FieldKind.COUNT, "access governance"),
    FieldSpec("external_account_count", "identity", FieldKind.COUNT, "access governance"),
    FieldSpec("mfa_coverage", "identity", FieldKind.RATIO, "access governance"),
    FieldSpec("dormant_account_count", "identity", FieldKind.COUNT, "access governance"),
    FieldSpec("recertification_age_days", "identity", FieldKind.COUNT, "access governance"),
    # Data posture
    FieldSpec("restricted_data_present", "data", FieldKind.CATEGORY, "protection decisions",
              categories=("yes", "no")),
    FieldSpec("data_volume_band", "data", FieldKind.BAND, "protection decisions",
              bands=_band((1e3, "small"), (1e6, "medium"), (float("inf"), "large"))),
    FieldSpec("residency_class", "data", FieldKind.CATEGORY, "jurisdiction decisions",
              categories=("domestic", "regional", "international", "mixed")),
    FieldSpec("new_restricted_flow", "data", FieldKind.CATEGORY, "protection decisions",
              categories=("yes", "no")),
    # Suppliers
    FieldSpec("supplier_token", "suppliers", FieldKind.CATEGORY, "supply-chain governance"),
    FieldSpec("supplier_criticality", "suppliers", FieldKind.CATEGORY, "supply-chain governance",
              categories=("low", "moderate", "high", "critical")),
    FieldSpec("supplier_access_type", "suppliers", FieldKind.CATEGORY, "supply-chain governance",
              categories=("none", "read", "write", "privileged")),
    FieldSpec("supplier_assurance_age_days", "suppliers", FieldKind.COUNT,
              "supply-chain governance"),
    # Security evidence
    FieldSpec("backup_coverage", "evidence", FieldKind.RATIO, "estimate current coverage"),
    FieldSpec("logging_coverage", "evidence", FieldKind.RATIO, "estimate current coverage"),
    FieldSpec("control_state", "evidence", FieldKind.CATEGORY, "estimate current coverage",
              categories=("not_implemented", "partial", "implemented", "verified")),
    # Change and incident
    FieldSpec("event_class", "change_incident", FieldKind.EVENT, "immediate reassessment"),
    FieldSpec("severity_band", "change_incident", FieldKind.CATEGORY, "immediate reassessment",
              categories=("low", "moderate", "high", "critical")),
    FieldSpec("twin_operational_link", "change_incident", FieldKind.CATEGORY,
              "twin integrity", categories=("yes", "no")),
    # Resource limits
    FieldSpec("security_hours_band", "resources", FieldKind.BAND, "feasible plan",
              bands=_band((4, "minimal"), (20, "limited"), (80, "moderate"),
                          (float("inf"), "substantial"))),
    FieldSpec("budget_units", "resources", FieldKind.COUNT, "feasible plan"),
    FieldSpec("complexity_ceiling", "resources", FieldKind.CATEGORY, "feasible plan",
              categories=("low", "moderate", "high")),
)

SPECS: Dict[str, FieldSpec] = {spec.name: spec for spec in ALLOWLIST}

#: Table 2 "explicit exclusions", expressed as a deny list.  The allowlist alone
#: already rejects these; the deny list makes the intent auditable and lets the
#: guard report *why* a connector failed.
PROHIBITED_PATTERNS: Tuple[Tuple[str, str], ...] = (
    (r"name", "personal or organizational names"),
    (r"email", "direct identifiers"),
    (r"phone", "direct identifiers"),
    (r"address", "direct identifiers"),
    (r"salary|payroll|wage", "employment and financial records"),
    (r"username|user_id|login|account_id", "direct account identifiers"),
    (r"password|secret|token_value|credential|api_key", "secrets"),
    (r"biometric", "biometric templates"),
    (r"payload|content|body|raw_log|narrative|description|comment|note",
     "business content and free text"),
    (r"customer|patient|employee_record", "customer or employee records"),
    (r"contract_text|clause", "contract text"),
    (r"ip_address|mac_address|device_history", "device and network identifiers"),
)

_PROHIBITED = tuple((re.compile(p, re.IGNORECASE), reason) for p, reason in PROHIBITED_PATTERNS)

#: Any string longer than this is treated as free text and rejected (R1).
MAX_CATEGORY_LENGTH = 64


class MetadataRejected(ValueError):
    """Raised when a connector record violates the minimization boundary."""

    def __init__(self, field: str, reason: str) -> None:
        super().__init__(f"rejected field {field!r}: {reason}")
        self.field = field
        self.reason = reason


@dataclass(frozen=True)
class Observation:
    """One accepted MNMM record (observation, relevance, quality, governance)."""

    tenant: str
    entity_token: str
    window: date
    field: str
    value: Any
    band: Optional[str]
    source_type: str
    observed_at: datetime
    completeness: float
    state: EvidenceState
    purpose: str
    access_class: str = "internal"
    schema_version: str = SCHEMA_VERSION
    delete_after: Optional[date] = None

    @property
    def is_usable(self) -> bool:
        return self.state is EvidenceState.OBSERVED


def pseudonymize(tenant_key: bytes, value: str) -> str:
    """Tenant-keyed pseudonym for a stable source identifier.

    Keyed so that the same identifier is not linkable across tenants.  The
    result is pseudonymous data under GDPR, not anonymous data.
    """
    digest = hmac.new(tenant_key, value.encode("utf-8"), sha256).hexdigest()
    return f"tok_{digest[:16]}"


def band_of(spec: FieldSpec, value: float) -> Optional[str]:
    """Convert an exact value to its approved band, if the field is banded."""
    if spec.kind not in (FieldKind.BAND,):
        return None
    for edge, label in spec.bands:
        if value < edge:
            return label
    return spec.bands[-1][1] if spec.bands else None


def check_prohibited(field_name: str) -> None:
    for pattern, reason in _PROHIBITED:
        if pattern.search(field_name):
            raise MetadataRejected(field_name, f"prohibited ({reason})")


@dataclass
class MetadataGuard:
    """Local metadata guard: validate, band, pseudonymize, and fail closed.

    The guard is the trust boundary of Figure 1.  A connector that emits a
    prohibited field fails closed; a connector that emits nothing produces an
    ``UNKNOWN`` evidence state and a verification task.
    """

    tenant: str
    tenant_key: bytes
    retention_days: int = 400
    now: Optional[datetime] = None
    rejections: List[Tuple[str, str]] = field(default_factory=list)
    verification_tasks: List[str] = field(default_factory=list)

    def _clock(self) -> datetime:
        return self.now or datetime.utcnow()

    def accept(
        self,
        record: Mapping[str, Any],
        source_type: str,
        entity: str = "enterprise",
        observed_at: Optional[datetime] = None,
    ) -> List[Observation]:
        """Validate one connector record and return the accepted observations.

        Raises :class:`MetadataRejected` on the first prohibited field: the
        guard fails closed rather than silently dropping it, so a misconfigured
        connector is visible instead of quietly degrading the evidence base.
        """
        observed_at = observed_at or self._clock()
        entity_token = pseudonymize(self.tenant_key, entity)
        window = observed_at.date()
        accepted: List[Observation] = []

        for name, raw in record.items():
            check_prohibited(name)
            spec = SPECS.get(name)
            if spec is None:
                self.rejections.append((name, "not on the allowlist"))
                raise MetadataRejected(name, "not on the allowlist")
            value, band = self._normalise(spec, name, raw)
            accepted.append(
                Observation(
                    tenant=self.tenant,
                    entity_token=entity_token,
                    window=window,
                    field=name,
                    value=value,
                    band=band,
                    source_type=source_type,
                    observed_at=observed_at,
                    completeness=1.0,
                    state=self._state(spec, observed_at),
                    purpose=spec.purpose,
                    delete_after=window + timedelta(days=self.retention_days),
                )
            )
        return accepted

    def _normalise(self, spec: FieldSpec, name: str, raw: Any) -> Tuple[Any, Optional[str]]:
        if isinstance(raw, str):
            if len(raw) > MAX_CATEGORY_LENGTH:
                raise MetadataRejected(name, "free text exceeds the category length limit")
            if name.endswith("_token"):
                # Stable source identifiers never enter the store in the clear.
                return pseudonymize(self.tenant_key, raw), None
            if spec.categories and raw not in spec.categories:
                raise MetadataRejected(name, "value not in the approved category set")
            if not spec.categories:
                raise MetadataRejected(name, "free-form strings are not accepted")
            return raw, None
        if isinstance(raw, bool):
            raise MetadataRejected(name, "bare booleans are ambiguous; use an approved category")
        if isinstance(raw, (int, float)):
            if spec.kind is FieldKind.RATIO and not 0.0 <= float(raw) <= 1.0:
                raise MetadataRejected(name, "ratio outside [0, 1]")
            if spec.kind is FieldKind.COUNT and (raw < 0 or raw != int(raw)):
                raise MetadataRejected(name, "count must be a non-negative integer")
            if spec.kind is FieldKind.BAND:
                # Precision is unnecessary: retain only the band (R1).
                return None, band_of(spec, float(raw))
            return raw, None
        raise MetadataRejected(name, f"unsupported value type {type(raw).__name__}")

    def _state(self, spec: FieldSpec, observed_at: datetime) -> EvidenceState:
        age = (self._clock() - observed_at).days
        if age > spec.max_staleness_days:
            self.verification_tasks.append(
                f"{spec.name}: evidence is {age} days old "
                f"(limit {spec.max_staleness_days}); verify before relying on it"
            )
            return EvidenceState.STALE
        return EvidenceState.OBSERVED

    def missing(self, expected_fields: Iterable[str]) -> List[Observation]:
        """Emit an ``UNKNOWN`` observation for each field a connector did not send.

        R6: a missing connector must not be read as a zero-risk value.
        """
        out: List[Observation] = []
        now = self._clock()
        for name in expected_fields:
            spec = SPECS[name]
            self.verification_tasks.append(
                f"{name}: no evidence received; raise a verification task "
                "(absence is not a secure state)"
            )
            out.append(
                Observation(
                    tenant=self.tenant,
                    entity_token=pseudonymize(self.tenant_key, "enterprise"),
                    window=now.date(),
                    field=name,
                    value=None,
                    band=None,
                    source_type="missing",
                    observed_at=now,
                    completeness=0.0,
                    state=EvidenceState.UNKNOWN,
                    purpose=spec.purpose,
                )
            )
        return out


def allowlisted_fields() -> FrozenSet[str]:
    return frozenset(SPECS)


def business_state(observations: Sequence[Observation]) -> Dict[str, Any]:
    """Aggregate accepted observations into the tenant-local business-state vector.

    Unknown and stale evidence is *not* folded into the vector; it is reported
    separately so the detector can treat it as uncertainty rather than as a
    settled value.
    """
    state: Dict[str, Any] = {}
    for obs in observations:
        if not obs.is_usable:
            continue
        state[obs.field] = obs.band if obs.band is not None else obs.value
    return state
