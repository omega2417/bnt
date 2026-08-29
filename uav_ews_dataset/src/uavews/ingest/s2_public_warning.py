"""S2 - public warning events.

The stream is external, asynchronous, and not under the collection's control.
Three consequences shape the adapter:

* the source clock is untrusted. The warning carries an issue time and a
  retrieval time; only the retrieval time is observed by the collection, so the
  offset between them is recorded rather than assumed away, and the source class
  gets the widest clock uncertainty in the configuration.
* the feed re-delivers. A warning fetched twice is the same event, and counting
  it twice would inflate both the event count and any measure of external
  corroboration. Duplicates are detected on the keyed hash of the upstream
  identifier and are recorded, not dropped silently.
* the payload is third-party content. The unmodified object is digested and
  referenced; only a normalized derived field is stored, and the original is
  retained or referenced according to the provider's terms.

Category names are mapped onto the Common Alerting Protocol field set so that a
consumer does not have to learn a bespoke vocabulary.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, List, Tuple

import pandas as pd

from .. import ids, timebase as tb
from ..config import Config
from .common import read_jsonl, register_source, rotation_epoch

# Minimal CAP alignment; the release stores both the source term and this mapping.
CAP_CATEGORY = {"alert": "Security", "background": "Other"}


def ingest(path: Path, cfg: Config, salt: bytes, t0_ns: int,
           run_to_event: Dict[str, str]) -> Tuple[pd.DataFrame, List[dict], List[dict]]:
    """Return (observations, source registry, duplicate report)."""
    rot = int(cfg.release["rotation_policy_days"])
    sigma_ms = float(cfg["synchronization"]["clock_uncertainty_ms"]["external_public"])

    observations: List[dict] = []
    sources: List[dict] = []
    duplicates: List[dict] = []
    seen: Dict[str, str] = {}

    for rec in read_jsonl(path):
        issued = tb.rfc3339_to_ns(rec["issued_at"])
        retrieved = tb.rfc3339_to_ns(rec["retrieved_at"])
        native = rec["source_alert_id"]
        h = ids.source_event_id_hash(salt, native)

        epoch = rotation_epoch(retrieved, t0_ns, rot)
        sid = ids.rotating_source_id(salt, f"public-feed::{rec['sender']}", epoch)
        register_source(sources, sid, "external_public", "public_warning",
                        "asynchronous_declared", sigma_ms, "public_warning_api",
                        "documented_reuse_terms", 1825, epoch)

        oid = ids.observation_id(salt, sid, native)
        if h in seen:
            duplicates.append({
                "stream": "S2", "source_event_id_hash": h,
                "first_observation_id": seen[h],
                "repeat_retrieved_utc": tb.ns_to_rfc3339(retrieved),
                "resolution": "suppressed_from_canonical_table",
            })
            continue
        seen[h] = oid

        hint = rec.get("linked_run_hint")
        event_id = run_to_event.get(hint) if hint else None

        # A warning that cannot be attached to a known event is still a record.
        # It is retained with a null event only when the release keeps an
        # unattached-context table; here it is dropped from the event-centered
        # tables and counted, because every canonical row must have a parent
        # event and inventing one would create a phantom event.
        if event_id is None:
            duplicates.append({
                "stream": "S2", "source_event_id_hash": h,
                "first_observation_id": None,
                "repeat_retrieved_utc": tb.ns_to_rfc3339(retrieved),
                "resolution": "unattached_context_not_in_event_tables",
            })
            continue

        observations.append({
            "observation_id": oid,
            "event_id": event_id,
            "window_id": None,
            "source_id": sid,
            "stream": "S2",
            "modality": "public_warning",
            "t_native_utc_ns": issued,
            "t_ingest_utc_ns": retrieved,
            # The feed publishes no offset estimate. The retrieval lag is an
            # upper bound on it, not the offset itself, so the correction is
            # zero and the whole lag is carried as uncertainty instead.
            "clock_offset_ns": 0,
            "clock_offset_sigma_ns": tb.seconds_to_ns(sigma_ms / 1000.0),
            "t_corrected_utc_ns": issued,
            "sync_error_ns": None,
            "obs_start_utc_ns": issued,
            "obs_end_utc_ns": retrieved,
            "location_cell": "GENERALIZED_AREA",
            "object_uri": None,
            "perceived_direction": None,
            "reporter_confidence": None,
            "source_event_id_hash": h,
            "access_tier": "open",
            "missing_reason": "not_applicable",
            "_cap_category": CAP_CATEGORY.get(rec.get("category", ""), "Other"),
            "_retrieval_lag_s": (retrieved - issued) / tb.NS,
        })

    return pd.DataFrame(observations), sources, duplicates
