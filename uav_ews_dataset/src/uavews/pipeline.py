"""End-to-end dataset formation and preparation.

Stage order is fixed and each stage records a provenance activity:

    1  ingest        raw stream deliveries -> canonical records
    2  window        event tiling into pre/event/post analysis windows
    3  associate     uncertainty-expanded attachment, Eq. (3)
    4  label         Eq. (1)/(2) ground truth, weak evidence, annotations
    5  adjudicate    conflict resolution, one released label per target
    6  privacy       access tiering, k-anonymity probe, export audit
    7  validate      Eq. (4), Eq. (5), sync, media quality, cross-modal, integrity
    8  split         leakage-resistant manifests and their audit
    9  package       RO-Crate, DataCite, PROV-O, checksums
    10 gate          acceptance rules applied to the computed values

Privacy runs before validation on purpose: the validation gates are meant to
assess what will actually be released, and assessing the pre-sanitization tables
would report quality the user never receives.
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List

import numpy as np
import pandas as pd

from . import (agreement, association, ids, labeling, packaging, privacy,
               schema, simulate, splits, timebase as tb, trialdesign, validation)
from .config import Config
from .geometry import WarningZone
from .ingest import s1_takeoff, s2_public_warning, s3_mobile, s4_media

__version__ = "0.1.0"


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


@dataclass
class PipelineResult:
    tables: Dict[str, pd.DataFrame]
    manifests: Dict[str, pd.DataFrame]
    reports: Dict[str, object]
    metrics: Dict[str, object]
    gates: pd.DataFrame
    kinematics: Dict[str, dict]
    activities: List[dict] = field(default_factory=list)
    written: Dict[str, Path] = field(default_factory=dict)


def run(cfg: Config, raw_root: Path, out_root: Path, salt_seed: str = "rehearsal",
        verbose: bool = True) -> PipelineResult:
    raw_root, out_root = Path(raw_root), Path(out_root)
    salt = ids.release_salt(salt_seed)
    zone = WarningZone.from_config(cfg)
    t0_ns = tb.rfc3339_to_ns("2025-04-01T00:00:00Z")
    activities: List[dict] = []

    def stage(name: str, subject: str = "", **kw):
        activities.append({"activity": name, "subject": subject,
                           "started": _now(), "software_version": __version__, **kw})
        if verbose:
            print(f"[{len(activities):>2}] {name} {subject}")

    # ---- 1. ingest -------------------------------------------------------- #
    stage("capture", "S1 takeoff indications")
    ev1, obs1, src1, kinematics = s1_takeoff.ingest(
        raw_root / "s1_takeoff_events.jsonl", raw_root, cfg, salt, zone, t0_ns)
    run_to_event = dict(zip(obs1["_native_run_id"], obs1["event_id"]))

    stage("capture", "site episode log")
    ev0, obs0, src0, map0 = s4_media.ingest_episode_log(
        raw_root / "site_episode_log.jsonl", cfg, salt, t0_ns)
    run_to_event.update(map0)

    stage("capture", "S2 public warnings")
    obs2, src2, s2_dups = s2_public_warning.ingest(
        raw_root / "s2_public_warnings.jsonl", cfg, salt, t0_ns, run_to_event)

    stage("capture", "S3 mobile reports")
    obs3, src3 = s3_mobile.ingest(
        raw_root / "s3_mobile_reports.jsonl", cfg, salt, t0_ns, run_to_event)

    ac = cfg["detectability"]["acoustic"]
    low_snr_db = float(ac["detection_snr_db"]) - float(ac.get("detector_processing_gain_db", 0.0))
    stage("capture", "S4 media objects")
    obs4, media, src4, s4_exc = s4_media.ingest(
        raw_root / "s4_media_index.jsonl", raw_root, cfg, salt, t0_ns,
        run_to_event, low_snr_db)

    events = pd.concat([ev1, ev0], ignore_index=True)
    observations = pd.concat([obs1, obs0, obs2, obs3, obs4], ignore_index=True)
    sources = pd.DataFrame(src1 + src0 + src2 + src3 + src4).drop_duplicates("source_id")

    # ---- 2. windows ------------------------------------------------------- #
    stage("transformation", "window tiling")
    windows = association.build_windows(events, cfg, salt)

    # ---- 3. association and Eq. (3) --------------------------------------- #
    stage("transformation", "synchronization error, Eq. (3)")
    markers = association.load_sync_markers(
        raw_root / "sync_markers.jsonl", salt, cfg, t0_ns)
    observations = association.compute_sync_error(observations, markers, run_to_event)
    stage("transformation", "uncertainty-expanded association")
    observations, assoc_diag = association.associate(observations, windows, sources, cfg)
    sync = association.sync_report(observations, sources, cfg)

    # ---- 4-5. labels ------------------------------------------------------ #
    stage("transformation", "kinematic ground truth, Eq. (1) and Eq. (2)")
    gt = labeling.derive_kinematic_labels(kinematics, windows, events, cfg, salt)
    neg = labeling.derive_negative_labels(events, salt)
    weak = labeling.derive_weak_labels(observations, salt)
    stage("review", "independent annotation")
    ann = simulate.simulate_annotations(events, windows, media, kinematics, cfg, salt)
    raw_labels = pd.concat([d for d in (gt, neg, weak, ann) if d is not None and not d.empty],
                           ignore_index=True)
    stage("adjudication", "conflict resolution")
    labels = labeling.adjudicate(raw_labels, cfg, salt)

    agree = agreement.agreement_report(
        labels, ["vehicle_presence", "movement_direction"])

    # ---- 6. privacy ------------------------------------------------------- #
    stage("deidentification", "media access tiering")
    media, privacy_decisions = privacy.apply_media_privacy(media, cfg)
    kanon = privacy.k_anonymity_report(observations)

    open_tables = {
        "events": events,
        "windows": windows,
        "sources": sources,
        "observations": privacy.strip_internal_columns(observations),
        "media_manifest": privacy.strip_internal_columns(media),
        "labels": labeling.released_labels(labels),
    }
    audit = privacy.audit_open_export(open_tables)
    blocking = audit[audit["severity"] == "blocking"] if not audit.empty else audit

    # ---- 7. validation ---------------------------------------------------- #
    stage("integrity_verification", "structural validation")
    issues: List[dict] = []
    for name, table in schema.TABLES.items():
        if name in open_tables:
            issues += schema.validate_table(open_tables[name], table, cfg.vocab)
    issues += schema.check_referential_integrity(open_tables)
    schema_issues = pd.DataFrame(issues)

    n_rows = sum(len(t) for t in open_tables.values())
    n_bad = int(schema_issues["n"].sum()) if not schema_issues.empty else 0
    schema_pass_rate = max(0.0, 1.0 - n_bad / max(n_rows, 1))

    completeness = validation.completeness_report(open_tables)
    dup = validation.duplicate_rate(media)
    miss = validation.missingness_report(open_tables["observations"], schema.OBSERVATIONS)
    mquality = validation.media_quality_report(media)
    pva = validation.predicted_vs_achieved(media)
    xmodal = validation.cross_modal_consistency(labels, observations, windows)
    stage("integrity_verification", "checksum recomputation")
    integrity = validation.verify_integrity(
        media[media["access_tier"] != "metadata_only"], raw_root)

    # ---- 8. splits -------------------------------------------------------- #
    stage("transformation", "leakage-resistant manifests")
    manifests = splits.build_manifests(events, observations, media, cfg)
    split_audit = splits.audit(manifests, events, media, cfg)

    # ---- 9-10. metrics, gates, package ------------------------------------ #
    presence_alpha = float("nan")
    if not agree.empty:
        row = agree[agree["target_name"] == "vehicle_presence"]
        if len(row):
            presence_alpha = float(row["krippendorff_alpha"].iloc[0])

    metrics: Dict[str, object] = {
        "schema_pass_rate": schema_pass_rate,
        "n_schema_issues": int(len(schema_issues)),
        "checksum_pass_rate": integrity["pass_rate"],
        "median_completeness": float(completeness["median_completeness"].min())
        if not completeness.empty else float("nan"),
        "p05_completeness": float(completeness["p05_completeness"].min())
        if not completeness.empty else float("nan"),
        "sync_median_ms": float(sync[sync.modality == "ALL"]["median_ms"].iloc[0]),
        "sync_p95_ms": float(sync[sync.modality == "ALL"]["p95_ms"].iloc[0]),
        "sync_max_ms": float(sync[sync.modality == "ALL"]["max_ms"].iloc[0]),
        "exact_duplicate_rate": dup["exact_duplicate_rate"],
        "near_duplicate_rate": dup["near_duplicate_rate"],
        "cross_modal_consistency": xmodal["consistency_rate"],
        "krippendorff_alpha": presence_alpha,
        "privacy_residual_findings": int(len(blocking)),
        "leakage_violations": int(split_audit["constraint_violations"].sum()
                                  + split_audit["near_duplicate_violations"].sum()),
        "association_rate": float(assoc_diag["associated"].mean()),
        "n_events": int(len(events)),
        "n_observations": int(len(observations)),
        "n_media_objects": int(len(media)),
        "n_labels_released": int(len(open_tables["labels"])),
        "audio_hours": float(media[media.media_type == "audio"]["duration_s"]
                             .fillna(0).sum() / 3600.0),
        "n_visual_objects": int((media["media_type"] != "audio").sum()),
    }
    gates = validation.run_gates(metrics, cfg)

    coverage = {
        "collection_start_utc": tb.ns_to_rfc3339(int(events["t_start_utc_ns"].min())),
        "collection_end_utc": tb.ns_to_rfc3339(int(events["t_end_utc_ns"].max())),
        "n_generalized_locations": int(events["location_cell"].nunique()),
        "n_site_groups": int(events["site_group_id"].nunique()),
        "event_kind_counts": events["event_kind"].value_counts().to_dict(),
        "hard_negative_counts": events["hard_negative_type"].value_counts().to_dict(),
    }

    reports: Dict[str, object] = {
        "schema_issues": schema_issues,
        "completeness": completeness,
        "duplicates": dup,
        "missingness": miss,
        "media_quality": mquality,
        "predicted_vs_achieved": pva,
        "cross_modal": xmodal,
        "integrity": integrity,
        "sync": sync,
        "association": assoc_diag,
        "agreement": agree,
        "k_anonymity": kanon,
        "privacy_decisions": privacy_decisions,
        "privacy_audit": audit,
        "split_audit": split_audit,
        "s2_duplicates": pd.DataFrame(s2_dups),
        "s4_exceptions": pd.DataFrame(s4_exc),
        "coverage": coverage,
        # The pre-sanitization media frame is kept for the report figures, which
        # compare predicted with achieved detectability. It is a working artefact
        # and is never part of the exported package.
        "media_full": media,
        "campaign_plan": trialdesign.campaign_plan(cfg),
        "detectability": trialdesign.detectability_table(cfg),
    }

    stage("release", "package assembly")
    written = packaging.write_package(out_root, open_tables, manifests, cfg, salt,
                                      activities, reports)
    return PipelineResult(tables=open_tables, manifests=manifests, reports=reports,
                          metrics=metrics, gates=gates, kinematics=kinematics,
                          activities=activities, written=written)
