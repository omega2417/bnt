"""S4 - visual and acoustic objects from authorized monitoring sites.

This adapter does the most work, because a media object is the only record type
whose quality can be measured rather than declared. For every delivered object it

* verifies the payload exists and digests the exact released bytes,
* measures audio and visual quality from the samples themselves,
* computes a perceptual hash and assigns a near-duplicate group,
* records the sensor-to-target geometry the object was captured at, so that the
  predicted detectability curves can later be checked against what was achieved,
* and, when the payload is absent, still emits the record with an explicit
  missingness reason instead of dropping the row.

Objects from monitoring sites are also the anchors for events that S1 never saw:
an observational or negative-control event has no takeoff indication, and the
first authorized record of it is a site recording.
"""

from __future__ import annotations

from pathlib import Path
from typing import Dict, List, Tuple

import numpy as np
import pandas as pd

from .. import ids, media_qc, timebase as tb
from ..config import Config
from .common import generalize_cell, read_jsonl, register_source, rotation_epoch


def ingest(path: Path, raw_root: Path, cfg: Config, salt: bytes, t0_ns: int,
           run_to_event: Dict[str, str], low_snr_db: float
           ) -> Tuple[pd.DataFrame, pd.DataFrame, List[dict], List[dict]]:
    """Return (observations, media_manifest, source registry, exceptions)."""
    res = float(cfg.release["public_spatial_resolution_m"])
    rot = int(cfg.release["rotation_policy_days"])
    sig = cfg["synchronization"]["clock_uncertainty_ms"]

    obs_rows: List[dict] = []
    media_rows: List[dict] = []
    sources: List[dict] = []
    exceptions: List[dict] = []

    for rec in read_jsonl(path):
        native = rec["native_run_id"]
        event_id = run_to_event.get(native)
        if event_id is None:
            exceptions.append({"stream": "S4", "object_key": rec["object_key"],
                               "reason": "no_parent_event"})
            continue

        t_start = tb.rfc3339_to_ns(rec["object_start"])
        t_end = tb.rfc3339_to_ns(rec["object_end"])
        method = rec["clock_method"]
        source_class = "site_ptp" if method == "ptp" else "site_ntp"
        sigma_ms = float(sig[source_class])

        epoch = rotation_epoch(t_start, t0_ns, rot)
        sid = ids.rotating_source_id(salt, f"site::{rec['site_code']}", epoch)
        register_source(sources, sid, source_class, rec["media_type"], method,
                        sigma_ms, f"site_sensor_{rec['media_type']}",
                        "site_operating_permission", 1825, epoch)

        oid = ids.observation_id(salt, sid, rec["object_key"])
        obj_id = ids.object_id(salt, sid, rec["object_key"])
        rel = rec.get("relative_path")

        base = {
            "observation_id": oid, "event_id": event_id, "window_id": None,
            "source_id": sid, "stream": "S4", "modality": rec["media_type"],
            "t_native_utc_ns": t_start, "t_ingest_utc_ns": t_end + tb.seconds_to_ns(1.5),
            "clock_offset_ns": 0,
            "clock_offset_sigma_ns": tb.seconds_to_ns(sigma_ms / 1000.0),
            "t_corrected_utc_ns": t_start, "sync_error_ns": None,
            "obs_start_utc_ns": t_start, "obs_end_utc_ns": t_end,
            "location_cell": "SITE_GENERALIZED",
            "perceived_direction": None, "reporter_confidence": None,
            "source_event_id_hash": ids.source_event_id_hash(salt, rec["object_key"]),
            "access_tier": "open",
        }

        if not rel:
            obs_rows.append({**base, "object_uri": None,
                             "missing_reason": rec.get("missing_reason")
                             or "sensor_unavailable"})
            exceptions.append({"stream": "S4", "object_key": rec["object_key"],
                               "reason": rec.get("missing_reason")
                               or "sensor_unavailable"})
            continue

        payload = raw_root / rel
        if not payload.exists():
            obs_rows.append({**base, "object_uri": None, "missing_reason": "corrupted"})
            exceptions.append({"stream": "S4", "object_key": rec["object_key"],
                               "reason": "payload_missing_on_disk"})
            continue

        digest = ids.sha256_file(payload)
        size = payload.stat().st_size
        try:
            if rec["media_type"] == "audio":
                m = media_qc.audio_metrics(payload, low_snr_db=low_snr_db)
                phash = media_qc.perceptual_hash(payload, "audio")
            else:
                m = media_qc.visual_metrics(payload)
                phash = media_qc.perceptual_hash(payload, "image")
        except Exception as exc:                    # corrupt or unreadable payload
            obs_rows.append({**base, "object_uri": rel, "missing_reason": "corrupted"})
            exceptions.append({"stream": "S4", "object_key": rec["object_key"],
                               "reason": f"decode_failed:{type(exc).__name__}"})
            continue

        obs_rows.append({**base, "object_uri": rel, "missing_reason": "not_applicable"})
        media_rows.append({
            "object_id": obj_id,
            "observation_id": oid,
            "event_id": event_id,
            "object_uri": rel,
            "media_type": rec["media_type"],
            "codec": "pcm_s16le" if rec["media_type"] == "audio" else "png",
            "duration_s": m.get("duration_s"),
            "width_px": m.get("width_px"),
            "height_px": m.get("height_px"),
            "frame_rate_hz": rec.get("frame_rate_hz"),
            "sample_rate_hz": m.get("sample_rate_hz"),
            "channels": m.get("channels"),
            "bit_depth": m.get("bit_depth"),
            "obj_start_utc_ns": t_start,
            "obj_end_utc_ns": t_end,
            "snr_db": m.get("snr_db"),
            "snr_estimator_floor_db": m.get("snr_estimator_floor_db"),
            "target_px": m.get("target_px"),
            "blur_score": m.get("blur_score"),
            "quality_flags": ";".join(m.get("quality_flags", [])),
            "derived_from": None,
            "calibration_version": rec["calibration_version"],
            "duplicate_group": None,                # assigned below
            "sha256": digest,
            "size_bytes": int(size),
            "access_tier": "open",
            # Geometry retained for the predicted-versus-achieved comparison.
            "_slant_range_m": rec.get("true_slant_range_m"),
            "_predicted_snr_db": rec.get("planned_snr_db"),
            "_predicted_target_px": rec.get("planned_target_px"),
            "_phash": phash,
            "_site_group": rec["site_group"],
        })

    media = pd.DataFrame(media_rows)
    if not media.empty:
        media["duplicate_group"] = assign_duplicate_groups(
            media, salt, int(cfg["splits"]["near_duplicate_max_hamming"]))
    return pd.DataFrame(obs_rows), media, sources, exceptions


def assign_duplicate_groups(media: pd.DataFrame, salt: bytes,
                            max_hamming: int = 6) -> pd.Series:
    """Cluster objects into near-duplicate groups - the unit of Equation (5).

    Exact SHA-256 equality collapses byte-identical redeliveries. Beyond that,
    objects of the same media type whose perceptual hashes lie within
    ``max_hamming`` bits are joined by union-find, so a chain of successive
    re-encodings ends up in one group rather than in a chain of pairs.

    The grouping is what the split builder uses to keep a re-encoded copy of a
    recording out of the partition that its original is not in; without it, the
    same content appears in train and test and every score is optimistic.
    """
    # Objects whose content is degenerate - a silent recording, a saturated
    # frame - are matched on byte identity only. A perceptual hash of silence is
    # a hash of nothing: every silent object is perceptually identical to every
    # other, so including them would merge unrelated events into one enormous
    # duplicate group and, through the split constraint, drag half the corpus
    # into a single partition.
    DEGENERATE = {"silence", "clipping", "over_exposure", "under_exposure"}

    parent: Dict[int, int] = {i: i for i in range(len(media))}

    def find(a: int) -> int:
        while parent[a] != a:
            parent[a] = parent[parent[a]]
            a = parent[a]
        return a

    def union(a: int, b: int) -> None:
        ra, rb = find(a), find(b)
        if ra != rb:
            parent[max(ra, rb)] = min(ra, rb)

    idx = media.reset_index(drop=True)
    by_digest: Dict[str, int] = {}
    for i, digest in enumerate(idx["sha256"]):
        if digest in by_digest:
            union(by_digest[digest], i)
        else:
            by_digest[digest] = i

    def degenerate(i: int) -> bool:
        flags = set(str(idx.at[i, "quality_flags"] or "").split(";")) - {""}
        return bool(flags & DEGENERATE)

    for _, block in idx.groupby("media_type").groups.items():
        members = [i for i in block if not degenerate(i)]
        hashes = [idx.at[i, "_phash"] for i in members]
        for a in range(len(members)):
            for b in range(a + 1, len(members)):
                if media_qc.hamming(hashes[a], hashes[b]) <= max_hamming:
                    union(members[a], members[b])

    roots = [find(i) for i in range(len(idx))]
    labels = {}
    for r in sorted(set(roots)):
        members = [idx.at[i, "object_id"] for i in range(len(idx)) if roots[i] == r]
        labels[r] = ids.group_key(salt, members)
    return pd.Series([labels[r] for r in roots], index=media.index)


def ingest_episode_log(path: Path, cfg: Config, salt: bytes, t0_ns: int
                       ) -> Tuple[pd.DataFrame, pd.DataFrame, List[dict], Dict[str, str]]:
    """Anchor the events that S1 never produced.

    Returns (events, observations, source registry, native run -> event_id).
    These events carry no reference trajectory, so no kinematic ground truth is
    derivable for them; the omission is represented as ``not_observed`` in the
    label table rather than filled by inference from the media.
    """
    rot = int(cfg.release["rotation_policy_days"])
    sigma_ms = float(cfg["synchronization"]["clock_uncertainty_ms"]["site_ntp"])

    events: List[dict] = []
    observations: List[dict] = []
    sources: List[dict] = []
    mapping: Dict[str, str] = {}

    for rec in read_jsonl(path):
        native = rec["native_run_id"]
        kind = rec["episode_kind"]
        eid = ids.event_id(salt, "OBS" if kind != "negative_control" else "NEG", native)
        mapping[native] = eid
        t_start = tb.rfc3339_to_ns(rec["episode_start"])
        t_end = tb.rfc3339_to_ns(rec["episode_end"])

        events.append({
            "event_id": eid,
            "event_kind": kind,
            "t_start_utc_ns": t_start,
            "t_end_utc_ns": t_end,
            "t_precision_ms": 10.0,
            "t_uncertainty_ms": float(rec["clock_sigma_ms"]),
            "zone_id": cfg["zone"]["name"],
            "location_cell": "SITE_GENERALIZED",
            "site_group_id": rec["site_group"],
            "campaign_id": "OBS-1" if kind != "negative_control" else "NEG-1",
            "route_family": None,
            "hard_negative_type": rec.get("negative_type"),
            "access_tier": "open",
        })

        epoch = rotation_epoch(t_start, t0_ns, rot)
        sid = ids.rotating_source_id(salt, f"site::{rec['site_code']}", epoch)
        register_source(sources, sid, "site_ntp", "image", "ntp", sigma_ms,
                        "site_episode_log", "site_operating_permission", 1825, epoch)
        observations.append({
            "observation_id": ids.observation_id(salt, sid, f"episode::{native}"),
            "event_id": eid, "window_id": None, "source_id": sid, "stream": "S4",
            "modality": "image",
            "t_native_utc_ns": t_start, "t_ingest_utc_ns": t_end,
            "clock_offset_ns": 0,
            "clock_offset_sigma_ns": tb.seconds_to_ns(sigma_ms / 1000.0),
            "t_corrected_utc_ns": t_start, "sync_error_ns": None,
            "obs_start_utc_ns": t_start, "obs_end_utc_ns": t_end,
            "location_cell": "SITE_GENERALIZED", "object_uri": None,
            "perceived_direction": None, "reporter_confidence": None,
            "source_event_id_hash": ids.source_event_id_hash(salt, f"episode::{native}"),
            "access_tier": "open", "missing_reason": "not_applicable",
        })
    return (pd.DataFrame(events), pd.DataFrame(observations), sources, mapping)
