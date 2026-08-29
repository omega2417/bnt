"""S1 - takeoff indication events from the controlled area.

S1 is the only stream that carries authorized ground truth, and it is therefore
the only one allowed to anchor a ``controlled_flight`` event. Two properties make
it different from the other three:

* its clock is disciplined to GNSS, so it defines the reference against which
  Equation (3) is evaluated for every other stream attached to the same event;
* it arrives with a reference trajectory, from which Equations (1) and (2) are
  computed. The trajectory itself is controlled-tier: only derived quantities -
  boundary distance, direction, warning time, all at published resolution -
  reach the open tier.

The operational run identifier never enters the repository. It is replaced by a
keyed hash so that a duplicate delivery of the same run is still detectable.
"""

from __future__ import annotations

from pathlib import Path
from typing import Dict, List, Tuple

import numpy as np
import pandas as pd

from .. import geometry, ids, timebase as tb
from ..config import Config
from .common import generalize_cell, read_jsonl, register_source, rotation_epoch


def ingest(path: Path, raw_root: Path, cfg: Config, salt: bytes,
           zone: geometry.WarningZone, t0_ns: int
           ) -> Tuple[pd.DataFrame, pd.DataFrame, List[dict], Dict[str, dict]]:
    """Return (events, observations, source registry, per-event kinematics)."""
    res = float(cfg.release["public_spatial_resolution_m"])
    rot = int(cfg.release["rotation_policy_days"])
    delta_t = cfg.delta_t_s
    eps = cfg.epsilon_m

    events: List[dict] = []
    observations: List[dict] = []
    sources: List[dict] = []
    kinematics: Dict[str, dict] = {}

    for rec in read_jsonl(path):
        native = rec["native_run_id"]
        t_start = tb.rfc3339_to_ns(rec["track_start_time"])
        t_end = tb.rfc3339_to_ns(rec["track_end_time"])
        t_takeoff = tb.rfc3339_to_ns(rec["takeoff_time"])
        eid = ids.event_id(salt, rec["campaign_id"], native)

        track = pd.read_csv(raw_root / rec["track_csv"])
        xy = track[["east_m", "north_m"]].to_numpy()
        t_s = track["t_s"].to_numpy()
        d = zone.boundary_distance(xy)
        sd = zone.signed_boundary_distance(xy)
        t_cross = geometry.crossing_time(t_s, sd)
        direction = geometry.direction_labels(t_s, d, delta_t, eps)
        T = geometry.warning_time(t_s, t_cross)
        t_cpa, d_cpa = geometry.closest_point_of_approach(t_s, d)

        kinematics[eid] = {
            "event_id": eid,
            "t_s": t_s, "d_m": d, "signed_d_m": sd, "xy": xy,
            "direction": direction, "warning_time_s": T,
            "t_cross_s": t_cross, "t_cpa_s": t_cpa, "d_cpa_m": d_cpa,
            "platform_class": rec["platform_class"],
            "approach_geometry": rec["approach_geometry"],
            "speed_band": rec["speed_band"],
            "altitude_band": rec["altitude_band"],
            "closing_speed_ms": float(-np.nanmin(geometry.radial_speed(t_s, d))),
            "t_start_ns": t_start,
        }

        # The event is anchored on the takeoff indication, not on the first
        # trajectory sample: the indication is what an operational system would
        # actually receive first, and the pre-indication interval is exactly the
        # lead time the dataset is meant to characterize.
        events.append({
            "event_id": eid,
            "event_kind": "controlled_flight",
            "t_start_utc_ns": t_takeoff,
            "t_end_utc_ns": t_end,
            "t_precision_ms": 1.0,
            "t_uncertainty_ms": float(rec["clock_sigma_ms"]),
            "zone_id": cfg["zone"]["name"],
            "location_cell": generalize_cell(xy[0, 0], xy[0, 1], res),
            "site_group_id": rec["site_group"],
            "campaign_id": rec["campaign_id"],
            "route_family": f"{rec['approach_geometry']}|{rec['speed_band']}",
            "hard_negative_type": None,
            "access_tier": "open",
        })

        epoch = rotation_epoch(t_start, t0_ns, rot)
        sid = ids.rotating_source_id(salt, f"controlled-area::{rec['site_code']}", epoch)
        register_source(sources, sid, "site_ptp", "takeoff_event", "gnss_pps",
                        float(rec["clock_sigma_ms"]), "authorized_operations_log",
                        "operating_authorization", 3650, epoch)

        observations.append({
            "observation_id": ids.observation_id(salt, sid, native),
            "event_id": eid,
            "window_id": None,
            "source_id": sid,
            "stream": "S1",
            "modality": "takeoff_event",
            "t_native_utc_ns": t_takeoff,
            "t_ingest_utc_ns": t_takeoff + tb.seconds_to_ns(0.4),
            "clock_offset_ns": 0,
            "clock_offset_sigma_ns": tb.seconds_to_ns(rec["clock_sigma_ms"] / 1000.0),
            "t_corrected_utc_ns": t_takeoff,
            "sync_error_ns": 0,
            "obs_start_utc_ns": t_takeoff,
            "obs_end_utc_ns": t_end,
            "location_cell": generalize_cell(xy[0, 0], xy[0, 1], res),
            "object_uri": None,
            "perceived_direction": None,
            "reporter_confidence": None,
            "source_event_id_hash": ids.source_event_id_hash(salt, native),
            "access_tier": "open",
            "missing_reason": "not_applicable",
            "_native_run_id": native,
        })

    return (pd.DataFrame(events), pd.DataFrame(observations), sources, kinematics)
