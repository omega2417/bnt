"""Digital twin: forward radio model + synthetic telemetry + attack injection.

The twin is the *ground-truth* generator used for reproducible experiments.
It simulates RSSI, FTM/RTT and WLAN-sensing observations from a known source
location, and can inject the adversarial / degradation scenarios listed in
prompt Module 15 (rogue AP, relay, drift, missing modality, jamming, ...).

Comparing the twin's prediction against measured telemetry gives the
*digital-twin residual* used as a threat/domain-shift cue (prompt Module 7).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional

import numpy as np

from ..config import PathLossConfig, SPEED_OF_LIGHT
from ..localization.radiomap import log_distance_rssi
from ..site import Site


class Scenario(str, Enum):
    CLEAN_LOS = "clean_los"
    CLEAN_NLOS = "clean_nlos"
    TEMPORAL_DRIFT = "temporal_drift"
    MISSING_FTM = "missing_ftm"
    ROGUE_AP = "rogue_ap"
    RELAY = "relay"
    SELECTIVE_JAMMING = "selective_jamming"
    RSSI_POWER_MANIPULATION = "rssi_power_manipulation"


@dataclass
class TelemetrySample:
    """One incident-window observation bundle (prompt Module 3)."""

    incident_id: str
    site_id: str
    true_xy: List[float]                       # ground truth (synthetic only)
    rssi: Dict[str, float] = field(default_factory=dict)     # sid -> dBm
    rtt_s: Dict[str, float] = field(default_factory=dict)    # aid -> seconds
    motion_centre: Optional[List[float]] = None
    motion_radius_m: float = 4.0
    missing_mask: Dict[str, bool] = field(default_factory=dict)
    scenario: str = Scenario.CLEAN_LOS.value
    notes: List[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "incident_id": self.incident_id,
            "site_id": self.site_id,
            "true_xy": self.true_xy,
            "rssi": self.rssi,
            "rtt_s": self.rtt_s,
            "motion_centre": self.motion_centre,
            "motion_radius_m": self.motion_radius_m,
            "missing_mask": self.missing_mask,
            "scenario": self.scenario,
            "notes": self.notes,
        }


class DigitalTwin:
    def __init__(
        self,
        site: Site,
        path_loss: PathLossConfig,
        seed: int = 0,
        drift_bias_db: Optional[np.ndarray] = None,
    ):
        self.site = site
        self.pl = path_loss
        self.rng = np.random.default_rng(seed)
        self.drift_bias_db = drift_bias_db

    # -- forward models ---------------------------------------------------- #
    def predict_rssi(self, source: np.ndarray) -> Dict[str, float]:
        out = {}
        for i, s in enumerate(self.site.sensors):
            if not s.supports_rssi:
                continue
            d = float(np.hypot(source[0] - s.x, source[1] - s.y))
            mean = float(log_distance_rssi(np.array([d]), self.pl)[0])
            if self.drift_bias_db is not None:
                mean += float(self.drift_bias_db[i])
            out[s.sensor_id] = mean
        return out

    # -- sampling ---------------------------------------------------------- #
    def sample(
        self,
        source: np.ndarray,
        incident_id: str,
        scenario: Scenario = Scenario.CLEAN_LOS,
        rssi_noise_db: float = 3.0,
        seed: Optional[int] = None,
    ) -> TelemetrySample:
        # Reseeding per incident makes a sample reproducible regardless of the
        # order in which incidents are drawn from a shared twin.
        if seed is not None:
            self.rng = np.random.default_rng(seed)
        src = np.asarray(source, float)
        rssi: Dict[str, float] = {}
        rtt: Dict[str, float] = {}
        notes: List[str] = []
        missing: Dict[str, bool] = {}

        nlos = scenario in (Scenario.CLEAN_NLOS,)

        for i, s in enumerate(self.site.sensors):
            d = float(np.hypot(src[0] - s.x, src[1] - s.y))
            if s.supports_rssi:
                mean = float(log_distance_rssi(np.array([d]), self.pl)[0])
                if self.drift_bias_db is not None:
                    mean += float(self.drift_bias_db[i])
                rssi[s.sensor_id] = mean + self.rng.normal(0, rssi_noise_db)
            if s.supports_ftm and scenario is not Scenario.MISSING_FTM:
                extra = 0.0
                sigma = 1.0
                if nlos:
                    extra = abs(self.rng.normal(3.0, 1.0))  # positive NLOS bias
                    sigma = 3.0
                d_meas = max(d + extra + self.rng.normal(0, sigma), 0.1)
                rtt[s.sensor_id] = 2.0 * d_meas / SPEED_OF_LIGHT

        # -- scenario-specific perturbations ------------------------------ #
        if scenario is Scenario.TEMPORAL_DRIFT:
            # Radiomap ageing: a slowly-varying per-sensor offset that the
            # baseline map does not know about.  DriftAgent should flag it,
            # and the GovernanceAgent must NOT auto-rewrite the baseline.
            for k, sid in enumerate(list(rssi)):
                rssi[sid] += 6.0 + 4.0 * np.sin(0.7 * k + 1.0)  # ~2..10 dB
            notes.append("Injected temporal radiomap drift (~+6 dB ageing)")

        if scenario is Scenario.MISSING_FTM:
            missing["ftm"] = True
            notes.append("FTM modality unavailable this window")

        if scenario is Scenario.ROGUE_AP:
            # An unexpected strong emitter in the public/controlled area
            # inflates the sensors near it.  Because it is displaced from the
            # true source, sensors near the rogue read far stronger than the
            # baseline radiomap predicts for the true location -> a large
            # digital-twin residual that the ThreatAssessmentAgent can flag.
            rogue = np.array([10.0, 20.0])
            for s in self.site.sensors:
                if not s.supports_rssi:
                    continue
                dr = float(np.hypot(rogue[0] - s.x, rogue[1] - s.y))
                boost = float(log_distance_rssi(np.array([dr]), self.pl)[0])
                rssi[s.sensor_id] = max(rssi[s.sensor_id], boost + 8.0)
            notes.append("Injected rogue AP at (10,20), +8 dB over baseline")

        if scenario is Scenario.RELAY:
            # Relay/delay adds a consistent positive delay to all FTM anchors.
            for aid in list(rtt):
                rtt[aid] += 30e-9  # ~30 ns => ~4.5 m extra one-way
            notes.append("Injected relay/delay attack (+30 ns on all anchors)")

        if scenario is Scenario.SELECTIVE_JAMMING:
            victims = [s.sensor_id for s in self.site.sensors
                       if s.supports_rssi][:2]
            for sid in victims:
                rssi[sid] = self.pl.min_rssi_dbm  # sensor blinded
                missing[f"rssi:{sid}"] = True
            notes.append(f"Selective jamming of sensors {victims}")

        if scenario is Scenario.RSSI_POWER_MANIPULATION:
            for sid in rssi:
                rssi[sid] += 8.0  # attacker raises apparent Tx power
            notes.append("Global +8 dB RSSI power manipulation")

        motion = src.tolist()
        return TelemetrySample(
            incident_id=incident_id,
            site_id=self.site.site_id,
            true_xy=src.tolist(),
            rssi=rssi,
            rtt_s=rtt,
            motion_centre=motion,
            motion_radius_m=4.0,
            missing_mask=missing,
            scenario=scenario.value,
            notes=notes,
        )

    def twin_residual(self, sample: TelemetrySample) -> float:
        """RMS residual (dB) between measured RSSI and twin prediction at the
        sample's reported motion centre.  Large residual => domain shift /
        possible manipulation (prompt Module 7)."""
        if sample.motion_centre is None or not sample.rssi:
            return 0.0
        pred = self.predict_rssi(np.asarray(sample.motion_centre, float))
        diffs = [sample.rssi[sid] - pred[sid]
                 for sid in sample.rssi if sid in pred]
        if not diffs:
            return 0.0
        return float(np.sqrt(np.mean(np.square(diffs))))
