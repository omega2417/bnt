"""Energy-level SOC simulator of the article (section 9.3 of the protocol).

The limits are applied *before* the step (P_dis,allow / P_ch,allow), and any
demand that cannot be supplied is booked as unserved energy; any generation
that cannot be absorbed is booked as curtailed energy. Clipping the state
without that accounting would create energy (section 9.3).
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np


@dataclass
class EnergySimResult:
    t_h: np.ndarray
    soc: np.ndarray            # energy fraction z_E at the end of each step
    p_pv: np.ndarray
    p_dem_bus: np.ndarray
    p_served_bus: np.ndarray
    p_unserved_bus: np.ndarray
    p_curtailed: np.ndarray
    p_crit_unserved_term: np.ndarray
    p_aux_unserved_term: np.ndarray
    aux_on: np.ndarray
    step_h: float

    def metrics(self, eps_w: float = 0.5) -> dict:
        dt = self.step_h
        e_dem = float(self.p_dem_bus.sum() * dt)
        e_uns = float(self.p_unserved_bus.sum() * dt)
        lolh = float(((self.p_unserved_bus > eps_w).sum()) * dt)
        crit_uns = float(self.p_crit_unserved_term.sum() * dt)
        aux_uns = float(self.p_aux_unserved_term.sum() * dt)
        return {
            "min_soc": float(self.soc.min()),
            "t_min_soc_h": float(self.t_h[int(self.soc.argmin())]),
            "final_soc": float(self.soc[-1]),
            "lolh_h": lolh,
            "lpsp_e": e_uns / e_dem if e_dem > 0 else 0.0,
            "e_unserved_bus_wh": e_uns,
            "e_unserved_critical_wh": crit_uns,
            "e_unserved_aux_wh": aux_uns,
            "e_curtailed_wh": float(self.p_curtailed.sum() * dt),
            "e_pv_available_wh": float(self.p_pv.sum() * dt),
            "e_demand_bus_wh": e_dem,
            "aux_on_hours": float(self.aux_on.sum() * dt),
        }


def simulate(pv_w, crit_term_w, aux_term_w, *, e_eff_wh, eta_dc, eta_ch, eta_dis,
             soc0=1.0, soc_min=0.15, soc_max=1.0, step_h=1.0,
             p_ch_max=np.inf, p_dis_max=np.inf, aux_policy=None,
             critical_priority=True) -> EnergySimResult:
    """Simulate one trajectory.

    aux_policy(k, soc, history) -> bool may veto the scheduled auxiliary load;
    it only receives the past (k, current soc) — never the future profile.
    """
    n = len(pv_w)
    e = soc0 * e_eff_wh
    e_min, e_max = soc_min * e_eff_wh, soc_max * e_eff_wh
    out = {k: np.zeros(n) for k in ("soc", "dem", "srv", "uns", "curt", "cu", "au", "aux")}
    for k in range(n):
        aux_sched = aux_term_w[k]
        aux_allowed = True if aux_policy is None else bool(aux_policy(k, e / e_eff_wh))
        aux_req = aux_sched if aux_allowed else 0.0
        dem_crit_bus = crit_term_w[k] / eta_dc
        dem_aux_bus = aux_req / eta_dc
        dem_bus = dem_crit_bus + dem_aux_bus
        # Unserved accounting uses the policy-independent desired demand.
        desired_bus = dem_crit_bus + aux_sched / eta_dc
        net = pv_w[k] - dem_bus
        if net >= 0:
            p_ch_allow = max(0.0, min(p_ch_max, (e_max - e) / (eta_ch * step_h)))
            p_ch = min(net, p_ch_allow)
            curt = net - p_ch
            e += eta_ch * p_ch * step_h
            served = dem_bus
        else:
            need = -net
            p_dis_allow = max(0.0, min(p_dis_max, eta_dis * (e - e_min) / step_h))
            p_dis = min(need, p_dis_allow)
            e -= p_dis / eta_dis * step_h
            served = pv_w[k] + p_dis
            curt = 0.0
        e = min(max(e, e_min), e_max)  # guards float error only; limits were applied above
        short_bus = max(0.0, dem_bus - served)
        if critical_priority:
            crit_short = min(short_bus, dem_crit_bus)
            aux_short = short_bus - crit_short
        else:
            share = dem_crit_bus / dem_bus if dem_bus > 0 else 0
            crit_short, aux_short = short_bus * share, short_bus * (1 - share)
        aux_short += (aux_sched - aux_req) / eta_dc  # vetoed light counts as aux unserved
        out["soc"][k] = e / e_eff_wh
        out["dem"][k] = desired_bus
        out["srv"][k] = desired_bus - short_bus - (aux_sched - aux_req) / eta_dc
        out["uns"][k] = short_bus + (aux_sched - aux_req) / eta_dc
        out["curt"][k] = curt
        out["cu"][k] = crit_short * eta_dc
        out["au"][k] = aux_short * eta_dc
        out["aux"][k] = 1.0 if (aux_req > 0 and aux_short * eta_dc < aux_req - 1e-9) else 0.0
    t = (np.arange(n) + 1) * step_h
    return EnergySimResult(t, out["soc"], np.asarray(pv_w, float), out["dem"], out["srv"], out["uns"],
                           out["curt"], out["cu"], out["au"], out["aux"], step_h)


def run_article_scenario(name: str, cfg: dict, step_s: float = 3600.0, use_nameplate_v: float | None = None,
                         battery_ah: float | None = None, aux_policy=None, soc0=None, psh_days=None):
    from . import profiles

    c, sc = cfg["common"], cfg["scenarios"][name]
    psh = psh_days if psh_days is not None else c["psh_14d"]
    pv, crit, aux = profiles.hourly_profiles(sc["pv_wp"], psh, c["k_der"], sc["p_base_w"], c["p_light_w"],
                                             c["light_on_hour"], c["light_hours"],
                                             c["pv_daylight_start_h"], c["pv_daylight_end_h"])
    if step_s != 3600:
        pv, crit, aux = (profiles.upsample(x, step_s) for x in (pv, crit, aux))
    v = use_nameplate_v if use_nameplate_v else sc["v_bus"]
    ah = battery_ah if battery_ah else sc["battery_ah"]
    e_eff = c["k_t"] * v * ah
    return simulate(pv, crit, aux, e_eff_wh=e_eff, eta_dc=sc["eta_dc"], eta_ch=c["eta_ch"], eta_dis=c["eta_dis"],
                    soc0=c["soc_initial"] if soc0 is None else soc0, soc_min=1 - c["dod"],
                    step_h=step_s / 3600.0, aux_policy=aux_policy)
