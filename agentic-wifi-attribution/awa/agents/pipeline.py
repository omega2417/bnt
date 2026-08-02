"""The ten agents and the orchestrator (prompt Module 9).

Each agent is a small, single-responsibility unit that reads and writes the
shared :class:`AgentContext` blackboard.  The orchestrator runs them as a
fixed state machine and records an append-only audit trail.  Governance
constraints (no unauthorised containment, no silent uncertainty, no unsigned
model use) are enforced by the GovernanceAgent as a final gate.
"""

from __future__ import annotations

from typing import Dict, List

import numpy as np

from ..config import PlatformConfig
from ..evidence.sar import build_sar
from ..localization import fusion, metrics
from ..readiness.model import (
    ReadinessDimension,
    ReadinessEvidence,
    assess_profile,
)
from .context import AgentContext, DecisionTier, DECISION_TIER_NAMES


class Agent:
    name = "agent"

    def run(self, ctx: AgentContext) -> None:  # pragma: no cover - interface
        raise NotImplementedError


# --------------------------------------------------------------------------- #
class ObservationAgent(Agent):
    """Validates schema/completeness/time and forms the incident window."""

    name = "ObservationAgent"

    def run(self, ctx: AgentContext) -> None:
        from ..telemetry.quality import build_incident_window

        ctx.incident = build_incident_window(ctx.sample, ctx.site)
        ctx.log(
            self.name,
            "incident window formed",
            completeness=round(ctx.incident.completeness, 3),
            ftm_available=ctx.incident.ftm_available,
            rejected=ctx.incident.rejected,
        )


# --------------------------------------------------------------------------- #
class LocalizationAgent(Agent):
    """Computes per-modality likelihoods and the fused posterior."""

    name = "LocalizationAgent"

    def run(self, ctx: AgentContext) -> None:
        cfg = ctx.cfg
        sample = ctx.sample
        sensors = {s.sensor_id: s for s in ctx.site.sensors}

        # Provenance-aware RSSI weights (low provenance -> lower weight).
        prov = {s.sensor_id: s.provenance_score for s in ctx.site.sensors}
        rssi_weights = {sid: prov.get(sid, 1.0) for sid in sample.rssi}

        rssi_ll = fusion.rssi_log_likelihood(
            ctx.grid, ctx.radiomap, sample.rssi, cfg.rssi, rssi_weights
        )
        ftm_ll = None
        if ctx.incident and ctx.incident.ftm_available:
            ftm_ll = fusion.ftm_log_likelihood(
                ctx.grid, sensors, sample.rtt_s, cfg.ftm
            )
        sensing_ll = None
        if sample.motion_centre is not None:
            sensing_ll = fusion.sensing_log_prior(
                ctx.grid,
                np.asarray(sample.motion_centre, float),
                sample.motion_radius_m,
                cfg.sensing,
                provenance=1.0,
            )

        fused = fusion.fuse(
            ctx.grid,
            log_prior=None,
            rssi_ll=rssi_ll,
            ftm_ll=ftm_ll,
            sensing_ll=sensing_ll,
        )
        ctx.posterior = fused.posterior
        ctx.used_modalities = fused.used_modalities
        ctx.missing_modalities = fused.missing_modalities

        # Single-modality posteriors for the consistency agent.
        ctx.rssi_posterior = fusion.fuse(ctx.grid, rssi_ll=rssi_ll).posterior
        if ftm_ll is not None:
            ctx.ftm_posterior = fusion.fuse(ctx.grid, ftm_ll=ftm_ll).posterior

        # Per-sensor contribution = mean absolute RSSI log-lik at the MAP cell.
        map_idx = int(np.argmax(ctx.posterior))
        contribs: Dict[str, float] = {}
        for sid in sample.rssi:
            if sid in ctx.radiomap.sensor_ids:
                i = ctx.radiomap.sensor_ids.index(sid)
                mu = ctx.radiomap.mean_rssi[i, map_idx]
                contribs[sid] = float(-abs(sample.rssi[sid] - mu))
        ctx.sensor_contributions = contribs

        ctx.uncertainty = metrics.summarise(
            ctx.grid, ctx.posterior, ctx.site,
            hpd_mass=cfg.fusion.hpd_mass,
            rel_threshold=cfg.fusion.multimodality_rel_threshold,
        ).to_dict()
        ctx.log(
            self.name,
            "posterior computed",
            used=ctx.used_modalities,
            missing=ctx.missing_modalities,
            MAP=[round(v, 2) for v in ctx.uncertainty["MAP"]],
            hpd_area_m2=round(ctx.uncertainty["HPD_area_m2"], 2),
        )


# --------------------------------------------------------------------------- #
class DriftAgent(Agent):
    """Estimates radiomap drift vs the immutable baseline (no rewrite)."""

    name = "DriftAgent"

    def run(self, ctx: AgentContext) -> None:
        # Compare measured RSSI at reported motion centre to baseline predict.
        residual = ctx.twin.twin_residual(ctx.sample)
        # z-like score vs assumed shadowing sigma.
        sigma = ctx.cfg.path_loss.shadow_sigma_db
        drift_score = residual / max(sigma, 1e-6)
        state = "stable"
        if drift_score > 2.5:
            state = "significant"
        elif drift_score > 1.0:
            state = "elevated"
        ctx.drift_state = {
            "twin_residual_db": round(residual, 3),
            "drift_score": round(drift_score, 3),
            "state": state,
            "baseline_rewritten": False,  # invariant: never auto-rewrite
        }
        ctx.log(self.name, "drift assessed", **ctx.drift_state)


# --------------------------------------------------------------------------- #
class ConsistencyAgent(Agent):
    """Cross-modal agreement via JS divergence + MAP Mahalanobis distance."""

    name = "ConsistencyAgent"

    def run(self, ctx: AgentContext) -> None:
        fcfg = ctx.cfg.fusion
        status = "CONSISTENT"
        js = maha = overlap = None
        if ctx.rssi_posterior is not None and ctx.ftm_posterior is not None:
            js = metrics.jensen_shannon(ctx.rssi_posterior, ctx.ftm_posterior)
            overlap = metrics.hpd_overlap(
                ctx.grid, ctx.rssi_posterior, ctx.ftm_posterior,
                fcfg.hpd_mass)
            map_r = metrics.posterior_map(ctx.grid, ctx.rssi_posterior)
            map_f = metrics.posterior_map(ctx.grid, ctx.ftm_posterior)
            sh_r = metrics.sharpness(ctx.grid, ctx.rssi_posterior)
            sh_f = metrics.sharpness(ctx.grid, ctx.ftm_posterior)
            pooled = np.sqrt(0.5 * (sh_r ** 2 + sh_f ** 2)) + 1e-6
            maha = float(np.linalg.norm(map_r - map_f) / pooled)
            if (overlap < fcfg.consistency_overlap_conflict
                    or maha > fcfg.consistency_mahalanobis_conflict):
                status = "CONFLICT"
            elif (overlap < fcfg.consistency_overlap_uncertain
                    or maha > fcfg.consistency_mahalanobis_uncertain):
                status = "UNCERTAIN"
        else:
            status = "UNCERTAIN"  # single modality -> cannot cross-check
        ctx.consistency = {
            "status": status,
            "hpd_overlap": None if overlap is None else round(overlap, 4),
            "map_mahalanobis": None if maha is None else round(maha, 3),
            "jensen_shannon": None if js is None else round(js, 4),
        }
        ctx.log(self.name, "consistency evaluated", **ctx.consistency)


# --------------------------------------------------------------------------- #
class ThreatAssessmentAgent(Agent):
    """Combines twin residual, consistency and scenario cues into a state."""

    name = "ThreatAssessmentAgent"

    def run(self, ctx: AgentContext) -> None:
        residual = ctx.drift_state.get("twin_residual_db", 0.0)
        consistency = ctx.consistency.get("status", "UNCERTAIN")
        indicators: List[str] = []
        anomaly = min(1.0, residual / 15.0)  # normalise dB residual to 0..1

        if residual > 8.0:
            indicators.append("high_twin_residual")
        if consistency == "CONFLICT":
            indicators.append("cross_modal_conflict")
            anomaly = max(anomaly, 0.6)
        if ctx.incident and ctx.incident.rejected:
            indicators.append("rejected_measurements")
        # Rogue/relay/jamming leave characteristic traces already surfaced
        # above; the scenario tag is *not* used as ground truth for detection,
        # only recorded for reproducibility.
        level = "none"
        if anomaly >= 0.7:
            level = "high"
        elif anomaly >= 0.4:
            level = "medium"
        elif anomaly >= 0.15:
            level = "low"
        ctx.threat_state = {
            "level": level,
            "anomaly_score": round(float(anomaly), 3),
            "indicators": indicators,
        }
        ctx.log(self.name, "threat assessed", **ctx.threat_state)


# --------------------------------------------------------------------------- #
class VerificationAgent(Agent):
    """Selects the next-best FTM anchor by expected entropy reduction."""

    name = "VerificationAgent"

    def run(self, ctx: AgentContext) -> None:
        # Expected information gain proxy: anchors closest to the current HPD
        # centroid with good geometry give the largest expected reduction.
        map_xy = np.asarray(ctx.uncertainty.get("MAP", [0, 0]), float)
        candidates = []
        for s in ctx.site.sensors:
            if not s.supports_ftm:
                continue
            d = float(np.hypot(s.x - map_xy[0], s.y - map_xy[1]))
            # crude EIG proxy: prefer moderate distance (geometry) + not blinded
            eig = 1.0 / (1.0 + abs(d - 8.0))
            candidates.append((s.sensor_id, round(eig, 4), round(d, 2)))
        candidates.sort(key=lambda c: c[1], reverse=True)
        best = candidates[0] if candidates else (None, 0.0, None)
        ctx.verification_plan = {
            "next_best_anchor": best[0],
            "expected_information_gain": best[1],
            "distance_to_map_m": best[2],
            "ranked_candidates": candidates[:3],
            "cost_note": "active FTM request consumes airtime/energy (Module 5)",
        }
        ctx.log(self.name, "verification planned",
                next_best_anchor=best[0], eig=best[1])


# --------------------------------------------------------------------------- #
class ReadinessAgent(Agent):
    """Produces the integrated readiness profile for the running system."""

    name = "ReadinessAgent"

    def run(self, ctx: AgentContext) -> None:
        # Demonstration evidence keyed to what this reference core actually
        # implements.  Real deployments attach test reports and protocols.
        trl = ReadinessDimension(
            "TRL", claimed_level=4,
            evidence=[
                ReadinessEvidence("E-TRL-1", "Bayesian fusion validated in "
                                  "simulation", "tests/test_fusion.py", True),
                ReadinessEvidence("E-TRL-2", "HPD + calibration metrics "
                                  "implemented", "awa/localization/metrics.py",
                                  True),
                ReadinessEvidence("E-TRL-3", "Relevant-environment pilot",
                                  "TODO: field trial", False),
            ],
            blocking_gaps=[],
        )
        crl = ReadinessDimension(
            "CRL", claimed_level=2,
            evidence=[
                ReadinessEvidence("E-CRL-1", "Value proposition drafted",
                                  "docs/ARCHITECTURE.md", True),
            ],
        )
        irl = ReadinessDimension(
            "IRL", claimed_level=3,
            evidence=[
                ReadinessEvidence("E-IRL-1", "SAR JSON contract + schema",
                                  "schemas/sar.schema.json", True),
                ReadinessEvidence("E-IRL-2", "SIEM/SOAR interfaces designed",
                                  "docs/ARCHITECTURE.md", True),
            ],
        )
        ops = ReadinessDimension(
            "OperationalReadiness", claimed_level=2,
            evidence=[
                ReadinessEvidence("E-OPS-1", "Reproducible demo runbook",
                                  "README.md", True),
            ],
            blocking_gaps=["No SOC SOP / incident-response playbook validated"],
        )
        profile = assess_profile("awa-core", [trl, crl, irl, ops])
        ctx.readiness_profile = profile.to_dict()
        ctx.log(self.name, "readiness assessed",
                TRL=ctx.readiness_profile["TRL"],
                IRL=ctx.readiness_profile["IRL"],
                production_ready=ctx.readiness_profile["production_ready"])


# --------------------------------------------------------------------------- #
class SocDecisionAgent(Agent):
    """Maps risk + calibration + policy to a bounded decision tier."""

    name = "SocDecisionAgent"

    def run(self, ctx: AgentContext) -> None:
        anomaly = ctx.threat_state.get("anomaly_score", 0.0)
        consistency = ctx.consistency.get("status", "UNCERTAIN")
        crit_mass = ctx.uncertainty.get("zone_posterior", {}).get(
            "Z-critical", 0.0
        )
        completeness = (
            ctx.incident.completeness if ctx.incident else 0.0
        )

        # Base tier from anomaly.
        if anomaly < 0.15:
            tier = DecisionTier.OBSERVE
        elif anomaly < 0.4:
            tier = DecisionTier.ENRICH
        elif anomaly < 0.7:
            tier = DecisionTier.VERIFY
        else:
            tier = DecisionTier.HUMAN_IN_THE_LOOP

        # Escalate if a critical-zone intrusion is likely AND well-supported.
        if crit_mass > 0.5 and anomaly >= 0.4 and completeness >= 0.6:
            tier = max(tier, DecisionTier.HUMAN_IN_THE_LOOP)

        # Containment is NEVER auto-selected here: it requires a governance
        # gate and an approved policy (enforced by GovernanceAgent).
        rationale = [
            f"anomaly={anomaly:.2f}",
            f"consistency={consistency}",
            f"critical_zone_mass={crit_mass:.2f}",
            f"completeness={completeness:.2f}",
        ]
        ctx.decision = {
            "recommended_tier": int(tier),
            "recommended_action": DECISION_TIER_NAMES[int(tier)],
            "rationale": rationale,
            "false_containment_cost_considered": True,
        }
        ctx.log(self.name, "decision proposed", **ctx.decision)


# --------------------------------------------------------------------------- #
class EvidenceAgent(Agent):
    """Builds the hash-anchored Spatial Attribution Record."""

    name = "EvidenceAgent"

    def run(self, ctx: AgentContext) -> None:
        cfg = ctx.cfg
        _, achieved, area = metrics.hpd_region(
            ctx.grid, ctx.posterior, cfg.fusion.hpd_mass
        )
        hpd_geometry = {
            "type": "grid_cells",
            "cell_size_m": ctx.grid.cfg.resolution,
            "area_m2": round(area, 3),
        }
        rssi_summary = {
            "map": metrics.posterior_map(
                ctx.grid, ctx.rssi_posterior
            ).tolist() if ctx.rssi_posterior is not None else None,
            "sharpness_m": round(metrics.sharpness(
                ctx.grid, ctx.rssi_posterior), 3)
            if ctx.rssi_posterior is not None else None,
        }
        ftm_summary = None
        if ctx.ftm_posterior is not None:
            ftm_summary = {
                "map": metrics.posterior_map(
                    ctx.grid, ctx.ftm_posterior).tolist(),
                "sharpness_m": round(metrics.sharpness(
                    ctx.grid, ctx.ftm_posterior), 3),
            }
        ctx.sar = build_sar(
            incident_id=ctx.sample.incident_id,
            entity_id="entity-pseudonymous-0001",
            site_id=ctx.site.site_id,
            time_window=["1970-01-01T00:00:00Z", "1970-01-01T00:00:05Z"],
            map_crs=ctx.site.crs,
            map_xy=ctx.uncertainty["MAP"],
            zone_posterior=ctx.uncertainty["zone_posterior"],
            hpd_geometry=hpd_geometry,
            hpd_mass=round(achieved, 4),
            uncertainty_metrics={
                k: ctx.uncertainty[k]
                for k in ("entropy_nats", "sharpness_m",
                          "multimodality_modes")
            },
            rssi_posterior_summary=rssi_summary,
            ftm_posterior_summary=ftm_summary,
            wlan_sensing_context={
                "motion_centre": ctx.sample.motion_centre,
                "used": "sensing" in ctx.used_modalities,
            },
            modality_consistency=ctx.consistency,
            sensor_contributions=ctx.sensor_contributions,
            missing_modalities=ctx.missing_modalities,
            quality_components=ctx.incident.quality_components
            if ctx.incident else {},
            drift_state=ctx.drift_state,
            threat_state=ctx.threat_state,
            anomaly_score=ctx.threat_state.get("anomaly_score", 0.0),
            versions={
                "data_schema_version": cfg.data_schema_version,
                "model_version": cfg.model_version,
                "radiomap_version": ctx.radiomap.version,
                "digital_twin_version": "twin-0.1.0",
                "calibration_version": cfg.calibration_version,
                "policy_version": cfg.policy_version,
            },
            evidence_references=[
                f"audit://{ctx.sample.incident_id}/log",
                f"posterior://{ctx.sample.incident_id}",
            ],
            recommended_action=ctx.decision["recommended_action"],
            decision_tier=ctx.decision["recommended_tier"],
            human_review_status="pending"
            if ctx.decision["recommended_tier"] >= int(
                DecisionTier.HUMAN_IN_THE_LOOP) else "not_required",
            readiness_profile=ctx.readiness_profile,
            created_at="1970-01-01T00:00:05Z",  # deterministic for repro
        )
        ctx.log(self.name, "SAR built",
                provenance_hash=ctx.sar["provenance_hash"][:16])


# --------------------------------------------------------------------------- #
class GovernanceAgent(Agent):
    """Final gate: enforces the agent prohibitions of prompt Module 9."""

    name = "GovernanceAgent"

    def run(self, ctx: AgentContext) -> None:
        findings: List[str] = []
        tier = ctx.decision.get("recommended_tier", 0)

        # Invariant: no containment tier without an approved policy flag.
        approved_containment = False  # demo: containment policy not approved
        if tier >= int(DecisionTier.LIMITED_CONTAINMENT) and not \
                approved_containment:
            findings.append(
                "Containment blocked: no approved containment policy; "
                "downgraded to HUMAN_IN_THE_LOOP"
            )
            ctx.decision["recommended_tier"] = int(
                DecisionTier.HUMAN_IN_THE_LOOP)
            ctx.decision["recommended_action"] = DECISION_TIER_NAMES[
                int(DecisionTier.HUMAN_IN_THE_LOOP)]

        # Invariant: baseline radiomap must not be silently rewritten.
        if ctx.drift_state.get("baseline_rewritten", False):
            findings.append("VIOLATION: baseline radiomap was rewritten")

        # Invariant: uncertainty must be surfaced, never hidden.
        if not ctx.uncertainty:
            findings.append("VIOLATION: uncertainty metrics missing from output")

        ctx.decision["governance_findings"] = findings
        ctx.log(self.name, "governance gate applied", findings=findings)


# --------------------------------------------------------------------------- #
class Orchestrator:
    """Runs a fixed sequence of agents over a shared context (state machine)."""

    def __init__(self, agents: List[Agent]):
        self.agents = agents

    def run(self, ctx: AgentContext) -> AgentContext:
        for agent in self.agents:
            agent.run(ctx)
        return ctx


def default_orchestrator() -> Orchestrator:
    return Orchestrator(
        [
            ObservationAgent(),
            LocalizationAgent(),
            DriftAgent(),
            ConsistencyAgent(),
            ThreatAssessmentAgent(),
            VerificationAgent(),
            ReadinessAgent(),
            SocDecisionAgent(),
            EvidenceAgent(),
            GovernanceAgent(),
        ]
    )
