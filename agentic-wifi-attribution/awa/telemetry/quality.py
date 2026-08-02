"""Incident-window assembly with completeness / freshness quality scores.

Missing values are represented by a *mask*, never by zero (prompt principle 7).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List

from ..digital_twin.twin import TelemetrySample
from ..site import Site


@dataclass
class IncidentWindow:
    """Normalised evidence bundle for a single incident (prompt Module 3)."""

    incident_id: str
    site_id: str
    sample: TelemetrySample
    completeness: float                 # fraction of expected sensors present
    channel_coverage: float             # fraction of sensors reporting RSSI
    ftm_available: bool
    sensing_available: bool
    rejected: List[str] = field(default_factory=list)
    quality_components: Dict[str, float] = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "incident_id": self.incident_id,
            "site_id": self.site_id,
            "completeness": self.completeness,
            "channel_coverage": self.channel_coverage,
            "ftm_available": self.ftm_available,
            "sensing_available": self.sensing_available,
            "rejected": self.rejected,
            "quality_components": self.quality_components,
        }


def build_incident_window(
    sample: TelemetrySample, site: Site
) -> IncidentWindow:
    rssi_sensors = [s for s in site.sensors if s.supports_rssi]
    n_expected = len(rssi_sensors)
    present = [sid for sid in sample.rssi]
    rejected: List[str] = []

    # Reject values pinned at the noise floor (blinded/jammed sensors).
    floor_rejects = [sid for sid, v in sample.rssi.items() if v <= -94.9]
    rejected.extend(f"rssi:{sid}:at_noise_floor" for sid in floor_rejects)
    valid_rssi = [sid for sid in present if sid not in floor_rejects]

    completeness = len(valid_rssi) / max(n_expected, 1)
    channel_coverage = len(present) / max(n_expected, 1)
    ftm_available = len(sample.rtt_s) > 0 and not sample.missing_mask.get(
        "ftm", False
    )
    sensing_available = sample.motion_centre is not None

    quality = {
        "completeness": round(completeness, 4),
        "channel_coverage": round(channel_coverage, 4),
        "freshness": 1.0,  # ASSUMPTION: synthetic samples are always fresh
        "n_rejected": float(len(rejected)),
    }
    return IncidentWindow(
        incident_id=sample.incident_id,
        site_id=sample.site_id,
        sample=sample,
        completeness=completeness,
        channel_coverage=channel_coverage,
        ftm_available=ftm_available,
        sensing_available=sensing_available,
        rejected=rejected,
        quality_components=quality,
    )
