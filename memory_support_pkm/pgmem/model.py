"""Evidence-typed personal event base (Section 4.2, Equation 1).

Each record is r_i = (c_i, t_i, s_i, kappa_i, sigma_i, v_i, e_i):
content, time, source/provenance, confidence indicator, consent scope,
version and evidence status.  Corrections create new linked versions,
disagreements are marked as disputed, deletions leave only a minimal
audit event (no content).
"""
from __future__ import annotations

import itertools
from dataclasses import dataclass, field, replace
from datetime import datetime
from enum import Enum
from typing import Callable, Iterable


class EvidenceStatus(str, Enum):
    PLAN = "plan"                # entered as an intention / schedule
    SELF_REPORT = "self_report"  # the person said it happened
    OBSERVATION = "observation"  # sensor / external log observed it
    INFERENCE = "inference"      # drawn by the assistant
    DISPUTED = "disputed"        # incompatible records exist


# Which record statuses can support a claim that asserts a given status (I2).
# A plan supports "it was scheduled", never "it happened".
SUPPORTS: dict[EvidenceStatus, set[EvidenceStatus]] = {
    EvidenceStatus.PLAN: {EvidenceStatus.PLAN, EvidenceStatus.SELF_REPORT, EvidenceStatus.OBSERVATION},
    EvidenceStatus.SELF_REPORT: {EvidenceStatus.SELF_REPORT},
    EvidenceStatus.OBSERVATION: {EvidenceStatus.OBSERVATION},
    EvidenceStatus.INFERENCE: {EvidenceStatus.INFERENCE},
}

STATUS_STRENGTH = {
    EvidenceStatus.INFERENCE: 0,
    EvidenceStatus.PLAN: 1,
    EvidenceStatus.SELF_REPORT: 2,
    EvidenceStatus.OBSERVATION: 3,
}


@dataclass(frozen=True)
class Record:
    """One versioned entry of the personal event base."""

    record_id: str
    person_id: str
    subject: str                 # event identity, e.g. "appt:dr_kovalenko:2026-10-02"
    content: str                 # c_i
    time: datetime               # t_i
    source: str                  # s_i: calendar, user_voice, sensor:pillbox, carer_entry ...
    kappa: float                 # confidence indicator in [0, 1], not a probability
    scope: frozenset[str]        # sigma_i: recipients allowed to see it
    version: int = 1             # v_i
    status: EvidenceStatus = EvidenceStatus.PLAN  # e_i
    category: str = "general"    # data category used by consent scopes
    kind: str = "event"          # claim kind this record speaks to: scheduled/occurred/content
    value: str = ""              # normalised value of the claim (date, "true", note text)
    supersedes: str | None = None
    active: bool = True
    disputed: bool = False

    def __post_init__(self) -> None:
        if not 0.0 <= self.kappa <= 1.0:
            raise ValueError("kappa must lie in [0, 1]")


@dataclass
class AuditEvent:
    time: datetime
    actor: str
    action: str
    record_id: str
    detail: str = ""


class PersonalEventBase:
    """E = {r_1, ..., r_n} with versioning, disputes, deletion and audit."""

    def __init__(self, person_id: str):
        self.person_id = person_id
        self._records: dict[str, Record] = {}
        self.audit: list[AuditEvent] = []
        self._ids = itertools.count(1)
        self._listeners: list[Callable[[str], None]] = []

    # -- change notification (used by I4 cache invalidation) --------------
    def on_change(self, fn: Callable[[str], None]) -> None:
        self._listeners.append(fn)

    def _notify(self, subject: str) -> None:
        for fn in self._listeners:
            fn(subject)

    def new_id(self) -> str:
        return f"{self.person_id}-r{next(self._ids):05d}"

    # -- writes ------------------------------------------------------------
    def add(self, record: Record, actor: str = "system", when: datetime | None = None) -> Record:
        if record.person_id != self.person_id:
            raise ValueError("record belongs to another person")
        self._records[record.record_id] = record
        self.audit.append(AuditEvent(when or record.time, actor, "add", record.record_id, record.status.value))
        self._notify(record.subject)
        return record

    def correct(self, record_id: str, actor: str, when: datetime, **changes) -> Record:
        """Corrections never overwrite: a new linked version is created."""
        old = self._records[record_id]
        new = replace(old, record_id=self.new_id(), version=old.version + 1,
                      supersedes=old.record_id, active=True, **changes)
        self._records[old.record_id] = replace(old, active=False)
        self._records[new.record_id] = new
        self.audit.append(AuditEvent(when, actor, "correct", new.record_id, f"supersedes {old.record_id}"))
        self._notify(old.subject)
        return new

    def mark_disputed(self, record_ids: Iterable[str], actor: str, when: datetime) -> None:
        subjects = set()
        for rid in record_ids:
            r = self._records[rid]
            self._records[rid] = replace(r, disputed=True)
            subjects.add(r.subject)
            self.audit.append(AuditEvent(when, actor, "dispute", rid))
        for s in subjects:
            self._notify(s)

    def delete(self, record_id: str, actor: str, when: datetime) -> None:
        """Content is removed; the audit keeps only that a deletion happened."""
        r = self._records.pop(record_id)
        self.audit.append(AuditEvent(when, actor, "delete", record_id))
        self._notify(r.subject)

    # -- reads -------------------------------------------------------------
    def get(self, record_id: str) -> Record:
        return self._records[record_id]

    def all(self, include_inactive: bool = False) -> list[Record]:
        return [r for r in self._records.values() if include_inactive or r.active]

    def by_subject(self, subject: str, include_inactive: bool = False) -> list[Record]:
        return [r for r in self.all(include_inactive) if r.subject == subject]

    def __len__(self) -> int:
        return len(self._records)


class EpisodeState(str, Enum):
    """Explicit task-episode states (DP3, I3)."""

    PENDING = "pending"
    ACTIVE = "active"
    COMPLETED = "completed"   # always paired with a stated source
    POSTPONED = "postponed"
    DECLINED = "declined"
    UNKNOWN = "unknown"
    # Only produced by baselines that violate I3:
    MISSED_INFERRED = "missed_inferred"


@dataclass
class Episode:
    episode_id: str
    person_id: str
    task_type: str
    scheduled: datetime
    safety_critical: bool
    state: EpisodeState = EpisodeState.PENDING
    completion_source: str | None = None
    levels: list[int] = field(default_factory=list)

    def complete(self, source: str) -> None:
        if not source:
            raise ValueError("completion needs an explicit evidential basis (I3)")
        self.state = EpisodeState.COMPLETED
        self.completion_source = source
