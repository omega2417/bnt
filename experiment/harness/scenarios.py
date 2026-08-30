"""Scenario injectors S1-S4, their action-effect models, and independent ground truth.

Effect sizes are expressed in units of the affected node's own baseline standard
deviation and are frozen in protocol/preregistration.yaml after the calibration
pilot (see docs/EXPERIMENT_REPORT.md, deviation D-01) and before any confirmatory
run. The injector writes the ground truth; no detector output is ever consulted
when labelling.
"""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

from .environment import P

__all__ = ["ScenarioSpec", "SCENARIOS", "ACTION_MODELS", "ActionModel",
           "apply_injection", "Injection"]


@dataclass(frozen=True)
class ScenarioSpec:
    code: str
    name: str
    target_kind: str
    shift_sd: tuple[float, ...] = field(default=tuple([0.0] * P))
    ramp_s: float = 10.0
    tamper_fraction: float = 0.0     # S2 only: share of messages replaced/replayed
    placement_event: bool = False    # S4 only
    trust_evidence: tuple[float, float, float] = (0.90, 0.90, 0.90)  # (c, q, b) under attack


SCENARIOS: dict[str, ScenarioSpec] = {
    # S1 - compromised edge node. Resource and sequencing signature; the traffic
    # signature stays inside normal variation, so a traffic-only detector is at a
    # genuine (not manufactured) disadvantage. Intensity calibrated on the pilot so
    # that the p=9 Mahalanobis statistic crosses its chi^2_9 threshold part-way up
    # the ramp rather than instantly or never.
    "S1": ScenarioSpec("S1", "Compromised edge node / loss of trust", "edge",
                       shift_sd=(0.70, 0.58, 0.46, 4.60, 3.45, 2.76, 0.92, 4.14, 1.38),
                       ramp_s=60.0, trust_evidence=(0.88, 0.42, 0.35)),
    # S2 - telemetry integrity violation. Replayed records are drawn from the node's
    # own baseline window, so they are statistically indistinguishable by
    # construction; only integrity + provenance evidence can expose them.
    "S2": ScenarioSpec("S2", "Telemetry integrity violation (inject/replace/replay)", "sensor",
                       shift_sd=(0.0,) * 6 + (0.15, 0.60, 0.0), ramp_s=10.0,
                       tamper_fraction=0.05, trust_evidence=(0.45, 0.38, 0.82)),
    # S3 - rate-limited volumetric disruption. Strong traffic signature visible to
    # both detector families; the arms must differ in response, not in detection.
    "S3": ScenarioSpec("S3", "Controlled network load / DoS on a sandbox service", "edge",
                       shift_sd=(6.00, 5.50, 7.00, 1.20, 0.90, 1.60, 1.10, 0.50, 4.00),
                       ramp_s=10.0, trust_evidence=(0.86, 0.80, 0.40)),
    # S4 - policy-violating placement. No telemetry signature at all: detection is a
    # decision-correctness property of the admissibility check of Eq. (13).
    "S4": ScenarioSpec("S4", "Placement-policy violation", "edge",
                       placement_event=True, trust_evidence=(0.90, 0.72, 0.60)),
}


# ---------------------------------------------------------------------------
# Action-effect model.
#
# Each protective action is described by (a) a multiplicative effect on the local
# risk of the compromised asset, (b) a collateral risk ADDED to the assets that
# depend on it, and (c) a multiplier applied to the dependency weights leaving the
# asset. The models are arm-independent: they belong to the environment, not to a
# configuration. No "correct action" is declared anywhere - the ground-truth best
# action is DERIVED per run as the argmin of the realised propagated risk.
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class ActionModel:
    name: str
    local_factor: dict           # scenario code -> multiplier on R[target]
    collateral: float            # risk added to each direct dependent
    edge_factor: float           # multiplier on outgoing dependency weights
    overhead: tuple              # (cpu, ram, net) normalised overhead
    disruption: float
    is_placement: bool = False


ACTION_MODELS = {
    # cuts the asset out completely, but starves everything that depends on it
    "isolate_target": ActionModel(
        "isolate_target", {"S1": 0.05, "S2": 0.05, "S3": 0.05, "S4": 0.05},
        collateral=0.22, edge_factor=0.0, overhead=(0.05, 0.03, 0.18), disruption=0.10),
    # blocks propagation by rehoming dependents, leaves the compromised asset dirty
    "migrate_dependent": ActionModel(
        "migrate_dependent", {"S1": 0.90, "S2": 0.90, "S3": 0.85, "S4": 0.90},
        collateral=0.0, edge_factor=0.20, overhead=(0.30, 0.35, 0.42), disruption=0.16,
        is_placement=True),
    # throttles the flood; ineffective against identity or integrity compromise
    "rate_limit": ActionModel(
        "rate_limit", {"S1": 0.85, "S2": 0.95, "S3": 0.18, "S4": 0.95},
        collateral=0.03, edge_factor=1.0, overhead=(0.08, 0.04, 0.10), disruption=0.05),
    # restores validated state; the only action that repairs a data-integrity fault
    "restore_validated_replica": ActionModel(
        "restore_validated_replica", {"S1": 0.70, "S2": 0.10, "S3": 0.88, "S4": 0.85},
        collateral=0.04, edge_factor=1.0, overhead=(0.22, 0.28, 0.15), disruption=0.12),
    # revokes the abused identity; the targeted answer to an edge compromise
    "revoke_identity": ActionModel(
        "revoke_identity", {"S1": 0.12, "S2": 0.60, "S3": 0.92, "S4": 0.55},
        collateral=0.02, edge_factor=1.0, overhead=(0.04, 0.03, 0.05), disruption=0.03),
    # Denies the inadmissible placement and reschedules onto an already-validated
    # node. is_placement is False on purpose: this action is the remediation of the
    # request, so it must not itself be tested against the very workload whose
    # admissibility failed - doing so removes the only correct answer to S4 from the
    # feasible set of exactly those arms that implement the constraint.
    "deny_and_reschedule": ActionModel(
        "deny_and_reschedule", {"S1": 0.88, "S2": 0.92, "S3": 0.95, "S4": 0.15},
        collateral=0.0, edge_factor=1.0, overhead=(0.12, 0.14, 0.20), disruption=0.08,
        is_placement=False),
}


@dataclass
class Injection:
    stream: np.ndarray
    anomaly_mask: np.ndarray    # samples whose distribution was actually perturbed
    tamper_mask: np.ndarray     # records replaced/replayed - integrity ground truth


def apply_injection(stream, sd, spec, t, t_attack, rng) -> Injection:
    """Perturb one node's stream and return the two independent ground-truth masks."""
    out = stream.copy()
    active = t >= t_attack
    tamper = np.zeros_like(active)
    if (not active.any()) or spec.placement_event:
        return Injection(out, np.zeros_like(active), tamper)

    intensity = np.zeros_like(t)
    if spec.ramp_s > 0:
        intensity[active] = np.clip((t[active] - t_attack) / spec.ramp_s, 0.0, 1.0)
    else:
        intensity[active] = 1.0

    shift = np.asarray(spec.shift_sd, dtype=float) * sd
    out += intensity[:, None] * shift[None, :]

    if spec.tamper_fraction > 0:
        pre = np.where(~active)[0]
        post = np.where(active)[0]
        k = int(round(spec.tamper_fraction * post.size))
        if k > 0 and pre.size > 0:
            chosen = rng.choice(post, size=k, replace=False)
            src = rng.choice(pre, size=k, replace=True)
            out[chosen] = stream[src] + intensity[chosen, None] * shift[None, :]
            tamper[chosen] = True
    return Injection(out, active.copy(), tamper)
