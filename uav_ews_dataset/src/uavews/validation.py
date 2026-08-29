"""Technical validation: the release gates of Table 7.

Each function computes one dimension and returns numbers, not a verdict. The
verdict is assembled at the end by :func:`run_gates`, which compares every
computed value with its configured acceptance rule and reports pass, fail, or
not-applicable. Keeping computation and judgement apart matters because the
acceptance rules are release policy and will change between versions, while the
metric definitions must not.

A record can pass structural validation and still fail media or evidence quality.
Quality is therefore always multi-valued: nothing in this module collapses the
dimensions into a single score.
"""

from __future__ import annotations

from pathlib import Path
from typing import Dict, List, Sequence

import numpy as np
import pandas as pd

from . import ids, schema, timebase as tb
from .config import Config


# --------------------------------------------------------------------------- #
# Equation (4): completeness
# --------------------------------------------------------------------------- #
def record_completeness(df: pd.DataFrame, table: schema.Table) -> pd.Series:
    """Equation (4): C_i = (1/|R|) * sum over r in R of 1(r is valid).

    R is the required-field set declared in :mod:`uavews.schema`, so completeness
    is measured against what the record was supposed to contain, not against the
    columns that happen to be populated. Averaging over an ad-hoc column list
    would let a release raise its own completeness by dropping fields.
    """
    R = [f for f in table.required_fields if f in df.columns]
    if not R:
        return pd.Series(np.ones(len(df)), index=df.index)
    valid = pd.concat([schema.is_present(df[f]) for f in R], axis=1)
    return valid.sum(axis=1) / float(len(table.required_fields))


def completeness_report(tables: Dict[str, pd.DataFrame]) -> pd.DataFrame:
    rows: List[dict] = []
    for name, table in schema.TABLES.items():
        if name not in tables or tables[name].empty:
            continue
        c = record_completeness(tables[name], table)
        rows.append({
            "table": name, "n_records": len(c),
            "n_required_fields": len(table.required_fields),
            "median_completeness": float(np.median(c)),
            "p05_completeness": float(np.percentile(c, 5)),
            "min_completeness": float(np.min(c)),
            "fully_complete_rate": float(np.mean(c >= 1.0)),
        })
    return pd.DataFrame(rows)


# --------------------------------------------------------------------------- #
# Equation (5): duplicates
# --------------------------------------------------------------------------- #
def duplicate_rate(media: pd.DataFrame) -> Dict[str, float]:
    """Equation (5): D = (N - N_u) / N, evaluated at object-group level.

    Counting at frame level would be both easier and wrong: a 25 fps clip yields
    hundreds of near-identical frames that are not duplicates in any sense the
    user cares about, and the resulting rate would be dominated by the frame rate
    rather than by redelivery. Two rates are reported - exact byte identity and
    near-duplicate grouping - because they call for different remedies. An exact
    duplicate is an ingestion defect; a near-duplicate is a partitioning hazard.
    """
    if media.empty:
        return {"n_objects": 0, "n_unique_groups": 0, "duplicate_rate": 0.0,
                "exact_duplicate_rate": 0.0, "near_duplicate_rate": 0.0}
    n = len(media)
    n_u = media["duplicate_group"].nunique()
    n_exact_u = media["sha256"].nunique()
    exact = (n - n_exact_u) / n
    total = (n - n_u) / n
    return {
        "n_objects": int(n),
        "n_unique_groups": int(n_u),
        "duplicate_rate": float(total),
        "exact_duplicate_rate": float(exact),
        "near_duplicate_rate": float(max(total - exact, 0.0)),
        "largest_group": int(media["duplicate_group"].value_counts().max()),
    }


# --------------------------------------------------------------------------- #
# Missingness
# --------------------------------------------------------------------------- #
def missingness_report(df: pd.DataFrame, table: schema.Table,
                       by: str = "modality") -> pd.DataFrame:
    """Missingness by field and stratum, with the reason codes that explain it."""
    rows: List[dict] = []
    strata = df[by].unique() if by in df.columns else ["ALL"]
    for f in table.fields:
        if f.name not in df.columns:
            continue
        for s in strata:
            sub = df if s == "ALL" else df[df[by] == s]
            if sub.empty:
                continue
            miss = float((~schema.is_present(sub[f.name])).mean())
            rows.append({"table": table.name, "field": f.name, by: s,
                         "n": len(sub), "missing_rate": miss,
                         "required": f.required,
                         "declared_missing_code": f.missing_code})
    return pd.DataFrame(rows)


# --------------------------------------------------------------------------- #
# Media quality
# --------------------------------------------------------------------------- #
def media_quality_report(media: pd.DataFrame) -> pd.DataFrame:
    if media.empty:
        return pd.DataFrame()
    rows: List[dict] = []
    for mtype, grp in media.groupby("media_type"):
        flags = grp["quality_flags"].fillna("").str.split(";")
        flat = [f for lst in flags for f in lst if f]
        counts = pd.Series(flat).value_counts() if flat else pd.Series(dtype=int)
        row = {"media_type": mtype, "n_objects": len(grp),
               "any_flag_rate": float((grp["quality_flags"].fillna("") != "").mean())}
        for flag in ("clipping", "silence", "low_snr", "speech_detected",
                     "blur", "over_exposure", "under_exposure"):
            row[f"rate_{flag}"] = float(counts.get(flag, 0)) / len(grp)
        if mtype == "audio":
            s = grp["snr_db"].dropna()
            row.update({"snr_median_db": float(s.median()) if len(s) else np.nan,
                        "snr_p05_db": float(np.percentile(s, 5)) if len(s) else np.nan,
                        "snr_p95_db": float(np.percentile(s, 95)) if len(s) else np.nan})
        else:
            t = grp["target_px"].dropna()
            b = grp["blur_score"].dropna()
            row.update({"target_px_median": float(t.median()) if len(t) else np.nan,
                        "target_px_p05": float(np.percentile(t, 5)) if len(t) else np.nan,
                        "blur_median": float(b.median()) if len(b) else np.nan})
        rows.append(row)
    return pd.DataFrame(rows)


def predicted_vs_achieved(media: pd.DataFrame) -> pd.DataFrame:
    """Compare the planning curves with what the sensors actually delivered.

    This is the check that turns the design assumptions of
    :mod:`uavews.trialdesign` into something falsifiable. A systematic offset
    between predicted and measured SNR is a calibration finding - the assumed
    source level or ambient level is wrong - and it is the first quantity the
    first field campaign should report back.
    """
    if media.empty or "_predicted_snr_db" not in media.columns:
        return pd.DataFrame()
    rows: List[dict] = []
    aud = media[(media["media_type"] == "audio") & media["snr_db"].notna()
                & media["_predicted_snr_db"].notna()]
    if len(aud) > 2:
        resid = aud["snr_db"].astype(float) - aud["_predicted_snr_db"].astype(float)
        rows.append({"channel": "acoustic_snr_db", "n": len(aud),
                     "bias": float(resid.mean()), "mad": float(resid.abs().mean()),
                     "rmse": float(np.sqrt((resid ** 2).mean())),
                     "pearson_r": float(np.corrcoef(
                         aud["snr_db"].astype(float),
                         aud["_predicted_snr_db"].astype(float))[0, 1])})
    vis = media[(media["media_type"] != "audio") & media["target_px"].notna()
                & media["_predicted_target_px"].notna()]
    vis = vis[vis["target_px"] > 0]
    if len(vis) > 2:
        resid = vis["target_px"].astype(float) - vis["_predicted_target_px"].astype(float)
        rows.append({"channel": "visual_target_px", "n": len(vis),
                     "bias": float(resid.mean()), "mad": float(resid.abs().mean()),
                     "rmse": float(np.sqrt((resid ** 2).mean())),
                     "pearson_r": float(np.corrcoef(
                         vis["target_px"].astype(float),
                         vis["_predicted_target_px"].astype(float))[0, 1])})
    return pd.DataFrame(rows)


# --------------------------------------------------------------------------- #
# Cross-modal consistency
# --------------------------------------------------------------------------- #
def cross_modal_consistency(labels: pd.DataFrame, observations: pd.DataFrame,
                            windows: pd.DataFrame) -> Dict[str, object]:
    """Do the weak reports agree with ground truth *over the same interval*?

    The comparison has to be contemporaneous. A track that approaches, passes,
    and recedes has no single event-level direction, so scoring a report against
    an event-level summary measures when the contributor happened to look rather
    than whether they were right. Each report is therefore matched to the
    ground-truth window its support interval overlaps most, and compared with the
    direction label of that window.

    A single percentage is not enough on its own: the confusion matrix is
    returned with it, because 90 % consistency in which every error is
    approaching-called-receding is a different resource from one whose errors
    fall into ``uncertain``.
    """
    gt = labels[(labels["evidence_tier"] == "controlled_ground_truth")
                & (labels["target_name"] == "movement_direction")
                & (labels["target_kind"] == "segment")]
    weak = observations[(observations["stream"] == "S3")
                        & observations["perceived_direction"].notna()]
    empty = {"n_comparable": 0, "n_unmatched": int(len(weak)),
             "consistency_rate": float("nan"), "confusion": pd.DataFrame()}
    if gt.empty or weak.empty or windows.empty:
        return empty

    gt_by_window = dict(zip(gt["target_id"], gt["value"]))
    win_by_event: Dict[str, list] = {}
    for r in windows.itertuples():
        if r.window_role == "event" and r.window_id in gt_by_window:
            win_by_event.setdefault(r.event_id, []).append(
                (r.window_id, int(r.w_start_utc_ns), int(r.w_end_utc_ns)))

    truths, claims, unmatched = [], [], 0
    for r in weak.itertuples():
        best, best_ov = None, 0
        for wid, a, b in win_by_event.get(r.event_id, []):
            ov = tb.overlap_ns((int(r.obs_start_utc_ns), int(r.obs_end_utc_ns)), (a, b))
            if ov > best_ov:
                best, best_ov = wid, ov
        if best is None:
            unmatched += 1
            continue
        truth = gt_by_window[best]
        claim = str(r.perceived_direction)
        if truth == "uncertain" or claim == "uncertain":
            continue
        truths.append(truth)
        claims.append(claim)

    if not truths:
        return {**empty, "n_unmatched": unmatched}
    t = pd.Series(truths, name="ground_truth")
    c = pd.Series(claims, name="reported")
    return {"n_comparable": len(t), "n_unmatched": unmatched,
            "consistency_rate": float((t.to_numpy() == c.to_numpy()).mean()),
            "confusion": pd.crosstab(t, c)}


# --------------------------------------------------------------------------- #
# Integrity
# --------------------------------------------------------------------------- #
def verify_integrity(media: pd.DataFrame, root: Path) -> Dict[str, object]:
    """Recompute every digest against the released bytes.

    The target is 100 %. Anything less is not a quality score to be reported and
    accepted - it means a released object is not the object the manifest
    describes, and the release cannot ship until the discrepancy is explained.
    """
    if media.empty:
        return {"n_files": 0, "n_match": 0, "pass_rate": 1.0, "failures": []}
    failures: List[dict] = []
    n_match = 0
    for _, r in media.iterrows():
        p = Path(root) / str(r["object_uri"])
        if not p.exists():
            failures.append({"object_id": r["object_id"], "reason": "missing_file"})
            continue
        actual = ids.sha256_file(p)
        if actual == r["sha256"]:
            n_match += 1
        else:
            failures.append({"object_id": r["object_id"], "reason": "digest_mismatch",
                             "expected": r["sha256"], "actual": actual})
    n = len(media)
    return {"n_files": int(n), "n_match": int(n_match),
            "pass_rate": n_match / n if n else 1.0, "failures": failures}


# --------------------------------------------------------------------------- #
# Gates
# --------------------------------------------------------------------------- #
def run_gates(metrics: Dict[str, object], cfg: Config) -> pd.DataFrame:
    """Compare every computed value with its acceptance rule.

    A failed gate is a documented decision - repair, exclusion, metadata-only, or
    controlled access - never a silent discard. This function produces the record
    of that decision; acting on it is the release manager's job.
    """
    g = cfg["quality_gates"]
    checks = [
        ("schema_pass_rate", metrics.get("schema_pass_rate"), ">=",
         g["schema_pass_rate_min"], "structural validation"),
        ("checksum_pass_rate", metrics.get("checksum_pass_rate"), ">=",
         g["checksum_pass_rate_min"], "integrity manifest"),
        ("median_completeness", metrics.get("median_completeness"), ">=",
         g["median_completeness_min"], "Eq. (4) median over all tables"),
        ("p05_completeness", metrics.get("p05_completeness"), ">=",
         g["p05_completeness_min"], "Eq. (4) 5th percentile"),
        ("sync_p95_ms", metrics.get("sync_p95_ms"), "<=",
         g["sync_p95_ms_max"], "Eq. (3) 95th percentile"),
        ("exact_duplicate_rate", metrics.get("exact_duplicate_rate"), "<=",
         g["exact_duplicate_rate_max"], "Eq. (5), byte identity"),
        ("near_duplicate_rate", metrics.get("near_duplicate_rate"), "<=",
         g["near_duplicate_rate_max"], "Eq. (5), perceptual grouping"),
        ("cross_modal_consistency", metrics.get("cross_modal_consistency"), ">=",
         g["cross_modal_consistency_min"], "weak reports vs ground truth"),
        ("krippendorff_alpha", metrics.get("krippendorff_alpha"), ">=",
         g["krippendorff_alpha_min"], "presence agreement"),
        ("privacy_residual_findings", metrics.get("privacy_residual_findings"), "<=",
         g["privacy_residual_findings_max"], "independent sample audit"),
        ("leakage_violations", metrics.get("leakage_violations"), "<=",
         0, "group disjointness across partitions"),
    ]
    rows: List[dict] = []
    for name, value, op, threshold, note in checks:
        if value is None or (isinstance(value, float) and np.isnan(value)):
            status = "not_evaluated"
        elif op == ">=":
            status = "pass" if value >= threshold else "FAIL"
        else:
            status = "pass" if value <= threshold else "FAIL"
        rows.append({"gate": name, "observed": value, "rule": f"{op} {threshold}",
                     "status": status, "basis": note})
    return pd.DataFrame(rows)
