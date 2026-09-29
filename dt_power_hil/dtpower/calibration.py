"""E00 — calibration procedure of section 8.1 and uncertainty budget (16.5).

The same functions drive (a) the emulated calibration and (b) the generation
of blank measurement protocols for the physical bench: calibration points,
expected LSB/range and acceptance limits are derived from the datasheet
characteristics in configs/hardware_bench_12v.json.
"""
from __future__ import annotations

import math

import numpy as np

from .sensors import PowerMonitorChannel

TARGET_V_REL = 0.005      # 0.5 % of reading (section 8.1)
TARGET_I_REL = 0.01       # 1 % of reading
TARGET_E_REL = 0.02       # 2 % on control integral


def calibration_levels(ch_cfg: dict, n: int = 5) -> list[float]:
    lo, hi = ch_cfg["i_expected_a"]
    if lo < 0:  # bidirectional: symmetric-ish charge and discharge points
        neg = list(np.linspace(lo, lo / 4, 2))
        pos = list(np.linspace(hi / 4, hi, 2))
        return [round(x, 3) for x in neg + [0.5 * hi / 4] + pos]
    return [round(x, 3) for x in np.linspace(hi / n, hi, n)]


def run_calibration(ch: PowerMonitorChannel, ch_cfg: dict, std: dict, rng: np.random.Generator,
                    v_level: float = 13.2, samples: int = 600) -> dict:
    """Emulated E00: zero series, 5 levels, fit on odd levels, verify on even ones."""
    zero_i, _, _ = ch.sample(np.zeros(samples), np.full(samples, v_level), calibrated=False)
    zero_offset = float(np.mean(zero_i))
    levels = calibration_levels(ch_cfg)
    rows = []
    for lvl in levels:
        i_true = np.full(samples, lvl)
        i_raw, v_raw, sat = ch.sample(i_true, np.full(samples, v_level), calibrated=False)
        i_std = lvl * (1 + rng.normal(0, std["u_i_rel_k2"] / 2)) + rng.normal(0, std["u_i_abs_k2_a"] / 2)
        v_std = v_level * (1 + rng.normal(0, std["u_v_rel_k2"] / 2))
        rows.append({"level_a": lvl, "i_std": i_std, "i_dut_mean": float(i_raw.mean()), "i_dut_sd": float(i_raw.std(ddof=1)),
                     "v_std": v_std, "v_dut_mean": float(v_raw.mean()), "saturated": bool(sat.any())})
    fit_idx = [0, 2, 4]
    ver_idx = [1, 3]
    x = np.array([rows[k]["i_dut_mean"] for k in fit_idx])
    y = np.array([rows[k]["i_std"] for k in fit_idx])
    a_i, b_i = np.polyfit(x, y, 1)
    xv = np.array([r["v_dut_mean"] for r in rows])
    yv = np.array([r["v_std"] for r in rows])
    # voltage: single-level gain+offset against standard over a second level at 12.0 V
    _, v2, _ = ch.sample(np.zeros(samples), np.full(samples, 12.0), calibrated=False)
    v2_std = 12.0 * (1 + rng.normal(0, std["u_v_rel_k2"] / 2))
    a_v, b_v = np.polyfit(np.r_[xv.mean(), v2.mean()], np.r_[yv.mean(), v2_std], 1)
    ch.cal_a_i, ch.cal_b_i, ch.cal_a_v, ch.cal_b_v = float(a_i), float(b_i), float(a_v), float(b_v)
    for r in rows:
        r["i_cal"] = a_i * r["i_dut_mean"] + b_i
        r["residual_a"] = r["i_cal"] - r["i_std"]
        r["residual_rel"] = r["residual_a"] / r["i_std"] if abs(r["i_std"]) > 1e-9 else float("nan")
    ver = [rows[k] for k in ver_idx]
    max_ver_rel = max(abs(r["residual_rel"]) for r in ver)
    return {"channel": ch.name, "zero_offset_raw_a": zero_offset, "a_i": float(a_i), "b_i": float(b_i),
            "a_v": float(a_v), "b_v": float(b_v), "levels": rows,
            "max_verification_rel": float(max_ver_rel),
            "pass_current": bool(max_ver_rel <= TARGET_I_REL)}


def uncertainty_budget(ch_cfg: dict, ic: dict, shunt: dict, std: dict, i_op: float, v_op: float = 13.0,
                       dT: float = 5.0, n_avg: int = 10, residual_rel: float = 0.0) -> dict:
    """Standard uncertainty components (k=1) of a calibrated 1-s telemetry value."""
    r = shunt["r_ohm"]
    comps = {
        "standard_I": std["u_i_rel_k2"] / 2 * abs(i_op) + std["u_i_abs_k2_a"] / 2,
        "calibration_fit_residual": abs(residual_rel) * abs(i_op) / math.sqrt(3),
        "quantisation": ic["shunt_lsb_v"] / r / math.sqrt(12) / math.sqrt(n_avg),
        "noise_1s_mean": ic["shunt_noise_rms_v"] / r / math.sqrt(n_avg),
        "shunt_tcr": shunt["tcr_ppm"] * 1e-6 * dT * abs(i_op) / math.sqrt(3),
        "residual_offset_after_zero": 0.25 * ic["shunt_offset_max_v"] / r / math.sqrt(3),
    }
    u_i = math.sqrt(sum(v * v for v in comps.values()))
    comps_v = {
        "standard_V": std["u_v_rel_k2"] / 2 * v_op,
        "quantisation": ic["bus_lsb_v"] / math.sqrt(12) / math.sqrt(n_avg),
        "noise_1s_mean": ic["bus_noise_rms_v"] / math.sqrt(n_avg),
        "residual_gain_offset": 0.1 * ic["bus_gain_err_max"] * v_op / math.sqrt(3) + 0.1 * ic["bus_offset_max_v"] / math.sqrt(3),
    }
    u_v = math.sqrt(sum(v * v for v in comps_v.values()))
    p = abs(v_op * i_op)
    u_p = p * math.sqrt((u_v / v_op) ** 2 + (u_i / abs(i_op)) ** 2) if abs(i_op) > 1e-6 else float("nan")
    return {"i_op_a": i_op, "v_op_v": v_op, "u_i_a": u_i, "U_i_a_k2": 2 * u_i, "U_i_rel_k2": 2 * u_i / abs(i_op) if i_op else float("nan"),
            "u_v_v": u_v, "U_v_rel_k2": 2 * u_v / v_op, "U_p_rel_k2": 2 * u_p / p if p else float("nan"),
            "components_i": comps, "components_v": comps_v}


def channel_protocol_row(name: str, hw: dict) -> dict:
    """Derived characteristics used to fill a blank measurement protocol."""
    ch = hw["channels"][name]
    ic = hw["sensors"][ch["meter"]]
    sh = hw["shunts"][ch["shunt"]]
    r = sh["r_ohm"]
    i_fs = ic["shunt_range_v"] / r
    lo, hi = ch["i_expected_a"]
    i_max = max(abs(lo), abs(hi))
    return {
        "channel": name, "location": ch["where"], "meter": ch["meter"], "shunt": ch["shunt"], "r_shunt_mohm": r * 1e3,
        "i_full_scale_a": i_fs, "i_lsb_ma": ic["shunt_lsb_v"] / r * 1e3, "v_lsb_mv": ic["bus_lsb_v"] * 1e3,
        "v_max_ic_v": ic["bus_max_v"], "i_expected_a": ch["i_expected_a"], "headroom_pct": 100 * (1 - i_max / i_fs),
        "p_shunt_max_w": i_max ** 2 * r, "u_shunt_max_mv": i_max * r * 1e3,
        "offset_max_ma": ic["shunt_offset_max_v"] / r * 1e3,
        "uncal_gain_err_max_pct": 100 * (ic["shunt_gain_err_max"] + sh["class_tol"]),
        "calibration_levels_a": calibration_levels(ch),
        "accept_v_rel_pct": TARGET_V_REL * 100, "accept_i_rel_pct": TARGET_I_REL * 100,
        "accept_i_abs_near_zero_ma": 5 * ic["shunt_lsb_v"] / r * 1e3 + ic["shunt_offset_max_v"] / r * 1e3,
    }
