"""Canonical table schemas and the structural validator.

The manuscript's Table 3 lists six analytic tables. Each is declared here as an
ordered list of :class:`Field` records carrying type, unit, nullability, and -
where applicable - the name of the controlled vocabulary that constrains it.
The same declaration drives three things that would otherwise drift apart:

* the structural validation gate,
* the exported ``docs/data_dictionary.csv``,
* the required-field set R that Equation (4) averages over.

A field is ``required`` when its absence makes the row uninterpretable. A
nullable field that is absent is not an error, but it must carry a
``missing_reason`` code: the release never distinguishes "not measured" from
"withheld" by leaving a cell blank.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional

import numpy as np
import pandas as pd


@dataclass(frozen=True)
class Field:
    name: str
    dtype: str                      # pandas/arrow-compatible dtype
    unit: str = ""
    required: bool = False
    vocab: Optional[str] = None     # key into vocabularies.yaml
    definition: str = ""
    missing_code: str = ""          # reason code used when the value is absent


@dataclass(frozen=True)
class Table:
    name: str
    key: str
    fields: List[Field]

    @property
    def required_fields(self) -> List[str]:
        """The set R of Equation (4)."""
        return [f.name for f in self.fields if f.required]

    def field(self, name: str) -> Field:
        for f in self.fields:
            if f.name == name:
                return f
        raise KeyError(name)

    def columns(self) -> List[str]:
        return [f.name for f in self.fields]


EVENTS = Table(
    "events", "event_id",
    [
        Field("event_id", "string", required=True,
              definition="Stable random identifier; encodes no site, time or participant."),
        Field("event_kind", "string", required=True, vocab="event_kind",
              definition="Controlled flight, verified or weak observation, or negative control."),
        Field("t_start_utc_ns", "int64", "ns", required=True,
              definition="Inclusive event start, UTC nanoseconds."),
        Field("t_end_utc_ns", "int64", "ns", required=True,
              definition="Inclusive event end, UTC nanoseconds."),
        Field("t_precision_ms", "float64", "ms", required=True,
              definition="Timestamp precision of the anchoring source."),
        Field("t_uncertainty_ms", "float64", "ms", required=True,
              definition="1-sigma uncertainty of the event interval endpoints."),
        Field("zone_id", "string", required=True,
              definition="Generalized warning-zone identifier; public geometry coarsened."),
        Field("location_cell", "string", required=True,
              definition="Spatial cell at the public generalization resolution."),
        Field("site_group_id", "string", required=True,
              definition="Grouping key for the location-holdout manifest."),
        Field("campaign_id", "string", required=True,
              definition="Collection campaign; groups replicate runs."),
        Field("route_family", "string", vocab=None,
              definition="Approach-geometry family; near-identical runs share a value.",
              missing_code="not_applicable"),
        Field("hard_negative_type", "string", vocab="hard_negative_type",
              definition="Confounder family for negative-control events.",
              missing_code="not_applicable"),
        Field("access_tier", "string", required=True, vocab="access_tier",
              definition="Release tier governing the event record itself."),
    ],
)

WINDOWS = Table(
    "windows", "window_id",
    [
        Field("window_id", "string", required=True,
              definition="Identifier of a bounded interval linked to one event."),
        Field("event_id", "string", required=True, definition="Parent event."),
        Field("window_role", "string", required=True,
              definition="pre_event, event, or post_event."),
        Field("w_start_utc_ns", "int64", "ns", required=True, definition="Window start."),
        Field("w_end_utc_ns", "int64", "ns", required=True, definition="Window end."),
        Field("window_index", "int32", required=True,
              definition="Ordinal position of the window within its event."),
    ],
)

SOURCES = Table(
    "sources", "source_id",
    [
        Field("source_id", "string", required=True,
              definition="Rotating pseudonymous source profile identifier."),
        Field("source_class", "string", required=True,
              definition="site_ptp, site_ntp, mobile, or external_public."),
        Field("modality", "string", required=True, vocab="modality",
              definition="Kind of record the source emits."),
        Field("sync_method", "string", required=True, vocab="sync_method",
              definition="Declared clock discipline."),
        Field("clock_sigma_ms", "float64", "ms", required=True,
              definition="1-sigma offset uncertainty to the site reference."),
        Field("device_profile", "string", required=True,
              definition="Generic device class; never a serial number or address."),
        Field("rights_basis", "string", required=True,
              definition="Consent, permission, or documented reuse basis."),
        Field("retention_days", "int32", "d", required=True,
              definition="Retention period agreed for the source."),
        Field("rotation_epoch", "int32", required=True,
              definition="Pseudonym rotation epoch this profile belongs to."),
    ],
)

OBSERVATIONS = Table(
    "observations", "observation_id",
    [
        Field("observation_id", "string", required=True, definition="Stable record key."),
        Field("event_id", "string", required=True, definition="Parent event."),
        Field("window_id", "string",
              definition="Associated window; null when no association passed the overlap test.",
              missing_code="not_applicable"),
        Field("source_id", "string", required=True, definition="Emitting source profile."),
        Field("stream", "string", required=True, definition="S1, S2, S3, or S4."),
        Field("modality", "string", required=True, vocab="modality"),
        Field("t_native_utc_ns", "int64", "ns", required=True,
              definition="Source-reported time; never overwritten."),
        Field("t_ingest_utc_ns", "int64", "ns", required=True, definition="Ingestion time."),
        Field("clock_offset_ns", "int64", "ns", required=True,
              definition="Estimated offset of the source clock to the reference."),
        Field("clock_offset_sigma_ns", "int64", "ns", required=True,
              definition="1-sigma uncertainty of that offset."),
        Field("t_corrected_utc_ns", "int64", "ns", required=True,
              definition="Derived corrected time = native - offset."),
        Field("sync_error_ns", "int64", "ns",
              definition="Equation (3) against the event reference clock.",
              missing_code="not_observed"),
        Field("obs_start_utc_ns", "int64", "ns", required=True,
              definition="Start of the observation support interval."),
        Field("obs_end_utc_ns", "int64", "ns", required=True,
              definition="End of the observation support interval."),
        Field("location_cell", "string", required=True,
              definition="Generalized cell; never an exact sensor coordinate."),
        Field("object_uri", "string",
              definition="Relative URI of the payload; null for structure-only records.",
              missing_code="not_applicable"),
        Field("perceived_direction", "string", vocab="movement_direction",
              definition="Direction reported by a human contributor, if any.",
              missing_code="not_observed"),
        Field("reporter_confidence", "float64",
              definition="Self-reported confidence of a mobile contributor.",
              missing_code="not_observed"),
        Field("source_event_id_hash", "string",
              definition="Keyed hash of an upstream identifier, for duplicate detection.",
              missing_code="not_applicable"),
        Field("corroboration_group", "string",
              definition="Cluster of reports from one source in one temporal "
                         "neighbourhood; corroboration counts groups, not rows.",
              missing_code="not_applicable"),
        Field("access_tier", "string", required=True, vocab="access_tier"),
        Field("missing_reason", "string", vocab="missing_reason",
              definition="Why an expected payload or field is absent.",
              missing_code="not_applicable"),
    ],
)

MEDIA_MANIFEST = Table(
    "media_manifest", "object_id",
    [
        Field("object_id", "string", required=True, definition="Media object key."),
        Field("observation_id", "string", required=True, definition="Owning observation."),
        Field("event_id", "string", required=True, definition="Owning event."),
        Field("object_uri", "string", required=True, definition="Relative path in the crate."),
        Field("media_type", "string", required=True, vocab="modality",
              definition="image, video, or audio."),
        Field("codec", "string", required=True, definition="Container/codec of the released object."),
        Field("duration_s", "float64", "s",
              definition="Duration; null for still images.", missing_code="not_applicable"),
        Field("width_px", "int32", "px", missing_code="not_applicable"),
        Field("height_px", "int32", "px", missing_code="not_applicable"),
        Field("frame_rate_hz", "float64", "Hz", missing_code="not_applicable"),
        Field("sample_rate_hz", "int32", "Hz", missing_code="not_applicable"),
        Field("channels", "int32", missing_code="not_applicable"),
        Field("bit_depth", "int32", "bit", missing_code="not_applicable"),
        Field("obj_start_utc_ns", "int64", "ns", required=True),
        Field("obj_end_utc_ns", "int64", "ns", required=True),
        Field("snr_db", "float64", "dB",
              definition="Measured in-band SNR; null when the estimator is "
                         "saturated, i.e. no tonal is distinguishable from noise.",
              missing_code="not_observed"),
        Field("snr_estimator_floor_db", "float64", "dB",
              definition="Peak-to-floor ratio below which the SNR estimate is "
                         "indistinguishable from noise for this object's length.",
              missing_code="not_applicable"),
        Field("target_px", "float64", "px",
              definition="Longest apparent target extent for visual objects.",
              missing_code="not_applicable"),
        Field("blur_score", "float64",
              definition="Variance of the Laplacian; lower is blurrier.",
              missing_code="not_applicable"),
        Field("quality_flags", "string", definition="Semicolon-joined quality flags.",
              missing_code="not_applicable"),
        Field("derived_from", "string",
              definition="Parent object_id when this object is a transformation.",
              missing_code="not_applicable"),
        Field("calibration_version", "string", required=True),
        Field("duplicate_group", "string", required=True,
              definition="Near-duplicate cluster key; the unit of Equation (5)."),
        Field("sha256", "string", required=True, definition="Digest of the released bytes."),
        Field("size_bytes", "int64", "B", required=True),
        Field("access_tier", "string", required=True, vocab="access_tier"),
    ],
)

LABELS = Table(
    "labels", "label_id",
    [
        Field("label_id", "string", required=True),
        Field("target_kind", "string", required=True,
              definition="event, observation, object, or segment."),
        Field("target_id", "string", required=True),
        Field("event_id", "string", required=True,
              definition="Denormalized parent event, so split membership is inherited."),
        Field("target_name", "string", required=True,
              definition="vehicle_presence, movement_direction, platform_class, "
                         "distance_interval, time_to_zone, or hard_negative_type."),
        Field("value", "string", required=True,
              definition="Controlled value, or a numeric string for time_to_zone."),
        Field("evidence_tier", "string", required=True, vocab="evidence_tier"),
        Field("annotator_id", "string", required=True,
              definition="Annotator-independent pseudonym, or a rule identifier."),
        Field("confidence", "float64", required=True,
              definition="Calibrated or rubric-based confidence in [0, 1]."),
        Field("confidence_method", "string", required=True),
        Field("uncertainty_reason", "string",
              definition="Why the label is uncertain, when it is.",
              missing_code="not_applicable"),
        Field("support_start_utc_ns", "int64", "ns", required=True,
              definition="Start of the temporal support of the label."),
        Field("support_end_utc_ns", "int64", "ns", required=True),
        Field("adjudication_status", "string", required=True, vocab="adjudication_status"),
        Field("adjudication_code", "string",
              definition="Non-identifying decision code from the review.",
              missing_code="not_applicable"),
        Field("is_adjudicated_final", "bool", required=True,
              definition="True for the single released label per (target, target_name)."),
        Field("access_tier", "string", required=True, vocab="access_tier"),
    ],
)

TABLES: Dict[str, Table] = {
    t.name: t for t in (EVENTS, WINDOWS, SOURCES, OBSERVATIONS, MEDIA_MANIFEST, LABELS)
}


# --------------------------------------------------------------------------- #
# Structural validation
# --------------------------------------------------------------------------- #
def is_present(series: pd.Series) -> pd.Series:
    """A value is present when it is neither null nor an empty string."""
    if series.dtype == object or pd.api.types.is_string_dtype(series):
        return series.notna() & (series.astype("string").str.len() > 0)
    return series.notna()


def validate_table(df: pd.DataFrame, table: Table, vocab: Dict[str, list]) -> List[dict]:
    """Return a list of structural violations; an empty list means the gate passes."""
    issues: List[dict] = []
    declared = set(table.columns())
    missing_cols = declared - set(df.columns)
    for col in sorted(missing_cols):
        issues.append({"table": table.name, "kind": "missing_column", "field": col,
                       "n": len(df), "detail": "declared in schema but absent"})
    extra = set(df.columns) - declared
    for col in sorted(extra):
        issues.append({"table": table.name, "kind": "undeclared_column", "field": col,
                       "n": len(df), "detail": "present but not in the data dictionary"})

    for f in table.fields:
        if f.name not in df.columns:
            continue
        col = df[f.name]
        if f.required:
            n_bad = int((~is_present(col)).sum())
            if n_bad:
                issues.append({"table": table.name, "kind": "null_required",
                               "field": f.name, "n": n_bad,
                               "detail": "required field is empty"})
        if f.vocab:
            allowed = set(vocab[f.vocab])
            vals = col[is_present(col)].astype("string")
            bad = sorted(set(vals) - allowed)
            if bad:
                issues.append({"table": table.name, "kind": "vocabulary_violation",
                               "field": f.name, "n": int(vals.isin(bad).sum()),
                               "detail": f"values outside {f.vocab}: {bad[:5]}"})

    if table.key in df.columns:
        dup = int(df[table.key].duplicated().sum())
        if dup:
            issues.append({"table": table.name, "kind": "duplicate_key",
                           "field": table.key, "n": dup,
                           "detail": "primary key is not unique"})

    for start, end in (("t_start_utc_ns", "t_end_utc_ns"),
                       ("w_start_utc_ns", "w_end_utc_ns"),
                       ("obs_start_utc_ns", "obs_end_utc_ns"),
                       ("obj_start_utc_ns", "obj_end_utc_ns"),
                       ("support_start_utc_ns", "support_end_utc_ns")):
        if start in df.columns and end in df.columns:
            bad = int((df[end] < df[start]).sum())
            if bad:
                issues.append({"table": table.name, "kind": "interval_inverted",
                               "field": f"{start}/{end}", "n": bad,
                               "detail": "end precedes start"})

    if "confidence" in df.columns:
        c = pd.to_numeric(df["confidence"], errors="coerce")
        bad = int(((c < 0) | (c > 1)).sum())
        if bad:
            issues.append({"table": table.name, "kind": "range_violation",
                           "field": "confidence", "n": bad,
                           "detail": "confidence outside [0, 1]"})

    if "sha256" in df.columns:
        s = df["sha256"].astype("string")
        bad = int((~s.str.fullmatch(r"[0-9a-f]{64}").fillna(False)).sum())
        if bad:
            issues.append({"table": table.name, "kind": "format_violation",
                           "field": "sha256", "n": bad,
                           "detail": "not a 64-character lowercase hex digest"})
    return issues


def check_referential_integrity(tables: Dict[str, pd.DataFrame]) -> List[dict]:
    """Verify the joins of the event-centered model actually resolve."""
    issues: List[dict] = []
    refs = [
        ("windows", "event_id", "events", "event_id"),
        ("observations", "event_id", "events", "event_id"),
        ("observations", "source_id", "sources", "source_id"),
        ("media_manifest", "observation_id", "observations", "observation_id"),
        ("media_manifest", "event_id", "events", "event_id"),
        ("labels", "event_id", "events", "event_id"),
    ]
    for child, fk, parent, pk in refs:
        if child not in tables or parent not in tables:
            continue
        cdf, pdf = tables[child], tables[parent]
        if fk not in cdf.columns or pk not in pdf.columns:
            continue
        present = is_present(cdf[fk])
        orphan = int((~cdf.loc[present, fk].isin(set(pdf[pk]))).sum())
        if orphan:
            issues.append({"table": child, "kind": "orphan_reference", "field": fk,
                           "n": orphan, "detail": f"no matching {parent}.{pk}"})

    # A window reference must point at a window of the *same* event.
    if "observations" in tables and "windows" in tables:
        obs, win = tables["observations"], tables["windows"]
        if "window_id" in obs.columns:
            m = obs.loc[is_present(obs["window_id"]), ["window_id", "event_id"]].merge(
                win[["window_id", "event_id"]], on="window_id",
                how="left", suffixes=("_obs", "_win"))
            bad = int((m["event_id_obs"] != m["event_id_win"]).sum())
            if bad:
                issues.append({"table": "observations", "kind": "cross_event_window",
                               "field": "window_id", "n": bad,
                               "detail": "observation linked to another event's window"})
    return issues


def data_dictionary() -> pd.DataFrame:
    """Export ``docs/data_dictionary.csv`` straight from the declarations."""
    rows = []
    for t in TABLES.values():
        for f in t.fields:
            rows.append({
                "table": t.name, "field": f.name, "type": f.dtype, "unit": f.unit,
                "required": f.required, "controlled_vocabulary": f.vocab or "",
                "missing_code": f.missing_code, "definition": f.definition,
            })
    return pd.DataFrame(rows)
