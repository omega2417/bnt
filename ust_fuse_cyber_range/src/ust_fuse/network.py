"""Network transport emulation (latency, jitter, packet loss).

Emulates the modest campus network of the budget range (proposal section 7,
"Мережеве обладнання").  It perturbs the *arrival* time of each detection at the
fusion node and can drop packets, which the fault-tolerance lab (ЛР-5) exploits.
"""
from __future__ import annotations

from typing import List

import numpy as np

from .datatypes import Detection
from .rng import RNGHub


def transport(
    detections: List[Detection],
    rng_hub: RNGHub,
    packet_loss: float = 0.0,
    jitter_ms: float = 3.0,
    extra_latency_ms: float = 0.0,
) -> List[Detection]:
    """Apply per-detection latency, jitter and random packet loss.

    Returns a new list (dropped packets removed), with ``t_arrive`` populated.
    """
    rng = rng_hub.stream("network")
    out: List[Detection] = []
    for d in detections:
        if packet_loss > 0.0 and rng.random() < packet_loss:
            continue
        base = d.meta.get("_base_latency_ms")
        if base is None:
            base = extra_latency_ms
        lat = (base + extra_latency_ms) * 1e-3
        jit = abs(rng.normal(0.0, jitter_ms * 1e-3))
        d.t_arrive = d.t_true + lat + jit
        out.append(d)
    # deliver in arrival order, as a real queue would
    out.sort(key=lambda x: x.t_arrive)
    return out
