"""Pydantic data contracts for configs, the incident blackboard, and agent I/O.

Configuration is *always* loaded through these models so that invalid or missing
parameters fail fast and every resolved value is explicit and serialisable.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, model_validator

# --------------------------------------------------------------------------- #
# Scenario / simulation config
# --------------------------------------------------------------------------- #


class MissionPhaseConfig(BaseModel):
    name: Literal["takeoff", "transit", "loiter", "return"]
    fraction: float = Field(gt=0, le=1, description="Fraction of mission duration")


class NetworkConfig(BaseModel):
    base_packets_per_s: float = 40.0
    base_bytes_per_packet: float = 220.0
    base_rtt_ms: float = 25.0
    base_jitter_ms: float = 4.0
    base_packet_loss: float = 0.01
    routing_control_rate: float = 2.0
    neighbour_churn: float = 0.05
    fanet_radio_range_m: float = 350.0


class TelemetryConfig(BaseModel):
    gnss_satellites: int = 12
    gnss_hdop: float = 0.9
    gnss_noise_m: float = 1.5
    battery_drain_per_s: float = 0.02
    rssi_dbm_mean: float = -62.0
    sinr_db_mean: float = 18.0


class BehaviourConfig(BaseModel):
    command_rate: float = 1.5
    session_rate: float = 0.05
    auth_failure_rate: float = 0.01


class ScenarioConfig(BaseModel):
    name: str = "base"
    fleet_size: int = Field(default=20, ge=1)
    mission_duration_s: int = Field(default=600, ge=10)
    export_period_s: float = Field(default=1.0, gt=0)
    area_size_m: float = 2000.0
    phases: list[MissionPhaseConfig] = Field(
        default_factory=lambda: [
            MissionPhaseConfig(name="takeoff", fraction=0.1),
            MissionPhaseConfig(name="transit", fraction=0.3),
            MissionPhaseConfig(name="loiter", fraction=0.4),
            MissionPhaseConfig(name="return", fraction=0.2),
        ]
    )
    telemetry: TelemetryConfig = Field(default_factory=TelemetryConfig)
    network: NetworkConfig = Field(default_factory=NetworkConfig)
    behaviour: BehaviourConfig = Field(default_factory=BehaviourConfig)

    @model_validator(mode="after")
    def _phases_sum_to_one(self) -> ScenarioConfig:
        total = sum(p.fraction for p in self.phases)
        if abs(total - 1.0) > 1e-6:
            raise ValueError(f"Mission phase fractions must sum to 1.0, got {total}")
        return self


# --------------------------------------------------------------------------- #
# Attack config
# --------------------------------------------------------------------------- #


class AttackConfig(BaseModel):
    id: Literal["T1", "T2", "T3", "T4", "T5", "T6"]
    enabled: bool = True
    onset_s: float = Field(ge=0)
    duration_s: float = Field(gt=0)
    intensity: float = Field(ge=0.0, le=1.0)
    target_uavs: list[int] = Field(default_factory=list)
    profile: Literal["gradual", "sudden", "burst"] = "gradual"


# --------------------------------------------------------------------------- #
# Model / agent configs
# --------------------------------------------------------------------------- #


class ADAConfig(BaseModel):
    window_length_s: float = 2.0
    window_stride_s: float = 1.0
    hidden_sizes: list[int] = Field(default_factory=lambda: [64, 32])
    latent_dim: int = 12
    learning_rate: float = 0.001
    batch_size: int = 128
    max_epochs: int = 60
    kappa: float = 3.0  # EWMA threshold multiplier
    alpha: float = 0.05  # EWMA adaptation rate
    ewma_warmup: int = 20
    max_train_windows: int | None = None  # cap benign windows for AE training (speed)


class TCAConfig(BaseModel):
    temporal_gap_s: float = 2.0
    severity_floor: float = 0.30  # S_min / tau_e (weighted-fusion scale, Σ w_m=1)
    min_peak_severity: float = 0.75  # drop segments whose peak modality score is below this
    modality_weights: dict[str, float] = Field(
        default_factory=lambda: {"telemetry": 0.34, "network": 0.33, "behaviour": 0.33}
    )


class AAAConfig(BaseModel):
    classifier: Literal["hist_gradient_boosting", "random_forest", "mlp"] = (
        "hist_gradient_boosting"
    )
    calibration: Literal["isotonic", "sigmoid", "none"] = "isotonic"
    hierarchical: bool = True
    max_iter: int = 200
    n_estimators: int = 200
    benign_ratio: float = 3.0  # cap benign windows at ratio x attack windows (balance/speed)


class RSAConfig(BaseModel):
    lambda1: float = 0.5  # resource-cost weight
    lambda2: float = 0.7  # mission-disruption weight
    pi_min: float = 0.55  # confidence floor for autonomous action
    policy_file: str = "configs/policies/response_matrix.yaml"


class PEAConfig(BaseModel):
    max_retries: int = 1
    enforcement_latency_ms: float = 15.0


# --------------------------------------------------------------------------- #
# Dataset / experiment config
# --------------------------------------------------------------------------- #


class DatasetConfig(BaseModel):
    scenario: str = "configs/scenarios/base_20_uav.yaml"
    missions_per_class: int = 6
    seeds: list[int] = Field(default_factory=lambda: [0, 1, 2])
    train_frac: float = 0.6
    val_frac: float = 0.2
    test_frac: float = 0.2

    @model_validator(mode="after")
    def _splits_sum_to_one(self) -> DatasetConfig:
        total = self.train_frac + self.val_frac + self.test_frac
        if abs(total - 1.0) > 1e-6:
            raise ValueError(f"train/val/test fractions must sum to 1.0, got {total}")
        return self


class ExperimentConfig(BaseModel):
    name: str = "smoke"
    run_group: str = "smoke"
    scenario: str = "configs/scenarios/base_20_uav.yaml"
    attacks_dir: str = "configs/attacks"
    ada: ADAConfig = Field(default_factory=ADAConfig)
    tca: TCAConfig = Field(default_factory=TCAConfig)
    aaa: AAAConfig = Field(default_factory=AAAConfig)
    rsa: RSAConfig = Field(default_factory=RSAConfig)
    pea: PEAConfig = Field(default_factory=PEAConfig)
    dataset: DatasetConfig = Field(default_factory=DatasetConfig)
    fleet_sizes: list[int] = Field(default_factory=lambda: [5, 10, 20])
    ablations: list[str] = Field(
        default_factory=lambda: [
            "no_cross_vehicle",
            "no_fusion",
            "no_hierarchy",
            "no_safe_mask",
            "no_calibration",
        ]
    )
    sensitivity: dict[str, list[float]] = Field(default_factory=dict)
    experiments: list[str] = Field(
        default_factory=lambda: ["detection", "attribution", "response"]
    )


# --------------------------------------------------------------------------- #
# Blackboard incident record (Section 4 explanation object)
# --------------------------------------------------------------------------- #


class Incident(BaseModel):
    incident_id: str
    window_ids: list[int] = Field(default_factory=list)
    affected_entities: list[str] = Field(default_factory=list)
    modality_scores: dict[str, float] = Field(default_factory=dict)
    fused_score: float = 0.0
    predicted_attack: str | None = None
    macro_class: str | None = None
    attack_posterior: dict[str, float] = Field(default_factory=dict)
    suspected_origin: str | None = None
    origin_confidence: float = 0.0
    top_features: dict[str, list[str]] = Field(default_factory=dict)
    selected_response: str | None = None
    runner_up_response: str | None = None
    utility_terms: dict[str, dict[str, float]] = Field(default_factory=dict)
    safety_mask: list[str] = Field(default_factory=list)
    enforcement_result: dict[str, object] = Field(default_factory=dict)
    explanation: dict[str, object] = Field(default_factory=dict)
    timestamps: dict[str, float] = Field(default_factory=dict)
    ground_truth: dict[str, object] = Field(default_factory=dict)

    def to_json(self) -> str:
        return self.model_dump_json(indent=2)
