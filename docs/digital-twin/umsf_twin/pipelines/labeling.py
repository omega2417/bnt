"""Interval labeling: joins telemetry rows to ground-truth intervals.

Labels come from the ``injected`` truth records only. Transition truth is kept
separate on purpose: using it as a label would credit a detector for seeing a
consequence of the injection rather than the injection itself.
"""

from __future__ import annotations

from typing import Any, Iterable

__all__ = ["label_rows", "ATTACK_STAGES"]

#: Truth stages that count as an adversarial condition for detection metrics.
ATTACK_STAGES = frozenset({"recon_burst", "lateral_sequence", "low_rate_c2",
                           "wifi_auth_burst", "rogue_ap_signal"})


def label_rows(rows: Iterable[dict[str, Any]], truth: Iterable[dict[str, Any]],
               stages: frozenset[str] = ATTACK_STAGES) -> list[dict[str, Any]]:
    intervals = [t for t in truth if t.get("kind") == "injected"
                 and t.get("stage") in stages]
    labeled = []
    for row in rows:
        step = int(row.get("step", 0))
        site = str(row.get("site_id"))
        matches = [t for t in intervals
                   if str(t["site_id"]) == site
                   and int(t["onset_step"]) <= step < int(t["end_step"])]
        labeled.append({
            **row,
            "label_attack": int(bool(matches)),
            "label_stage": "|".join(sorted({t["stage"] for t in matches})),
            "label_truth_ids": "|".join(sorted(t["truth_id"] for t in matches)),
        })
    return labeled
