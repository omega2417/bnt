"""Response federate: shadow mode, approval queue, deferred effect, audit log.

A recommendation formed after inference at ``T`` can only take effect at
``T + delta_min`` (section 6.5), and in shadow mode it never takes effect at
all - it is recorded, counted and left for a human.
"""

from __future__ import annotations

from typing import Any

from ...core.clock import Phase
from ...core.federate import Federate, FederateHealth
from .playbooks import select_playbook

__all__ = ["ResponseFederate"]


class ResponseFederate(Federate):
    order = 80

    def __init__(self, shadow_mode: bool = True, delta_min_s: float = 1.0,
                 auto_approve: bool = False, name: str = "response") -> None:
        super().__init__(name)
        self.shadow_mode = shadow_mode
        self.delta_min_s = delta_min_s
        self.auto_approve = auto_approve
        self.pending: list[dict[str, Any]] = []
        self.audit: list[dict[str, Any]] = []
        self.applied = 0
        self.suppressed = 0

    def advance(self, t_ns: int, dt_ns: int) -> None:
        assert self.clock is not None
        t_s = t_ns / 1e9
        shared = self.context["shared"]
        detection = shared.get("detection", {})

        for site_id, row in detection.items():
            if not row.get("alert"):
                continue
            playbook = select_playbook(row.get("rule_hits", ""))
            if playbook is None:
                continue
            self.pending.append({
                "site_id": site_id,
                "playbook_id": playbook.playbook_id,
                "action": playbook.action,
                "rollback": playbook.rollback,
                "blast_radius": playbook.blast_radius,
                "confidence": round(float(row.get("score") or 0.0), 4),
                "explanation": row.get("explanation", ""),
                "proposed_at_s": t_s,
                "effective_at_s": t_s + self.delta_min_s,
                "approval_required": playbook.requires_approval and not self.auto_approve,
                "shadow_mode": self.shadow_mode,
            })

        ready = [item for item in self.pending if item["effective_at_s"] <= t_s]
        self.pending = [item for item in self.pending if item["effective_at_s"] > t_s]
        for item in ready:
            if self.shadow_mode or item["approval_required"]:
                item["outcome"] = "recorded_only"
                self.suppressed += 1
            else:
                item["outcome"] = "applied"
                self.applied += 1
                self.emit("response_applied", {"site_id": item["site_id"],
                                               "playbook": item["playbook_id"]},
                          Phase.RESPONSE)
            self.audit.append(item)

        shared["response"] = {"pending": len(self.pending), "applied": self.applied,
                              "suppressed": self.suppressed}

    def observe(self) -> dict[str, Any]:
        return {"pending": len(self.pending), "applied": self.applied,
                "suppressed": self.suppressed, "audit_records": len(self.audit)}

    def health(self) -> FederateHealth:
        if not self.shadow_mode and self.applied:
            return FederateHealth.degraded(self.name, "active response outside shadow mode")
        return FederateHealth.ok(self.name)
