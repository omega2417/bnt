"""Analytical sizing of the article (eqs. B.4–B.7)."""
from __future__ import annotations

import numpy as np


def daily_energy(p_base: float, p_light: float, light_hours: float, eta_dc: float):
    e_load = p_base * 24 + p_light * light_hours
    return e_load, e_load / eta_dc


def battery_requirement(e_src: float, n_aut: float, dod: float, k_t: float, eta_dis: float):
    """Nominal battery energy for N_aut days (B.5). Reproduces 1772.9 Wh for S1."""
    return e_src * n_aut / (dod * k_t * eta_dis)


def pv_requirement(e_src: float, psh: float, k_der: float, margin: float):
    """Lower bound of PV peak power with design margin (B.6)."""
    return e_src * (1 + margin) / (psh * k_der)


def line_loss_ratio(v_bus: float, v_ref: float = 12.0) -> float:
    """I^2R loss for equal power and cable relative to v_ref (B.7)."""
    return (v_ref / v_bus) ** 2


def size_scenario(sc: dict, common: dict) -> dict:
    e_load, e_src = daily_energy(sc["p_base_w"], common["p_light_w"], common["light_hours"], sc["eta_dc"])
    e_batt = battery_requirement(e_src, common["n_aut_days"], common["dod"], common["k_t"], common["eta_dis"])
    return {
        "e_load_day": e_load,
        "e_src_day": e_src,
        "e_batt_req": e_batt,
        "c_ah": e_batt / sc["v_bus"],
        "p_pv": pv_requirement(e_src, common["psh_design"], common["k_der"], common["margin"]),
        "loss_ratio_vs_12v": line_loss_ratio(sc["v_bus"]),
        "i_bus_mean_a": e_src / 24 / sc["v_bus"],
    }


def sensitivity(common: dict, p_base: float = 18.0, v_bus: float = 12.0,
                psh_values=(1.2, 1.8, 2.5), eta_values=(0.85, 0.90, 0.95)):
    rows = []
    for eta in eta_values:
        _, e_src = daily_energy(p_base, common["p_light_w"], common["light_hours"], eta)
        row = {"eta_dc": eta}
        for psh in psh_values:
            row[f"wp_psh_{psh}"] = pv_requirement(e_src, psh, common["k_der"], common["margin"])
        row["c_ah"] = battery_requirement(e_src, common["n_aut_days"], common["dod"], common["k_t"], common["eta_dis"]) / v_bus
        rows.append(row)
    return rows


def sensitivity_grid(common: dict, p_base=18.0, psh=np.linspace(1.0, 3.0, 9), eta=np.linspace(0.82, 0.98, 9)):
    grid = np.zeros((len(eta), len(psh)))
    for i, e in enumerate(eta):
        _, e_src = daily_energy(p_base, common["p_light_w"], common["light_hours"], e)
        for j, p in enumerate(psh):
            grid[i, j] = pv_requirement(e_src, p, common["k_der"], common["margin"])
    return psh, eta, grid
