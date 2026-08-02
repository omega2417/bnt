"""Spatial Attribution Record: machine-readable, hash-anchored evidence.

The SAR is the platform's evidentiary output for SOC/SIEM/SOAR (prompt Module
12).  It is deterministic and reproducible: every field derives from versioned
artefacts, and ``provenance_hash`` binds the record to its inputs so any later
tampering is detectable.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any, Dict, List, Optional


def sar_provenance_hash(record: Dict[str, Any]) -> str:
    """SHA-256 over the canonical JSON of the record *excluding* the hash and
    signature fields themselves."""
    payload = {
        k: v
        for k, v in record.items()
        if k not in ("provenance_hash", "signature")
    }
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def build_sar(
    *,
    incident_id: str,
    entity_id: str,
    site_id: str,
    time_window: List[str],
    map_crs: str,
    map_xy: List[float],
    zone_posterior: Dict[str, float],
    hpd_geometry: Dict[str, Any],
    hpd_mass: float,
    uncertainty_metrics: Dict[str, Any],
    rssi_posterior_summary: Dict[str, Any],
    ftm_posterior_summary: Optional[Dict[str, Any]],
    wlan_sensing_context: Dict[str, Any],
    modality_consistency: Dict[str, Any],
    sensor_contributions: Dict[str, float],
    missing_modalities: List[str],
    quality_components: Dict[str, Any],
    drift_state: Dict[str, Any],
    threat_state: Dict[str, Any],
    anomaly_score: float,
    versions: Dict[str, str],
    evidence_references: List[str],
    recommended_action: str,
    decision_tier: int,
    human_review_status: str,
    readiness_profile: Dict[str, Any],
    created_at: str,
    signer: str = "awa-demo-unsigned",
) -> Dict[str, Any]:
    """Assemble a SAR dict matching ``schemas/sar.schema.json``."""
    record: Dict[str, Any] = {
        "incident_id": incident_id,
        "entity_id": entity_id,
        "site_id": site_id,
        "time_window": time_window,
        "data_schema_version": versions.get("data_schema_version", "sar-1.0.0"),
        "map_crs": map_crs,
        "MAP": map_xy,
        "zone_posterior": zone_posterior,
        "HPD_geometry": hpd_geometry,
        "HPD_mass": hpd_mass,
        "uncertainty_metrics": uncertainty_metrics,
        "RSSI_posterior": rssi_posterior_summary,
        "FTM_posterior": ftm_posterior_summary,
        "WLAN_sensing_context": wlan_sensing_context,
        "modality_consistency": modality_consistency,
        "sensor_contributions": sensor_contributions,
        "missing_modalities": missing_modalities,
        "quality_components": quality_components,
        "drift_state": drift_state,
        "threat_state": threat_state,
        "anomaly_score": anomaly_score,
        "model_version": versions.get("model_version"),
        "radiomap_version": versions.get("radiomap_version"),
        "digital_twin_version": versions.get("digital_twin_version"),
        "calibration_version": versions.get("calibration_version"),
        "policy_version": versions.get("policy_version"),
        "playbook_version": versions.get("playbook_version", "playbook-0.1.0"),
        "evidence_references": evidence_references,
        "recommended_action": recommended_action,
        "decision_tier": decision_tier,
        "human_review_status": human_review_status,
        "readiness_profile": readiness_profile,
        "created_at": created_at,
    }
    record["provenance_hash"] = sar_provenance_hash(record)
    # Demonstration signature only; production uses PKI / mTLS (Module 16).
    record["signature"] = f"{signer}:{record['provenance_hash'][:16]}"
    return record
