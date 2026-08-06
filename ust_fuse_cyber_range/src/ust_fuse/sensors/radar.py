"""Simulated radar sensor (the ranging anchor of the fusion pipeline).

In the budget MVP this is a *partner / rented* radar (proposal section 4:
"Симулятор радарних вимірювань + один партнерський/орендований радар").  It is
the only sensor that provides a usable range measurement, so it anchors the
Cartesian track state; the bearing-only sensors sharpen the cross-range.
"""
from __future__ import annotations

from .base import Sensor


class RadarSensor(Sensor):
    archetype = "radar"
    # The base implementation already models a ranging sensor; the radar simply
    # keeps ``provides_range=True`` and a moderate false-alarm rate.
