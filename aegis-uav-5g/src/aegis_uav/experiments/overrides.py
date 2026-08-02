"""Experiment overrides (ablation switches + parameter sweeps) and per-mission
attack instantiation with controlled variation."""

from __future__ import annotations

from dataclasses import dataclass

from ..schemas import AttackConfig, ScenarioConfig

__all__ = ["Overrides", "make_attack"]


@dataclass
class Overrides:
    # Ablation switches
    no_cross_vehicle: bool = False
    no_fusion: bool = False
    no_hierarchy: bool = False
    no_safe_mask: bool = False
    no_calibration: bool = False
    no_counterfactual_origin: bool = False
    # Parameter sweeps (None = use config default)
    kappa: float | None = None
    alpha: float | None = None
    window_length_s: float | None = None
    severity_floor: float | None = None
    lambda1: float | None = None
    lambda2: float | None = None
    pi_min: float | None = None

    @classmethod
    def for_ablation(cls, name: str) -> Overrides:
        mapping = {
            "no_cross_vehicle": dict(no_cross_vehicle=True),
            "no_fusion": dict(no_fusion=True),
            "no_hierarchy": dict(no_hierarchy=True),
            "no_safe_mask": dict(no_safe_mask=True),
            "no_calibration": dict(no_calibration=True),
            "no_counterfactual_origin": dict(no_counterfactual_origin=True),
        }
        return cls(**mapping.get(name, {}))


# Base attack templates (onset/duration/intensity/profile) per class.
_TEMPLATES: dict[str, dict] = {
    "T1": dict(onset_s=40, duration_s=45, intensity=0.5, profile="gradual"),
    "T2": dict(onset_s=45, duration_s=40, intensity=0.6, profile="sudden"),
    "T3": dict(onset_s=50, duration_s=40, intensity=0.7, profile="burst"),
    "T4": dict(onset_s=45, duration_s=45, intensity=0.6, profile="gradual"),
    "T5": dict(onset_s=50, duration_s=40, intensity=0.55, profile="gradual"),
    "T6": dict(onset_s=45, duration_s=45, intensity=0.6, profile="sudden"),
}


def make_attack(attack_id: str, scenario: ScenarioConfig, variant: int) -> AttackConfig:
    """Instantiate an attack config with per-mission target/onset variation.

    The variation keeps every mission distinct (different origin UAV, jittered
    onset/intensity) while staying reproducible from ``variant``.
    """
    tpl = dict(_TEMPLATES[attack_id])
    n = scenario.fleet_size
    onset = float(tpl["onset_s"] + (variant % 5) * 3.0)
    intensity = float(min(1.0, max(0.2, tpl["intensity"] + ((variant % 3) - 1) * 0.05)))
    if attack_id == "T6":  # compromised GCS controls several UAVs
        targets = sorted({variant % n, (variant + 1) % n, (variant + 2) % n})
    else:
        targets = [variant % n]
    return AttackConfig(
        id=attack_id,
        enabled=True,
        onset_s=onset,
        duration_s=float(tpl["duration_s"]),
        intensity=intensity,
        target_uavs=targets,
        profile=tpl["profile"],
    )
