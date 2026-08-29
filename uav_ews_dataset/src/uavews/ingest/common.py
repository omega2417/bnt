"""Shared helpers for the stream adapters."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, Iterator, List

import numpy as np

from .. import ids, timebase as tb


def read_jsonl(path: Path) -> Iterator[dict]:
    with open(path, "r", encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if line:
                yield json.loads(line)


def generalize_cell(east_m: float, north_m: float, resolution_m: float) -> str:
    """Snap a local-frame position to the published spatial cell.

    Truncation towards minus infinity - not rounding - is used so that the cell
    is a genuine partition of the plane: with rounding, two positions on either
    side of a cell centre would map to the same cell while the cell edges
    themselves would be ambiguous.
    """
    e = int(np.floor(float(east_m) / resolution_m))
    n = int(np.floor(float(north_m) / resolution_m))
    return f"C{e:+04d}{n:+04d}"


def rotation_epoch(t_ns: int, t0_ns: int, rotation_days: int) -> int:
    """Which pseudonym-rotation epoch a timestamp belongs to."""
    days = (int(t_ns) - int(t0_ns)) / (86_400 * tb.NS)
    return int(days // max(rotation_days, 1))


def envelope(source_id: str, source_native_id: str, salt: bytes,
             t_start_ns: int, t_end_ns: int, modality: str,
             location_cell: str, object_uri: str | None,
             rights_basis: str) -> Dict[str, object]:
    """The minimum event envelope every collection component must produce."""
    return {
        "source_id": source_id,
        "source_event_id_hash": ids.source_event_id_hash(salt, source_native_id),
        "obs_start_utc_ns": int(t_start_ns),
        "obs_end_utc_ns": int(t_end_ns),
        "modality": modality,
        "location_cell": location_cell,
        "object_uri": object_uri,
        "rights_basis": rights_basis,
    }


def register_source(registry: List[dict], source_id: str, source_class: str,
                    modality: str, sync_method: str, clock_sigma_ms: float,
                    device_profile: str, rights_basis: str,
                    retention_days: int, rotation_epoch_: int) -> None:
    """Add a source profile once; adapters call this for every record."""
    for row in registry:
        if row["source_id"] == source_id:
            return
    registry.append({
        "source_id": source_id, "source_class": source_class,
        "modality": modality, "sync_method": sync_method,
        "clock_sigma_ms": float(clock_sigma_ms),
        "device_profile": device_profile, "rights_basis": rights_basis,
        "retention_days": int(retention_days),
        "rotation_epoch": int(rotation_epoch_),
    })
