"""Passive RF / SDR receiver.

A software-defined-radio receiver used for *passive* RF observation only
(proposal section 7: "Пасивні RF-спостереження ... без створення перешкод").
It only sees RF-emitting UAVs (``rf_active``), gives a coarse bearing and an RF
class label, and never transmits — matching the proposal's safety constraint
that active jamming is out of scope (section 12).
"""
from __future__ import annotations

import numpy as np

from ..datatypes import GroundTruth
from .base import Sensor


class RFSDRSensor(Sensor):
    archetype = "rf_sdr"

    def _target_visible(self, gt: GroundTruth, t: float) -> bool:
        # silent / non-emitting platforms are invisible to a passive receiver
        return bool(gt.rf_active)

    def _class_label(self, gt: GroundTruth, rng_stream) -> str:
        # RF fingerprint: emitting vs control-link type, coarse but useful for
        # association support in fusion.
        if rng_stream.random() < 0.75:
            return f"rf::{gt.uav_class}"
        return "rf::unknown"
