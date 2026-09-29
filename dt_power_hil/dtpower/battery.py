"""Equivalent-circuit LiFePO4 pack used as the *emulated physical plant*.

The plant has hidden "true" parameters drawn per bench instance; the twin and
the EMS never read them directly (section 3.3: plant and controller models must
not be identical copies with identical hidden parameters).
Sign convention (section 9.1): positive current = discharge.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field

import numpy as np

# Typical LiFePO4 cell OCV (V) vs charge SOC at 25 °C; plateau 3.28-3.33 V.
OCV_SOC = np.array([0.0, 0.05, 0.10, 0.20, 0.30, 0.40, 0.50, 0.60, 0.70, 0.80, 0.90, 0.95, 1.00])
OCV_CELL = np.array([2.80, 3.10, 3.20, 3.25, 3.28, 3.29, 3.30, 3.31, 3.32, 3.33, 3.35, 3.40, 3.55])


def ocv_pack(z: float, n_series: int = 4) -> float:
    return n_series * float(np.interp(z, OCV_SOC, OCV_CELL))


def docv_dz(z: float, n_series: int = 4, h: float = 0.01) -> float:
    return (ocv_pack(min(1.0, z + h), n_series) - ocv_pack(max(0.0, z - h), n_series)) / (min(1.0, z + h) - max(0.0, z - h))


@dataclass
class BatteryTruth:
    capacity_ah: float
    r0: float
    r1: float
    c1: float
    eta_q: float
    n_series: int = 4
    ocv_shift_v: float = 0.0   # unit-to-unit OCV offset, unknown to the twin


@dataclass
class BatteryPlant:
    truth: BatteryTruth
    z: float                    # true charge SOC
    temp_c: float = 22.0
    v_p: float = 0.0
    bms_open: bool = False
    v_uv: float = 10.0
    v_ov: float = 14.6
    i_ch_max: float = 20.0
    i_dis_max: float = 40.0
    ah_throughput: float = field(default=0.0)

    def ocv(self) -> float:
        return ocv_pack(self.z, self.truth.n_series) + self.truth.ocv_shift_v

    def solve_current(self, p_net_w: float) -> tuple[float, float]:
        """Current and terminal voltage delivering p_net_w (>0 discharge)."""
        e = self.ocv() - self.v_p
        r = self.truth.r0
        disc = e * e - 4 * r * p_net_w
        if disc < 0:  # requested power beyond the maximum transferable power
            i = e / (2 * r)
        else:
            i = (e - math.sqrt(disc)) / (2 * r)
        return i, e - i * r

    def terminal_voltage(self, i: float) -> float:
        return self.ocv() - self.v_p - i * self.truth.r0

    def step(self, i: float, dt: float) -> None:
        tr = self.truth
        if self.bms_open:
            i = 0.0
        q = tr.capacity_ah * 3600.0
        if i >= 0:
            self.z -= i * dt / q
        else:
            self.z += tr.eta_q * (-i) * dt / q
        self.z = min(max(self.z, 0.0), 1.0)
        a = math.exp(-dt / (tr.r1 * tr.c1))
        self.v_p = a * self.v_p + tr.r1 * (1 - a) * i
        self.ah_throughput += abs(i) * dt / 3600.0
        v = self.terminal_voltage(i)
        if v < self.v_uv or v > self.v_ov:
            self.bms_open = True


def draw_truth(hw: dict, rng: np.random.Generator) -> BatteryTruth:
    t = hw["battery"]["emulation_truth"]
    return BatteryTruth(
        capacity_ah=float(rng.normal(t["capacity_ah_mean"], t["capacity_ah_sd"])),
        r0=float(max(0.008, rng.normal(t["r0_ohm_mean"], t["r0_ohm_sd"]))),
        r1=t["r1_ohm"], c1=t["c1_f"], eta_q=t["coulombic_eff"],
        ocv_shift_v=float(rng.normal(0.0, 0.02)),
    )
