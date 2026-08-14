"""Threat Correlation Agent (TCA).

Aggregates flagged windows across modalities, time and vehicles into incidents by
temporal-interval merging + topology-aware connected components, and computes the
fused severity S(E) = Σ_m w_m · s̄_m(E) (Eq. 4).
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from ..schemas import TCAConfig
from .base import BaseAgent

__all__ = ["CorrelatedIncident", "ThreatCorrelationAgent"]

_MOD_KEY = {"telemetry": "tel", "network": "net", "behaviour": "beh"}


@dataclass
class CorrelatedIncident:
    run_id: str
    row_indices: list[int]
    affected_entities: list[str]
    window_start_min: float
    window_start_max: float
    modality_scores: dict[str, float] = field(default_factory=dict)
    fused_score: float = 0.0


class _UnionFind:
    def __init__(self, n: int) -> None:
        self.parent = list(range(n))

    def find(self, a: int) -> int:
        while self.parent[a] != a:
            self.parent[a] = self.parent[self.parent[a]]
            a = self.parent[a]
        return a

    def union(self, a: int, b: int) -> None:
        self.parent[self.find(a)] = self.find(b)


class ThreatCorrelationAgent(BaseAgent):
    name = "tca"

    def __init__(self, config: TCAConfig, seed: int = 0, deterministic: bool = True) -> None:
        super().__init__(config, seed, deterministic)

    def correlate(
        self, detection: pd.DataFrame, use_fusion: bool = True
    ) -> list[CorrelatedIncident]:
        cfg: TCAConfig = self.config
        gap = cfg.temporal_gap_s
        weights = cfg.modality_weights
        flagged = detection[detection["any_flag"]].copy()
        flagged["_peak"] = flagged[["tel_score", "net_score", "beh_score"]].max(axis=1)
        incidents: list[CorrelatedIncident] = []

        for run_id, run_rows in flagged.groupby("run_id"):
            segments = self._temporal_segments(run_rows, gap)
            # Drop marginal (benign false-positive) segments whose peak modality
            # severity never rises above the configured floor.
            segments = [s for s in segments if s["peak"] >= cfg.min_peak_severity]
            if not segments:
                continue
            # Merge segments overlapping in time (topology-aware: same run/FANET).
            uf = _UnionFind(len(segments))
            for i in range(len(segments)):
                for j in range(i + 1, len(segments)):
                    if self._overlap(segments[i], segments[j], gap):
                        uf.union(i, j)
            groups: dict[int, list[int]] = {}
            for i in range(len(segments)):
                groups.setdefault(uf.find(i), []).append(i)

            for members in groups.values():
                rows_idx: list[int] = []
                entities: set[str] = set()
                tmin, tmax = np.inf, -np.inf
                for si in members:
                    seg = segments[si]
                    rows_idx.extend(seg["rows"])
                    entities.add(seg["uav"])
                    tmin = min(tmin, seg["start"])
                    tmax = max(tmax, seg["end"])
                sub = detection.loc[rows_idx]
                mod_scores = {
                    m: float(sub[f"{_MOD_KEY[m]}_score"].mean()) for m in weights
                }
                if use_fusion:
                    fused = float(sum(weights[m] * mod_scores[m] for m in weights))
                else:  # ablation: single best modality
                    fused = float(max(mod_scores.values()))
                inc = CorrelatedIncident(
                    run_id=str(run_id),
                    row_indices=rows_idx,
                    affected_entities=sorted(entities),
                    window_start_min=float(tmin),
                    window_start_max=float(tmax),
                    modality_scores=mod_scores,
                    fused_score=fused,
                )
                if fused >= cfg.severity_floor:
                    incidents.append(inc)
        incidents.sort(key=lambda x: (x.run_id, x.window_start_min))
        return incidents

    @staticmethod
    def _temporal_segments(run_rows: pd.DataFrame, gap: float) -> list[dict]:
        segments: list[dict] = []
        for uav, urows in run_rows.groupby("uav_index"):
            urows = urows.sort_values("window_start")
            starts = urows["window_start"].to_numpy()
            idx = urows.index.to_numpy()
            peaks = urows["_peak"].to_numpy()
            if len(starts) == 0:
                continue

            def _new(k: int, uav=uav, idx=idx, starts=starts, peaks=peaks) -> dict:
                return {"uav": f"uav_{int(uav):02d}", "rows": [int(idx[k])],
                        "start": float(starts[k]), "end": float(starts[k]),
                        "peak": float(peaks[k])}

            cur = _new(0)
            for k in range(1, len(starts)):
                if starts[k] - cur["end"] <= gap:
                    cur["rows"].append(int(idx[k]))
                    cur["end"] = float(starts[k])
                    cur["peak"] = max(cur["peak"], float(peaks[k]))
                else:
                    segments.append(cur)
                    cur = _new(k)
            segments.append(cur)
        return segments

    @staticmethod
    def _overlap(a: dict, b: dict, gap: float) -> bool:
        return not (a["end"] + gap < b["start"] or b["end"] + gap < a["start"])
