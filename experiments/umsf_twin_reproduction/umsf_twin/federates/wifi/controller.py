"""UniFi CloudKey controller surrogate.

The controller is a *visibility* element: when it is unreachable the access
points keep forwarding, but the twin loses AP-level telemetry, which is a
distinct failure mode from an AP outage and is modelled as such.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

__all__ = ["Controller"]


@dataclass
class Controller:
    controller_id: str
    site_id: str
    generation: str = "Gen2"
    reachable: bool = True
    adopted: set[str] = field(default_factory=set)
    visibility_gaps: int = 0

    def adopt(self, ap_ids: list[str]) -> None:
        self.adopted.update(ap_ids)

    def step(self, reachable: bool) -> dict[str, Any]:
        self.reachable = reachable
        if not reachable:
            self.visibility_gaps += 1
        return {
            "controller_id": self.controller_id,
            "site_id": self.site_id,
            "generation": self.generation,
            "reachable": reachable,
            "adopted_ap_count": len(self.adopted),
            "visibility_gaps": self.visibility_gaps,
            "quality_flag": "OK" if reachable else "GAP",
        }
