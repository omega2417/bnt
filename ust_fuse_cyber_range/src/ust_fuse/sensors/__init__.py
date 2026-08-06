"""Sensor models for the digital twin."""
from __future__ import annotations

from ..config import SensorConfig
from .base import Sensor
from .radar import RadarSensor
from .eo_ir import EOIRSensor
from .rf_sdr import RFSDRSensor
from .acoustic import AcousticSensor

_REGISTRY = {
    "radar": RadarSensor,
    "eo_ir": EOIRSensor,
    "rf_sdr": RFSDRSensor,
    "acoustic": AcousticSensor,
}


def build_sensor(cfg: SensorConfig) -> Sensor:
    """Instantiate the concrete sensor class for a :class:`SensorConfig`."""
    cls = _REGISTRY.get(cfg.sensor_type, RadarSensor)
    return cls(cfg)


__all__ = [
    "Sensor",
    "RadarSensor",
    "EOIRSensor",
    "RFSDRSensor",
    "AcousticSensor",
    "build_sensor",
]
