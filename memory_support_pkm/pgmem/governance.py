"""Consent, access control and the dispatch-time permission check (I1, I4)."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime

from .model import AuditEvent


@dataclass
class PolicyEngine:
    """Revisable consent scopes keyed by (recipient, data category, action)."""

    person_id: str
    grants: set[tuple[str, str, str]] = field(default_factory=set)
    audit: list[AuditEvent] = field(default_factory=list)

    def grant(self, recipient: str, category: str, action: str) -> None:
        self.grants.add((recipient, category, action))

    def revoke(self, recipient: str, category: str, action: str) -> None:
        self.grants.discard((recipient, category, action))

    def allows(self, recipient: str, category: str, action: str) -> bool:
        # The person always sees and controls their own data.
        if recipient == self.person_id:
            return True
        return (recipient, category, action) in self.grants or (recipient, "*", action) in self.grants


@dataclass
class QueuedAction:
    key: str            # idempotency key: replay never duplicates (I4)
    kind: str           # message / disclosure / prompt
    recipient: str
    category: str
    payload: str
    created: datetime


class ActionQueue:
    """Actions are permitted at execution time, not at queueing time (I1)."""

    def __init__(self, policy: PolicyEngine):
        self.policy = policy
        self.pending: list[QueuedAction] = []
        self.sent: dict[str, QueuedAction] = {}
        self.cancelled: list[QueuedAction] = []

    def enqueue(self, action: QueuedAction) -> None:
        if action.key in self.sent or any(a.key == action.key for a in self.pending):
            return
        self.pending.append(action)

    def dispatch(self, now: datetime) -> list[QueuedAction]:
        delivered = []
        for a in self.pending:
            if a.key in self.sent:
                continue
            if self.policy.allows(a.recipient, a.category, a.kind):
                self.sent[a.key] = a
                delivered.append(a)
                self.policy.audit.append(AuditEvent(now, "assistant", f"send:{a.kind}", a.key, a.recipient))
            else:
                self.cancelled.append(a)
                self.policy.audit.append(AuditEvent(now, "assistant", "cancel", a.key, "permission changed"))
        self.pending = []
        return delivered
