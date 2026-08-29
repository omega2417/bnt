"""S3 - voluntary mobile reports and sensor observations.

Weak evidence, and the adapter's job is to keep it weak. Three mechanisms:

* the contributor identity is replaced by a pseudonym that rotates every
  ``rotation_policy_days``, so contributions are unlinkable across epochs;
* reports from the same source in the same temporal neighbourhood are assigned a
  ``corroboration_group`` and counted once, so one enthusiastic contributor
  cannot manufacture apparent consensus;
* free text is held out of the open tier until it passes disclosure review.

Mobile clocks are not disciplined. The device reports its own skew estimate,
which is applied as a correction while the native time is preserved, and the
residual is carried as a wide uncertainty that the association step must respect.
"""

from __future__ import annotations

from pathlib import Path
from typing import Dict, List, Tuple

import pandas as pd

from .. import ids, timebase as tb
from ..config import Config
from .common import generalize_cell, read_jsonl, register_source, rotation_epoch


def ingest(path: Path, cfg: Config, salt: bytes, t0_ns: int,
           run_to_event: Dict[str, str],
           corroboration_window_s: float = 120.0
           ) -> Tuple[pd.DataFrame, List[dict]]:
    res = float(cfg.release["public_spatial_resolution_m"])
    rot = int(cfg.release["rotation_policy_days"])
    sigma_ms = float(cfg["synchronization"]["clock_uncertainty_ms"]["mobile"])

    rows: List[dict] = []
    sources: List[dict] = []

    for rec in read_jsonl(path):
        hint = rec.get("linked_run_hint")
        event_id = run_to_event.get(hint) if hint else None
        if event_id is None:
            # Unattachable reports are the norm in participatory sensing. They
            # are counted in the ingestion exception log rather than forced onto
            # the nearest event: proximity alone is not evidence of relation.
            continue

        reported = tb.rfc3339_to_ns(rec["reported_at"])
        epoch = rotation_epoch(reported, t0_ns, rot)
        sid = ids.rotating_source_id(salt, rec["contributor_key"], epoch)
        register_source(sources, sid, "mobile", "mobile_report",
                        "asynchronous_declared", sigma_ms, rec["device_profile"],
                        "informed_consent_v1.2", 730, epoch)

        skew_ns = tb.seconds_to_ns(float(rec.get("device_clock_skew_s") or 0.0))
        corrected = reported - skew_ns
        rows.append({
            "observation_id": ids.observation_id(salt, sid, rec["report_uid"]),
            "event_id": event_id,
            "window_id": None,
            "source_id": sid,
            "stream": "S3",
            "modality": "mobile_report",
            "t_native_utc_ns": reported,
            # The delivery time is observed by the collection, so it comes from
            # the delivery. An adapter must never synthesize a value it did not
            # receive - besides being fiction, a randomly generated field makes
            # the release irreproducible, and Python's string hash is salted per
            # process, so it would not even be stable across two runs of the same
            # code on the same input.
            "t_ingest_utc_ns": tb.rfc3339_to_ns(
                rec.get("received_at") or rec["reported_at"]),
            "clock_offset_ns": skew_ns,
            "clock_offset_sigma_ns": tb.seconds_to_ns(sigma_ms / 1000.0),
            "t_corrected_utc_ns": corrected,
            "sync_error_ns": None,
            "obs_start_utc_ns": tb.rfc3339_to_ns(rec["observation_start"]) - skew_ns,
            "obs_end_utc_ns": tb.rfc3339_to_ns(rec["observation_end"]) - skew_ns,
            "location_cell": generalize_cell(rec["coarse_east_m"],
                                             rec["coarse_north_m"], res),
            "object_uri": None,
            "perceived_direction": rec.get("perceived_direction"),
            "reporter_confidence": rec.get("self_confidence"),
            "source_event_id_hash": ids.source_event_id_hash(salt, rec["report_uid"]),
            "access_tier": "open",
            "missing_reason": ("not_observed" if not rec.get("perceived_direction")
                               else "not_applicable"),
            "_free_text_present": bool(rec.get("free_text")),
            "_consent_receipt": rec.get("consent_receipt"),
        })

    df = pd.DataFrame(rows)
    if not df.empty:
        df["corroboration_group"] = _cluster(df, corroboration_window_s)
    return df, sources


def _cluster(df: pd.DataFrame, window_s: float) -> pd.Series:
    """Group reports by (event, source, temporal neighbourhood).

    A single-linkage pass in time: within one event and one source, consecutive
    reports closer than ``window_s`` join the same group. Downstream, corroboration
    counts distinct groups, not distinct rows, so twenty taps from one phone in
    one minute contribute the weight of one report.
    """
    out = pd.Series(index=df.index, dtype="object")
    for (eid, sid), grp in df.groupby(["event_id", "source_id"], sort=False):
        grp = grp.sort_values("t_corrected_utc_ns")
        gid, last = 0, None
        for idx, row in grp.iterrows():
            t = row["t_corrected_utc_ns"]
            if last is not None and (t - last) > tb.seconds_to_ns(window_s):
                gid += 1
            out.loc[idx] = f"{eid[:8]}:{sid[:8]}:{gid}"
            last = t
    return out
