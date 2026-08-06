"""Low-cost acoustic array sensor.

A cheap short-range acoustic bearing sensor.  Useful only close in, but it adds
an independent modality for the fusion / redundancy experiments (ЛР-5).  It is
bearing-only with a short ``max_range`` and is strongly affected by wind, so its
detection probability is the most sensitive to the weather / domain scale.
"""
from __future__ import annotations

from .base import Sensor


class AcousticSensor(Sensor):
    archetype = "acoustic"
    # base bearing-only behaviour with short range already captures the physics;
    # weather sensitivity is applied through the scenario's ``pd_scale``.
