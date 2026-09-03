"""Windowed feature pipeline (the ``features`` stage of section 8).

Features are computed from delivered telemetry only - never from ground truth
and never from the simulator's internal state - so that the same code can run
unchanged against real collector output in REPLAY mode.
"""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field
from statistics import fmean, pstdev
from typing import Any, Iterable

__all__ = ["FeatureWindow", "compute_features", "FEATURE_NAMES"]

FEATURE_NAMES = ("rtt_ms", "loss_pct", "throughput_mbps", "retry_pct",
                 "auth_failures", "scan_rate_pps", "flows_per_s")


@dataclass
class FeatureWindow:
    size: int = 30
    history: dict[str, deque] = field(default_factory=dict)

    def push(self, row: dict[str, Any]) -> dict[str, float]:
        output: dict[str, float] = {}
        for name in FEATURE_NAMES:
            raw = row.get(name, "")
            if raw in ("", None):
                continue
            series = self.history.setdefault(name, deque(maxlen=self.size))
            series.append(float(raw))
            output[f"{name}_mean"] = fmean(series)
            output[f"{name}_sd"] = pstdev(series) if len(series) > 1 else 0.0
            output[f"{name}_max"] = max(series)
            output[f"{name}_delta"] = series[-1] - series[0]
        return output


def compute_features(rows: Iterable[dict[str, Any]], size: int = 30) -> list[dict[str, Any]]:
    windows: dict[str, FeatureWindow] = {}
    output = []
    for row in rows:
        if row.get("telemetry_gap_marker") in (1, "1"):
            continue
        site = str(row.get("site_id"))
        window = windows.setdefault(site, FeatureWindow(size))
        features = window.push(row)
        output.append({"site_id": site, "step": row.get("step"),
                       "timestamp_utc": row.get("timestamp_utc"), **features})
    return output
