"""Fault injection (ЛР-5. Відмовостійкість) and red-team negative tests.

Faults are declared in the scenario as a list of dicts and applied to the raw
detection stream *after* sensing but *before* fusion.  Supported kinds:

* ``sensor_dropout``  — a sensor goes dark over a time window;
* ``packet_loss``     — random loss over a window (network-level);
* ``degradation``     — inflated noise / lowered Pd over a window;
* ``spoof``           — injected false telemetry near a true target (red-team);
* ``stuck``           — a sensor repeats its last measurement (frozen).

Each fault carries a ``t0``/``t1`` window so the timeline plots can annotate it.
"""
from __future__ import annotations

from typing import Dict, List

import numpy as np

from .datatypes import Detection, GroundTruth
from .rng import RNGHub


def _in_window(t: float, f: Dict) -> bool:
    return f.get("t0", -np.inf) <= t <= f.get("t1", np.inf)


def apply_faults(
    detections: List[Detection],
    faults: List[Dict],
    truths: List[GroundTruth],
    rng_hub: RNGHub,
) -> List[Detection]:
    """Apply the scenario's fault list to a detection stream."""
    if not faults:
        return detections
    rng = rng_hub.stream("faults")
    out: List[Detection] = []
    last_by_sensor: Dict[str, Detection] = {}

    for d in detections:
        drop = False
        for f in faults:
            kind = f.get("kind")
            if kind == "sensor_dropout" and f.get("sensor") == d.sensor_id and _in_window(d.t_true, f):
                drop = True
                break
            if kind == "packet_loss" and _in_window(d.t_true, f):
                if rng.random() < f.get("prob", 0.3):
                    drop = True
                    break
            if kind == "degradation" and f.get("sensor") == d.sensor_id and _in_window(d.t_true, f):
                scale = f.get("noise_scale", 2.0)
                d.R = d.R * scale
                d.z = d.z + rng.multivariate_normal(np.zeros(3), d.R * 0.1)
            if kind == "stuck" and f.get("sensor") == d.sensor_id and _in_window(d.t_true, f):
                prev = last_by_sensor.get(d.sensor_id)
                if prev is not None:
                    d.z = prev.z.copy()
        if not drop:
            last_by_sensor[d.sensor_id] = d
            out.append(d)

    # red-team spoofing: fabricate plausible-but-fake detections
    for f in faults:
        if f.get("kind") != "spoof":
            continue
        sensor = f.get("sensor")
        n = int(f.get("count", 20))
        for _ in range(n):
            t = rng.uniform(f.get("t0", 0.0), f.get("t1", 1.0))
            gt = truths[int(rng.integers(0, len(truths)))]
            p = gt.position_at(t)
            if p is None:
                continue
            z = p + rng.normal(0, f.get("offset_m", 40.0), size=3)
            src = next((d for d in out if d.sensor_id == sensor), None)
            R = (src.R.copy() if src is not None else np.eye(3) * 100.0)
            out.append(
                Detection(
                    t_true=t, t_stamp=t, t_arrive=t,
                    sensor_id=sensor or "SPOOF",
                    sensor_type="spoof",
                    z=z, R=R, snr_db=20.0, truth_id=-1,
                    detected_class="spoofed",
                    meta={"spoof": True},
                )
            )
    out.sort(key=lambda x: x.t_true)
    return out


def fault_windows(faults: List[Dict]) -> List[Dict]:
    """Return a compact description of faults for timeline annotation."""
    return [
        {
            "kind": f.get("kind"),
            "sensor": f.get("sensor", "*"),
            "t0": f.get("t0", 0.0),
            "t1": f.get("t1", 0.0),
        }
        for f in faults
    ]
