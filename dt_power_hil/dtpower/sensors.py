"""Emulation of the real measurement chain from datasheet characteristics.

Each channel = shunt (class tolerance, TCR) + power monitor IC (offset, gain
error, noise, LSB quantisation, full-scale saturation). Per-device errors are
drawn uniformly inside the datasheet max limits, i.e. a worst-case-bounded but
random unit, then partly removed by the E00 calibration (calibration.py).
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np


@dataclass
class ChannelErrors:
    shunt_rel: float        # (R_true - R_nom)/R_nom
    shunt_offset_v: float
    shunt_gain: float
    bus_offset_v: float
    bus_gain: float


@dataclass
class PowerMonitorChannel:
    name: str
    ic: dict
    r_nom: float
    err: ChannelErrors
    rng: np.random.Generator
    cal_a_i: float = 1.0      # calibration: I_cal = a*I_raw + b
    cal_b_i: float = 0.0
    cal_a_v: float = 1.0
    cal_b_v: float = 0.0
    sign: int = 1             # wiring polarity; -1 emulates a reversed shunt (E07 sign test)

    @property
    def i_range(self) -> float:
        return self.ic["shunt_range_v"] / self.r_nom

    @property
    def i_lsb(self) -> float:
        return self.ic["shunt_lsb_v"] / self.r_nom

    def _raw(self, i_true: np.ndarray, v_true: np.ndarray):
        ic, e = self.ic, self.err
        v_sh = self.sign * i_true * self.r_nom * (1 + e.shunt_rel)
        v_sh = v_sh * (1 + e.shunt_gain) + e.shunt_offset_v + self.rng.normal(0, ic["shunt_noise_rms_v"], np.shape(i_true))
        sat = np.abs(v_sh) >= ic["shunt_range_v"]
        v_sh = np.clip(v_sh, -ic["shunt_range_v"], ic["shunt_range_v"])
        v_sh = np.round(v_sh / ic["shunt_lsb_v"]) * ic["shunt_lsb_v"]
        vb = v_true * (1 + e.bus_gain) + e.bus_offset_v + self.rng.normal(0, ic["bus_noise_rms_v"], np.shape(v_true))
        vb = np.clip(vb, 0, ic["bus_max_v"])
        vb = np.round(vb / ic["bus_lsb_v"]) * ic["bus_lsb_v"]
        return v_sh / self.r_nom, vb, sat

    def sample(self, i_true, v_true, calibrated: bool = True):
        i_raw, v_raw, sat = self._raw(np.asarray(i_true, float), np.asarray(v_true, float))
        if calibrated:
            return self.cal_a_i * i_raw + self.cal_b_i, self.cal_a_v * v_raw + self.cal_b_v, sat
        return i_raw, v_raw, sat


def make_channel(name: str, hw: dict, rng: np.random.Generator) -> PowerMonitorChannel:
    ch = hw["channels"][name]
    ic = hw["sensors"][ch["meter"]]
    sh = hw["shunts"][ch["shunt"]]
    u = lambda m: float(rng.uniform(-m, m))  # noqa: E731
    err = ChannelErrors(
        shunt_rel=u(sh["class_tol"]),
        shunt_offset_v=u(ic["shunt_offset_max_v"]),
        shunt_gain=u(ic["shunt_gain_err_max"]),
        bus_offset_v=u(ic["bus_offset_max_v"]),
        bus_gain=u(ic["bus_gain_err_max"]),
    )
    return PowerMonitorChannel(name, ic, sh["r_ohm"], err, rng)


@dataclass
class TempSensor:
    accuracy: float
    resolution: float
    bias: float
    rng: np.random.Generator

    def read(self, t_true: float) -> float:
        t = t_true + self.bias + self.rng.normal(0, self.resolution / 2)
        return round(t / self.resolution) * self.resolution


def make_temp(hw: dict, rng) -> TempSensor:
    d = hw["sensors"]["DS18B20"]
    return TempSensor(d["accuracy_c"], d["resolution_c"], float(rng.uniform(-d["accuracy_c"], d["accuracy_c"])), rng)
