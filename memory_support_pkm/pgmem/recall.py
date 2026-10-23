"""Grounded recall and uncertainty (Section 4.4, Equations 4 and 5).

Three assistants share one interface ``answer(question) -> Answer``:

* ``GroundedRecall``  – the proposed policy (permission filter, evidence-type
  check, conflict/identity check before thresholding, release rule).
* ``NaiveRAG``        – a single-agent retrieval assistant used as a baseline.
* ``ReminderOnly``    – a reminder interface that cannot answer questions.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable

import numpy as np

from .governance import PolicyEngine
from .model import STATUS_STRENGTH, SUPPORTS, EvidenceStatus, PersonalEventBase, Record

THETA_LOW = 0.40
THETA_HIGH = 0.75


@dataclass(frozen=True)
class Question:
    question_id: str
    person_id: str
    requester: str            # who is asking (the person or a trusted person)
    subject: str              # event identity the question refers to
    kind: str                 # scheduled / occurred / content
    category: str
    text: str = ""


@dataclass(frozen=True)
class Claim:
    """An atomic claim a_j (Min et al., 2023)."""

    subject: str
    kind: str
    value: str
    asserted_status: EvidenceStatus
    record_id: str | None     # None => no record behind the claim (fabrication)
    record_version: int | None = None


@dataclass
class Answer:
    decision: str             # answer / answer_uncertain / abstain / clarify / refuse / none
    claims: list[Claim] = field(default_factory=list)
    s_min: float | None = None
    text: str = ""
    disclosed_records: list[str] = field(default_factory=list)

    @property
    def substantive(self) -> bool:
        return self.decision in ("answer", "answer_uncertain")


def support_score(claim: Claim, records: list[Record],
                  sup: Callable[[Claim, Record], float]) -> float:
    """Equation (4): S(a_j) = max_{r in R(q)} sup(a_j, r) * kappa_r.
    Heuristic, neither a probability nor independent verification."""
    if not records:
        return 0.0
    return max(sup(claim, r) * r.kappa for r in records)


def release(s_min: float, theta_low: float = THETA_LOW, theta_high: float = THETA_HIGH) -> str:
    """Equation (5)."""
    if s_min >= theta_high:
        return "answer"
    if s_min >= theta_low:
        return "answer_uncertain"
    return "abstain"


def exact_sup(claim: Claim, r: Record) -> float:
    """Reference entailment: identity, kind, value and evidence type must match."""
    if r.subject != claim.subject or r.kind != claim.kind or r.value != claim.value:
        return 0.0
    return 1.0 if r.status in SUPPORTS[claim.asserted_status] else 0.0


def noisy_sup(rng: np.random.Generator, sd: float = 0.12) -> Callable[[Claim, Record], float]:
    """An imperfect entailment estimator, as any real NLI model would be."""
    def f(claim: Claim, r: Record) -> float:
        base = exact_sup(claim, r)
        return float(np.clip(base + rng.normal(0, sd) - (0.05 if base else 0.0), 0, 1))
    return f


_TEMPLATES = {
    ("scheduled", EvidenceStatus.PLAN): "У вашому календарі записано: {value}.",
    ("occurred", EvidenceStatus.SELF_REPORT): "Ви зафіксували {time}, що це зроблено. Незалежно я це не перевіряв.",
    ("occurred", EvidenceStatus.OBSERVATION): "Це зафіксовано джерелом «{source}» {time}.",
    ("content", EvidenceStatus.PLAN): "У нотатці записано: «{value}».",
    ("content", EvidenceStatus.SELF_REPORT): "Ви занотували: «{value}».",
}


class GroundedRecall:
    """The proposed recall policy (Figure 2b)."""

    def __init__(self, base: PersonalEventBase, policy: PolicyEngine,
                 sup: Callable[[Claim, Record], float] = exact_sup,
                 theta_low: float = THETA_LOW, theta_high: float = THETA_HIGH,
                 identity_confusion: float = 0.0, rng: np.random.Generator | None = None):
        self.base, self.policy, self.sup = base, policy, sup
        self.theta_low, self.theta_high = theta_low, theta_high
        self.identity_confusion = identity_confusion
        self.rng = rng or np.random.default_rng(0)
        self._cache: dict[tuple, tuple[Answer, tuple]] = {}
        base.on_change(self._invalidate)

    # I4: corrections, disputes and deletions invalidate cached answers.
    def _invalidate(self, subject: str) -> None:
        for key in [k for k in self._cache if k[1] == subject]:
            del self._cache[key]

    def _retrieve(self, q: Question) -> list[Record]:
        recs = [r for r in self.base.all()
                if self.policy.allows(q.requester, r.category, "read")]       # I1
        hits = [r for r in recs if r.subject == q.subject]
        if self.identity_confusion and self.rng.random() < self.identity_confusion:
            # Retriever slips in a record about a similar but different event.
            similar = [r for r in recs if r.subject != q.subject and r.subject.split(":")[0] == q.subject.split(":")[0]]
            if similar:
                hits = hits + [similar[int(self.rng.integers(len(similar)))]]
        return hits

    def answer(self, q: Question) -> Answer:
        # Permissions travel with cached answers: any grant change is a cache miss (I1, I4).
        key = (q.requester, q.subject, q.kind, frozenset(self.policy.grants))
        if key in self._cache:
            return self._cache[key][0]
        ans = self._answer(q)
        self._cache[key] = (ans, tuple(c.record_id for c in ans.claims))
        return ans

    def _answer(self, q: Question) -> Answer:
        if not self.policy.allows(q.requester, q.category, "read"):
            return Answer("refuse", text="Я не можу поділитися цією інформацією без вашого дозволу.")
        hits = self._retrieve(q)
        if not hits:
            return Answer("abstain", text="У мене немає жодного запису про це, і я не можу цього знати.")
        # Conflict / identity checks precede thresholding: a max cannot resolve contradictions.
        if any(r.disputed for r in hits):
            return Answer("clarify", text="Записи про це суперечать один одному. Давайте уточнимо разом.")
        if len({r.subject for r in hits}) > 1:
            return Answer("clarify", text="Я знайшов записи про кілька схожих подій. Яку саме ви маєте на увазі?")
        values = {(r.kind, r.value) for r in hits if r.kind == q.kind}
        if len(values) > 1:
            return Answer("clarify", text="Є кілька несумісних записів. Давайте уточнимо.")

        # Draft: the strongest claim the records allow, never stronger (I2).
        same_kind = [r for r in hits if r.kind == q.kind]
        limit_note = ""
        if q.kind == "occurred" and not same_kind:
            # Only a plan exists: answer about the schedule and state the limit.
            same_kind = [r for r in hits if r.kind == "scheduled"]
            limit_note = " Ці записи не підтверджують, що подія відбулася."
        if not same_kind:
            return Answer("abstain", text="Записи не стосуються саме цього питання.")
        best = max(same_kind, key=lambda r: (STATUS_STRENGTH.get(r.status, 0), r.time))
        claim = Claim(best.subject, best.kind, best.value, best.status, best.record_id, best.version)
        s = support_score(claim, hits, self.sup)
        decision = release(s, self.theta_low, self.theta_high)
        if decision == "abstain":
            return Answer("abstain", s_min=s, text="Я не впевнений і не хочу вигадувати відповідь.")
        tpl = _TEMPLATES.get((claim.kind, claim.asserted_status), "Запис: {value}.")
        text = tpl.format(value=best.value, source=best.source, time=best.time.strftime("%d.%m о %H:%M")) + limit_note
        if decision == "answer_uncertain":
            text += " (Підтримка запису неповна — варто перевірити.)"
        return Answer(decision, [claim], s, text, [best.record_id])


class NaiveRAG:
    """Single-agent retrieval assistant without evidence typing or governance."""

    def __init__(self, base: PersonalEventBase, rng: np.random.Generator,
                 p_fabricate: float = 0.4, p_stale: float = 0.3):
        self.base, self.rng = base, rng
        self.p_fabricate, self.p_stale = p_fabricate, p_stale

    def answer(self, q: Question) -> Answer:
        pool = self.base.all(include_inactive=self.rng.random() < self.p_stale)
        hits = [r for r in pool if r.subject == q.subject]          # no permission filter
        if not hits:
            if self.rng.random() < self.p_fabricate:
                fake = Claim(q.subject, q.kind, "true" if q.kind == "occurred" else "вигадано",
                             EvidenceStatus.OBSERVATION, None)
                return Answer("answer", [fake], 1.0, "Так, це було.")
            return Answer("abstain", text="Не знаю.")
        best = max(hits, key=lambda r: r.kappa)                       # highest score wins
        value = best.value
        if q.kind == "occurred" and best.kind == "scheduled":
            value = "true"                                            # plan read as attendance
        claim = Claim(q.subject, q.kind, value, EvidenceStatus.OBSERVATION, best.record_id, best.version)
        return Answer("answer", [claim], best.kappa, f"Так: {value}.", [best.record_id])


class ReminderOnly:
    def answer(self, q: Question) -> Answer:
        return Answer("none", text="(інтерфейс нагадувань не відповідає на запитання)")
