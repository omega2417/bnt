"""E09 — capacity of the permitted working interval (section 8.2).

CC-CV charge to 14.2 V / tail 0.05C, rest, CC discharge 0.25C (10 A) to
11.2 V under load (2.8 V/cell), rest, CC-CV recharge. Q is counted by the
REF channel and, separately, by M1; the coulombic efficiency is Ah_out/Ah_in.
"""
from __future__ import annotations

import numpy as np

from .battery import BatteryPlant


def _cccv(plant: BatteryPlant, chans, v_cv, i_cc, i_tail, rng, count):
    ah = {"REF": 0.0, "M1": 0.0}
    t = 0
    while t < 12 * 3600:
        e = plant.ocv() - plant.v_p
        i_allow = min(i_cc, max(0.0, (v_cv - e) / plant.truth.r0))
        i = -i_allow
        v = plant.terminal_voltage(i)
        plant.step(i, 1.0)
        if count:
            for n in ah:
                im, _, _ = chans[n].sample(np.full(10, i), np.full(10, v))
                ah[n] += -im.mean() / 3600
        t += 1
        if i_allow < i_tail:
            break
    return ah, t


def capacity_test(hw: dict, truth, chans: dict, rng: np.random.Generator) -> dict:
    b = hw["battery"]
    plant = BatteryPlant(truth=truth, z=0.5, v_uv=b["bms_undervoltage_v"], v_ov=b["bms_overvoltage_v"])
    v_cv, i_tail = b["charge_voltage_v"], 0.05 * b["nameplate_capacity_ah"]
    _cccv(plant, chans, v_cv, 20.0, i_tail, rng, count=False)
    z_full = plant.z
    for _ in range(1800):
        plant.step(0.0, 1.0)
    ah_out = {"REF": 0.0, "M1": 0.0}
    e_out = 0.0
    t_dis = 0
    i_dis = 0.25 * b["nameplate_capacity_ah"]
    while True:
        v = plant.terminal_voltage(i_dis)
        if v <= 11.2 or t_dis > 6 * 3600:
            break
        plant.step(i_dis, 1.0)
        for n in ah_out:
            im, vm, _ = chans[n].sample(np.full(10, i_dis), np.full(10, v))
            ah_out[n] += im.mean() / 3600
            if n == "REF":
                e_out += (im * vm).mean() / 3600
        t_dis += 1
    z_end = plant.z
    for _ in range(1800):
        plant.step(0.0, 1.0)
    ah_in, t_ch = _cccv(plant, chans, v_cv, 20.0, i_tail, rng, count=True)
    return {
        "q_ref_ah": ah_out["REF"], "q_m1_ah": ah_out["M1"], "e_ref_wh": e_out,
        "eta_q_ref": ah_out["REF"] / ah_in["REF"] if ah_in["REF"] > 0 else 1.0,
        "eta_q_m1": ah_out["M1"] / ah_in["M1"] if ah_in["M1"] > 0 else 1.0,
        "discharge_time_h": t_dis / 3600, "recharge_time_h": t_ch / 3600,
        "z_true_full": z_full, "z_true_end": z_end,
        "true_capacity_ah_hidden": truth.capacity_ah,
        "working_interval_fraction_true": z_full - z_end,
        "conditions": "22 C, CC 10 A (0.25C) to 11.2 V, CC-CV 20 A / 14.2 V / tail 2 A",
    }
