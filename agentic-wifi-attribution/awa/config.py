"""Configuration dataclasses and physical constants.

All numeric defaults are *illustrative* and calibrated only against the
synthetic environment shipped with this package.  They must be re-estimated
against a controlled offline survey before any real deployment.  Assumptions
are flagged inline with ``# ASSUMPTION``.
"""

from __future__ import annotations

from dataclasses import dataclass, field, asdict
from typing import Tuple

# Speed of light (m/s) -- used to convert FTM round-trip time to range.
SPEED_OF_LIGHT = 299_792_458.0


@dataclass(frozen=True)
class GridConfig:
    """Regular 2-D inference grid over a single floor (metres)."""

    x_min: float = 0.0
    x_max: float = 40.0
    y_min: float = 0.0
    y_max: float = 25.0
    resolution: float = 0.5  # cell size in metres

    def shape(self) -> Tuple[int, int]:
        nx = int(round((self.x_max - self.x_min) / self.resolution))
        ny = int(round((self.y_max - self.y_min) / self.resolution))
        return ny, nx  # rows, cols  (y, x)

    @property
    def cell_area(self) -> float:
        return self.resolution * self.resolution


@dataclass(frozen=True)
class PathLossConfig:
    """Log-distance path-loss model  RSSI(d) = P0 - 10 n log10(d/d0) + X.

    ASSUMPTION: single-slope log-distance model with log-normal shadowing is
    adequate for the synthetic indoor scene.  Real sites need multi-wall /
    multi-slope calibration (Module 4 of the prompt).
    """

    p0_dbm: float = -40.0     # reference RSSI at d0
    d0_m: float = 1.0         # reference distance
    path_loss_exp: float = 2.8  # n -- typical indoor 2.7..3.5
    shadow_sigma_db: float = 4.0  # log-normal shadowing std (dB)
    min_rssi_dbm: float = -95.0   # receiver sensitivity floor


@dataclass(frozen=True)
class RssiLikelihoodConfig:
    sigma_db: float = 4.0          # measurement std at the fingerprint cell
    student_t_dof: float = 4.0     # robustness: heavy tails absorb outliers
    use_student_t: bool = True     # robust likelihood by default
    contamination_eps: float = 0.02  # baseline outlier mass


@dataclass(frozen=True)
class FtmLikelihoodConfig:
    """FTM/RTT pseudo-range likelihood with LOS/NLOS mixture."""

    sigma_los_m: float = 1.0       # LOS ranging std
    sigma_nlos_m: float = 4.0      # NLOS ranging std
    nlos_bias_m: float = 3.0       # NLOS adds *positive* range bias
    nlos_prob: float = 0.25        # prior probability a burst is NLOS
    max_range_m: float = 60.0      # physically impossible beyond this


@dataclass(frozen=True)
class SensingConfig:
    """IEEE 802.11bf WLAN-sensing context likelihood parameters.

    Sensing is used as a *context* modality (motion / presence / scene
    change), never as unconditional identity evidence (prompt Module 6).
    """

    motion_weight: float = 0.5     # how strongly motion reshapes the prior
    provenance_floor: float = 0.3  # below this provenance, sensing is muted


@dataclass(frozen=True)
class FusionConfig:
    hpd_mass: float = 0.95         # target credible mass of the HPD region
    multimodality_rel_threshold: float = 0.5  # local-max cutoff vs global max
    # Cross-modal consistency (prompt Module 9, ConsistencyAgent).  Location
    # agreement (HPD overlap + MAP Mahalanobis) is the primary signal; JS
    # divergence is reported but not decisive because it conflates a genuine
    # location disagreement with a mere difference in posterior sharpness.
    consistency_overlap_uncertain: float = 0.30  # overlap < -> at least UNCERTAIN
    consistency_overlap_conflict: float = 0.05   # overlap < -> CONFLICT
    consistency_mahalanobis_uncertain: float = 2.5
    consistency_mahalanobis_conflict: float = 4.0


@dataclass
class PlatformConfig:
    """Top-level bundle of all configuration blocks (versioned)."""

    grid: GridConfig = field(default_factory=GridConfig)
    path_loss: PathLossConfig = field(default_factory=PathLossConfig)
    rssi: RssiLikelihoodConfig = field(default_factory=RssiLikelihoodConfig)
    ftm: FtmLikelihoodConfig = field(default_factory=FtmLikelihoodConfig)
    sensing: SensingConfig = field(default_factory=SensingConfig)
    fusion: FusionConfig = field(default_factory=FusionConfig)

    # Versioned artefact identifiers embedded into every SAR (prompt M12).
    data_schema_version: str = "sar-1.0.0"
    model_version: str = "awa-core-0.1.0"
    calibration_version: str = "synthetic-cal-0.1.0"
    policy_version: str = "policy-demo-0.1.0"

    def to_dict(self) -> dict:
        return asdict(self)
