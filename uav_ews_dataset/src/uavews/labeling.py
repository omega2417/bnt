"""Label construction, evidence tiers, and conflict adjudication.

The rule the schema enforces is that a label is never an unqualified class name.
Every row carries what it means, how strongly it is supported, who or what
produced it, over which interval, and how a conflict about it was resolved.

Evidence priority is *not* a global ordering. Controlled ground truth wins on the
fields the reference system actually observes - presence, direction, distance,
warning time - and on nothing else. It has no authority over whether a target was
audible, whether a frame was usable, or what an unrelated public report meant.
Encoding that distinction is the whole point of ``AUTHORITATIVE_FIELDS``.
"""

from __future__ import annotations

from typing import Dict, List, Sequence

import numpy as np
import pandas as pd

from . import ids, timebase as tb
from .config import Config

#: Fields on which a controlled flight log is authoritative. Anything outside
#: this set is adjudicated on the evidence, whatever tier it came from.
AUTHORITATIVE_FIELDS = frozenset({
    "vehicle_presence", "movement_direction", "distance_interval",
    "time_to_zone", "platform_class",
})

TIER_RANK = {"controlled_ground_truth": 3, "expert_verified": 2, "weak_public_report": 1}

DISTANCE_BINS = [(0.0, 100.0, "0-100"), (100.0, 300.0, "100-300"),
                 (300.0, 700.0, "300-700"), (700.0, 1500.0, "700-1500"),
                 (1500.0, float("inf"), "1500+")]


def distance_bin(d_m: float) -> str:
    if d_m is None or not np.isfinite(d_m):
        return "unknown"
    for lo, hi, name in DISTANCE_BINS:
        if lo <= d_m < hi:
            return name
    return "unknown"


def _row(salt, target_kind, target_id, event_id, target_name, value, tier,
         annotator, confidence, method, support, status="not_required",
         final=True, uncertainty=None, code=None) -> dict:
    return {
        "label_id": ids.label_id(salt, target_kind + ":" + target_name,
                                 target_id, annotator),
        "target_kind": target_kind, "target_id": target_id, "event_id": event_id,
        "target_name": target_name, "value": str(value),
        "evidence_tier": tier, "annotator_id": annotator,
        "confidence": float(confidence), "confidence_method": method,
        "uncertainty_reason": uncertainty,
        "support_start_utc_ns": int(support[0]), "support_end_utc_ns": int(support[1]),
        "adjudication_status": status, "adjudication_code": code,
        "is_adjudicated_final": bool(final), "access_tier": "open",
    }


def derive_kinematic_labels(kinematics: Dict[str, dict], windows: pd.DataFrame,
                            events: pd.DataFrame, cfg: Config,
                            salt: bytes) -> pd.DataFrame:
    """Ground-truth labels computed from the reference trajectory.

    Window-level direction is the majority of the per-sample labels of
    Equation (1)/(2) inside the window, and it is only emitted when that majority
    is decisive: a window that straddles the turn from approaching to receding
    genuinely has no single direction, and forcing one would teach a model to
    predict the annotation rule rather than the physics.
    """
    rows: List[dict] = []
    ev = events.set_index("event_id")
    win_by_event: Dict[str, pd.DataFrame] = {
        eid: g for eid, g in windows.groupby("event_id")}

    for eid, kin in kinematics.items():
        if eid not in ev.index:
            continue
        t0 = int(kin["t_start_ns"])
        e_start = int(ev.at[eid, "t_start_utc_ns"])
        e_end = int(ev.at[eid, "t_end_utc_ns"])
        t_s = kin["t_s"]
        d = kin["d_m"]
        direction = kin["direction"]
        T = kin["warning_time_s"]

        rows.append(_row(salt, "event", eid, eid, "vehicle_presence", "present",
                         "controlled_ground_truth", "rule:flight_log", 1.0,
                         "authorized_flight_log", (e_start, e_end)))
        rows.append(_row(salt, "event", eid, eid, "platform_class",
                         kin["platform_class"], "controlled_ground_truth",
                         "rule:flight_log", 1.0, "authorized_flight_log",
                         (e_start, e_end)))

        for _, w in win_by_event.get(eid, pd.DataFrame()).iterrows():
            if w["window_role"] != "event":
                continue
            wid = w["window_id"]
            a = (int(w["w_start_utc_ns"]) - t0) / tb.NS
            b = (int(w["w_end_utc_ns"]) - t0) / tb.NS
            m = (t_s >= a) & (t_s <= b)
            if m.sum() < 2:
                continue
            support = (int(w["w_start_utc_ns"]), int(w["w_end_utc_ns"]))

            vals, counts = np.unique(direction[m].astype(str), return_counts=True)
            share = counts.max() / counts.sum()
            top = str(vals[int(np.argmax(counts))])
            if share >= 0.6 and top != "uncertain":
                value, conf, unc = top, float(share), None
            else:
                value, conf, unc = "uncertain", float(share), "mixed_direction_in_window"
            rows.append(_row(salt, "segment", wid, eid, "movement_direction", value,
                             "controlled_ground_truth", "rule:eq1_direction", conf,
                             "majority_of_reference_samples", support,
                             uncertainty=unc))

            d_mid = float(np.median(d[m]))
            rows.append(_row(salt, "segment", wid, eid, "distance_interval",
                             distance_bin(d_mid), "controlled_ground_truth",
                             "rule:eq1_distance", 1.0, "reference_trajectory",
                             support))

            tt = T[m]
            if np.all(np.isnan(tt)):
                value, unc = "censored", "no_verified_crossing"
                conf = 1.0
            else:
                value = f"{float(np.nanmedian(tt)):.1f}"
                unc, conf = None, 1.0
            rows.append(_row(salt, "segment", wid, eid, "time_to_zone", value,
                             "controlled_ground_truth", "rule:eq2_warning_time",
                             conf, "reference_trajectory", support,
                             uncertainty=unc))
    return pd.DataFrame(rows)


def derive_negative_labels(events: pd.DataFrame, salt: bytes) -> pd.DataFrame:
    """Labels for negative-control events.

    Retaining the confounder family is what makes false-alarm evaluation possible
    at all: a benchmark whose negatives are only empty sky measures nothing about
    the errors that matter operationally.
    """
    rows: List[dict] = []
    neg = events[events["event_kind"] == "negative_control"]
    for _, e in neg.iterrows():
        support = (int(e["t_start_utc_ns"]), int(e["t_end_utc_ns"]))
        rows.append(_row(salt, "event", e["event_id"], e["event_id"],
                         "vehicle_presence", "absent", "controlled_ground_truth",
                         "rule:negative_control_session", 1.0,
                         "planned_negative_session", support))
        rows.append(_row(salt, "event", e["event_id"], e["event_id"],
                         "hard_negative_type", e["hard_negative_type"] or "other",
                         "controlled_ground_truth", "rule:negative_control_session",
                         1.0, "planned_negative_session", support))
    return pd.DataFrame(rows)


def derive_weak_labels(observations: pd.DataFrame, salt: bytes) -> pd.DataFrame:
    """Weak evidence from mobile reports, clustered so one device counts once.

    The confidence carried forward is the contributor's own, discounted by the
    size of its corroboration group: the second and later reports in one group
    add no independent information, so their weight is divided rather than summed.
    """
    rows: List[dict] = []
    m = observations[(observations["stream"] == "S3")
                     & observations["perceived_direction"].notna()]
    if m.empty:
        return pd.DataFrame(rows)
    sizes = m.groupby("corroboration_group")["observation_id"].transform("size")
    for (_, o), n in zip(m.iterrows(), sizes):
        conf = float(o["reporter_confidence"] or 0.5) / float(max(n, 1))
        rows.append(_row(salt, "observation", o["observation_id"], o["event_id"],
                         "movement_direction", o["perceived_direction"],
                         "weak_public_report", f"contributor:{o['source_id'][:8]}",
                         min(max(conf, 0.0), 1.0), "self_reported_discounted",
                         (int(o["obs_start_utc_ns"]), int(o["obs_end_utc_ns"])),
                         final=False))
    return pd.DataFrame(rows)


# --------------------------------------------------------------------------- #
# Adjudication
# --------------------------------------------------------------------------- #
def adjudicate(labels: pd.DataFrame, cfg: Config, salt: bytes) -> pd.DataFrame:
    """Resolve conflicts and mark exactly one released label per target.

    A conflict enters review when independent labels disagree, when confidence
    falls below the configured threshold, or when temporal boundaries differ by
    more than the boundary tolerance. Resolution follows the tier rule: on a field
    the flight log observes, ground truth is accepted; otherwise the weighted
    majority of the non-ground-truth labels decides, and a tie leaves the value
    ``uncertain`` rather than picking one.

    Original annotations are retained with ``is_adjudicated_final`` false, which
    is what makes the agreement statistics computable after the fact. In a real
    release those rows live in the controlled audit trail.
    """
    if labels.empty:
        return labels
    conf_threshold = float(cfg["annotation"]["confidence_threshold"])
    tol_ns = tb.seconds_to_ns(float(cfg["annotation"]["boundary_tolerance_s"]))

    out: List[pd.DataFrame] = []
    finals: List[dict] = []

    for (target_kind, target_id, target_name), grp in labels.groupby(
            ["target_kind", "target_id", "target_name"], sort=False):
        grp = grp.copy()
        values = set(grp["value"])
        spans = [(int(a), int(b)) for a, b in
                 zip(grp["support_start_utc_ns"], grp["support_end_utc_ns"])]
        boundary_spread = (max(s[0] for s in spans) - min(s[0] for s in spans)) if spans else 0
        low_conf = bool((grp["confidence"] < conf_threshold).any())
        disagree = len(values) > 1
        boundary_conflict = boundary_spread > tol_ns

        if not (disagree or low_conf or boundary_conflict):
            grp["adjudication_status"] = "not_required"
            grp["is_adjudicated_final"] = True
            out.append(grp)
            continue

        gt = grp[grp["evidence_tier"] == "controlled_ground_truth"]
        grp["adjudication_status"] = "pending"
        grp["is_adjudicated_final"] = False
        event_id = grp["event_id"].iloc[0]
        support = (int(grp["support_start_utc_ns"].min()),
                   int(grp["support_end_utc_ns"].max()))

        if len(gt) and target_name in AUTHORITATIVE_FIELDS:
            value = gt["value"].iloc[0]
            conf = float(gt["confidence"].iloc[0])
            tier = "controlled_ground_truth"
            code = "GT-ACCEPT"
            status = "accepted"
        else:
            weights: Dict[str, float] = {}
            for _, r in grp.iterrows():
                w = float(r["confidence"]) * TIER_RANK.get(r["evidence_tier"], 1)
                weights[r["value"]] = weights.get(r["value"], 0.0) + w
            ranked = sorted(weights.items(), key=lambda kv: -kv[1])
            if len(ranked) > 1 and abs(ranked[0][1] - ranked[1][1]) < 1e-9:
                value, conf, code, status = "uncertain", 0.0, "TIE-UNRESOLVED", "revised"
            else:
                value = ranked[0][0]
                total = sum(weights.values()) or 1.0
                conf = ranked[0][1] / total
                code, status = "WEIGHTED-MAJORITY", "revised"
            tier = ("expert_verified" if any(grp["evidence_tier"] == "expert_verified")
                    else "weak_public_report")

        reasons = []
        if disagree: reasons.append("label_disagreement")
        if low_conf: reasons.append("confidence_below_threshold")
        if boundary_conflict: reasons.append("boundary_spread")

        out.append(grp)
        finals.append(_row(salt, target_kind, target_id, event_id, target_name,
                           value, tier, "adjudicator", conf, "adjudication_rule_v1",
                           support, status=status, final=True,
                           uncertainty=";".join(reasons) or None, code=code))

    result = pd.concat(out + ([pd.DataFrame(finals)] if finals else []),
                       ignore_index=True)
    # An adjudicated label id must not collide with the annotation it replaced.
    result["label_id"] = [
        lid if not final or status == "not_required" else lid[:-1] + "f"
        for lid, final, status in zip(result["label_id"],
                                      result["is_adjudicated_final"],
                                      result["adjudication_status"])]
    return result


def released_labels(labels: pd.DataFrame) -> pd.DataFrame:
    """The single label per (target, target_name) that the open tier publishes."""
    return labels[labels["is_adjudicated_final"]].drop_duplicates(
        subset=["target_kind", "target_id", "target_name"], keep="last")
