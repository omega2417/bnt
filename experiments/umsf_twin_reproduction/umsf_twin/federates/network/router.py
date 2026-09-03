"""Multi-WAN router surrogate (Keenetic Titan / Viva).

Implements the selection policies of section 9.2: strict priority failover,
session balancing and policy routing, plus failover latency, NAT-state rebuild
and the probability that live sessions survive a path change.
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field
from typing import Any

from .wan import WanLink, WanState

__all__ = ["MultiWanRouter"]


@dataclass
class MultiWanRouter:
    router_id: str
    site_id: str
    links: list[WanLink]
    policy: str = "primary_backup"          # primary_backup | balance | policy_routing
    failover_delay_s: float = 5.0
    hysteresis_s: float = 15.0
    session_survival_pct: float = 35.0
    nat_rebuild_s: float = 2.0
    active_link_id: str | None = None
    failover_until_s: float = -1.0
    preferred_available_since_s: float | None = None
    failover_count: int = 0
    dropped_sessions: int = 0
    nat_entries: int = 0

    def __post_init__(self) -> None:
        if not self.links:
            raise ValueError(f"{self.router_id}: at least one WAN link is required")
        self.links.sort(key=lambda link: link.priority)
        self.active_link_id = self.links[0].link_id

    # -- selection -------------------------------------------------------
    def usable_links(self) -> list[WanLink]:
        return [link for link in self.links if link.usable]

    def select(self, t_s: float, rng: random.Random) -> WanLink | None:
        usable = self.usable_links()
        if not usable:
            self.active_link_id = None
            return None

        if self.policy == "balance":
            chosen = max(usable, key=lambda link: link.effective_capacity)
        elif self.policy == "policy_routing":
            chosen = min(usable, key=lambda link: (link.base_rtt_ms + link.latency_add_ms))
        else:
            chosen = min(usable, key=lambda link: link.priority)

        current = self.link(self.active_link_id)
        if current is not None and current.usable and chosen.link_id != current.link_id:
            # hysteresis: only return to a better link after it has been stable
            if chosen.priority < current.priority:
                if self.preferred_available_since_s is None:
                    self.preferred_available_since_s = t_s
                if t_s - self.preferred_available_since_s < self.hysteresis_s:
                    return current
            else:
                return current
        else:
            self.preferred_available_since_s = None

        if chosen.link_id != self.active_link_id:
            self.failover_count += 1
            self.failover_until_s = t_s + self.failover_delay_s
            self.nat_entries = 0
            survivors = rng.random() * 100.0 < self.session_survival_pct
            if not survivors:
                self.dropped_sessions += 1
            self.active_link_id = chosen.link_id
            self.preferred_available_since_s = None
        return chosen

    def link(self, link_id: str | None) -> WanLink | None:
        return next((link for link in self.links if link.link_id == link_id), None)

    # -- observation -----------------------------------------------------
    def step(self, t_s: float, rng: random.Random) -> dict[str, Any]:
        active = self.select(t_s, rng)
        in_failover = t_s < self.failover_until_s
        self.nat_entries = min(4096, self.nat_entries + (64 if not in_failover else 0))
        return {
            "router_id": self.router_id,
            "active_wan_id": active.link_id if active else None,
            "wan_state": active.state if active else WanState.DOWN,
            "capacity_mbps": 0.0 if (active is None or in_failover) else active.effective_capacity,
            "base_rtt_ms": active.base_rtt_ms + active.latency_add_ms if active else 0.0,
            "failover_active": in_failover,
            "failover_count": self.failover_count,
            "dropped_sessions": self.dropped_sessions,
            "nat_entries": self.nat_entries,
            "usable_links": len(self.usable_links()),
            "total_links": len(self.links),
        }

    def reset(self) -> None:
        for link in self.links:
            link.reset()
        self.active_link_id = self.links[0].link_id
        self.failover_until_s = -1.0
        self.failover_count = self.dropped_sessions = self.nat_entries = 0
        self.preferred_available_since_s = None
