"""Response playbooks: recommendation, rollback plan and blast radius.

Nothing here executes. Each playbook produces a *proposal* with an explicit
rollback and an approval requirement, which is the only response posture the
physical range is allowed to start from.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

__all__ = ["Playbook", "PLAYBOOKS", "select_playbook"]


@dataclass(frozen=True)
class Playbook:
    playbook_id: str
    trigger: str
    action: str
    rollback: str
    blast_radius: str
    requires_approval: bool = True
    max_auto_scope: str = "none"


PLAYBOOKS: tuple[Playbook, ...] = (
    Playbook("PB-RECON", "scan_rate", "rate-limit the originating lab segment",
             "remove the rate-limit rule", "attack zone only"),
    Playbook("PB-AUTH", "auth_burst", "raise Wi-Fi auth throttling on affected APs",
             "restore the previous throttle profile", "affected SSID"),
    Playbook("PB-LATERAL", "lateral", "quarantine the involved lab assets",
             "return assets from the quarantine VLAN", "lab assets only"),
    Playbook("PB-C2", "c2_beacon", "hold the suspect flow for analyst review",
             "release the flow", "single flow"),
    Playbook("PB-ROGUE", "rogue_ap", "flag the BSSID and notify the operator",
             "clear the flag", "inventory record only"),
    Playbook("PB-PATH", "path_degraded", "re-check WAN health and prefer a stable link",
             "restore the routing policy", "site egress"),
)


def select_playbook(rule_hits: str) -> Playbook | None:
    hits = [hit for hit in str(rule_hits).split("|") if hit]
    for playbook in PLAYBOOKS:
        if playbook.trigger in hits:
            return playbook
    return None
