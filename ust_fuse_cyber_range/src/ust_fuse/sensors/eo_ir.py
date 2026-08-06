"""Electro-optical / infra-red (PTZ / network camera) sensor.

A low-cost owned camera (proposal section 7).  It is *bearing-only* — very
precise in azimuth/elevation but with essentially no range, so its ENU
covariance is a thin needle along the line of sight.  It can classify the UAV
(multirotor / fixed-wing / fpv) with weather-dependent reliability (ЛР-6).
"""
from __future__ import annotations

import numpy as np

from ..datatypes import GroundTruth
from .base import Sensor


class EOIRSensor(Sensor):
    archetype = "eo_ir"

    def _class_label(self, gt: GroundTruth, rng_stream) -> str:
        # correct classification with probability that degrades for small/fast UAVs
        base = {"multirotor": 0.9, "fixedwing": 0.88, "fpv": 0.7,
                "silent_glider": 0.8}.get(gt.uav_class, 0.6)
        if rng_stream.random() < base:
            return gt.uav_class
        others = ["multirotor", "fixedwing", "fpv", "silent_glider"]
        others = [o for o in others if o != gt.uav_class]
        return str(rng_stream.choice(others))
