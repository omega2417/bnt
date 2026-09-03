"""Asset-level load shedding for groups I, II and III (section 9.9).

The MVP of the source document used a single scalar factor. Here the groups
are real: group III is dropped first, then II, and group I is preserved until
the safety limit, with an explicit hysteresis so a recovering SoC does not
cause repeated shedding.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

__all__ = ["LoadManager", "GROUP_ORDER"]

#: Shedding order: auxiliary first, critical never (until the safety limit).
GROUP_ORDER = (3, 2)


@dataclass
class LoadManager:
    warn_soc_pct: float = 30.0
    shed_soc_pct: float = 20.0
    shed_group2_soc_pct: float = 12.0
    restore_hysteresis_pct: float = 5.0
    #: Consecutive overcurrent-free steps required before an auxiliary group
    #: is restored. Without it the controller chatters: restoring the group
    #: immediately recreates the overcurrent that shed it.
    restore_after_clear_steps: int = 15
    warn_autonomy_min: float = 30.0
    critical_autonomy_min: float = 15.0
    shed_groups: set[int] = field(default_factory=set)
    shed_events: int = 0
    restore_events: int = 0
    overcurrent_steps: int = 0
    clear_steps: int = 0

    def update(self, soc_pct: float, autonomy_min: float, on_battery: bool,
               overcurrent: bool = False) -> dict[str, Any]:
        """Decide which groups stay powered.

        Three independent triggers shed load: state of charge, forecast
        autonomy and - added here because the source MVP had no notion of it -
        a discharge current above the BMS limit. Group I is never shed by this
        logic; only the safety limit may remove it.
        """

        previous = set(self.shed_groups)

        if not on_battery and soc_pct > self.shed_soc_pct + self.restore_hysteresis_pct:
            self.shed_groups.clear()
        else:
            if (soc_pct <= self.shed_soc_pct
                    or autonomy_min <= self.critical_autonomy_min or overcurrent):
                self.shed_groups.add(3)
            if soc_pct <= self.shed_group2_soc_pct or (overcurrent and 3 in self.shed_groups
                                                       and self.overcurrent_steps > 5):
                self.shed_groups.add(2)
            if overcurrent:
                self.overcurrent_steps += 1
                self.clear_steps = 0
            else:
                self.overcurrent_steps = 0
                self.clear_steps += 1
            if (soc_pct > self.shed_soc_pct + self.restore_hysteresis_pct
                    and not overcurrent
                    and self.clear_steps >= self.restore_after_clear_steps):
                self.shed_groups.discard(3)
            if soc_pct > self.shed_group2_soc_pct + self.restore_hysteresis_pct:
                self.shed_groups.discard(2)

        if self.shed_groups - previous:
            self.shed_events += 1
        if previous - self.shed_groups:
            self.restore_events += 1

        return {
            "shed_groups": sorted(self.shed_groups),
            "shed_events": self.shed_events,
            "restore_events": self.restore_events,
            "warning_soc": soc_pct <= self.warn_soc_pct,
            "warning_autonomy": autonomy_min <= self.warn_autonomy_min,
            "critical_autonomy": autonomy_min <= self.critical_autonomy_min,
            "group1_preserved": 1 not in self.shed_groups,
            "shed_reason_overcurrent": overcurrent,
            "overcurrent_clear_steps": self.clear_steps,
        }

    def retained_load_w(self, group_loads_w: dict[int, float]) -> float:
        return sum(watts for group, watts in group_loads_w.items()
                   if group not in self.shed_groups)
