"""E11 — 14-day profile: SIL replication of S1–S3 and lockstep controller replay.

In controller_replay the EMS decision is converted into a command and passed
through the edge-guard contract (freshness, run_id, idempotency) before it
may change the auxiliary load. Replay is lockstep in model time, which is
*not* evidence of real-time execution (section 14.3).
"""
from __future__ import annotations

import numpy as np

from . import energy_sim, profiles
from .edge_guard import EdgeGuard


class HourlyPolicy:
    """C0/C1/C2 on the hourly energy model with a causal day-ahead PV persistence."""

    def __init__(self, name, pcfg, pv_hist_source, crit_bus, aux_bus_sched, e_eff, eta_ch, eta_dis, cold_profile):
        self.name, self.p = name, pcfg
        self.pv_src = pv_hist_source   # the simulator's realised PV; only indices < k are read
        self.crit, self.aux = crit_bus, aux_bus_sched
        self.e_eff, self.eta_ch, self.eta_dis = e_eff, eta_ch, eta_dis
        self.cold = cold_profile
        self.state = False
        self.edge = EdgeGuard("E11", "boot0", "controller_replay", 0.0, 0.0, stale_s=1e9)
        self.edge.self_test(True)
        self.edge.start(0.0)
        self.cmds = {"sent": 0, "accepted": 0, "rejected": 0}
        self.switches = 0
        self.decisions = []

    def _forecast_pv(self, k, n):
        out = np.empty(n)
        for j in range(n):
            kk = k + j - 24
            out[j] = self.pv_src[kk] if 0 <= kk < k else self.cold[(k + j) % 24]
        return out

    def _pred_min(self, k, soc, with_aux, n=6):
        pv = self._forecast_pv(k, n)
        e = soc * self.e_eff
        mn = soc
        for j in range(n):
            idx = min(k + j, len(self.crit) - 1)
            d = self.crit[idx] + (self.aux[idx] if with_aux else 0.0)
            net = pv[j] - d
            e = min(self.e_eff, e + self.eta_ch * net) if net >= 0 else e - (-net) / self.eta_dis
            mn = min(mn, e / self.e_eff)
        return mn

    def __call__(self, k, soc):
        sched = self.aux[k] > 0
        if not sched:
            want = False
        elif self.name == "C0":
            want = True
        elif self.name == "C1":
            c = self.p["C1"]
            want = (soc > c["aux_off_soc"]) if self.state else (soc >= c["aux_on_soc"])
        else:
            c = self.p["C2"]
            mn = self._pred_min(k, soc, True)
            want = (mn >= c["reserve_soc"]) if self.state else (mn >= c["return_pred_soc"] and soc >= c["return_now_soc"])
        if want != self.state:
            cmd = {"schema_version": "1.0", "mode": "controller_replay", "source": "ems", "run_id": "E11", "boot_id_target": "boot0",
                   "command_id": f"E11-{k}", "action": "SET_AUX_ON" if want else "SET_AUX_OFF",
                   "expires_at_utc": k * 3600.0 + 2.0}
            self.edge.last_hb_mono = k * 3600.0
            ack = self.edge.handle_command(k * 3600.0, cmd)
            self.cmds["sent"] += 1
            self.cmds["accepted" if ack["accepted"] else "rejected"] += 1
            if ack["accepted"]:
                self.switches += 1
                self.state = want
        return self.state


def run_e11(cfg: dict, pcfg: dict) -> dict:
    out = {"sil": {}, "sil_1min": {}, "reconciliation": [], "controller_replay": {}}
    for s in ("S1", "S2", "S3"):
        r = energy_sim.run_article_scenario(s, cfg, step_s=3600)
        out["sil"][s] = {**r.metrics(), "soc": r.soc.tolist()}
        r1 = energy_sim.run_article_scenario(s, cfg, step_s=60)
        out["sil_1min"][s] = r1.metrics()
        # nameplate 12.8/25.6/51.2 V instead of the 12/24/48 V class
        rn = energy_sim.run_article_scenario(s, cfg, step_s=3600, use_nameplate_v=cfg["scenarios"][s]["v_bus"] * 12.8 / 12)
        out["sil"][s]["min_soc_nameplate_v"] = rn.metrics()["min_soc"]
    c = cfg["common"]
    orders = {"late (protocol 10.2)": c["psh_14d"], "middle": [1.8] * 5 + [0.9] * 3 + [0.4] + [1.8] * 5,
              "early": [0.9] * 3 + [0.4] + [1.8] * 10}
    eff = {"eta_ch=eta_dis=0.95": (0.95, 0.95), "eta_rt only on charge (0.9025,1)": (0.9025, 1.0), "no battery loss (1,1)": (1.0, 1.0)}
    for on, o in orders.items():
        for en, (ec, ed) in eff.items():
            for kt in (0.95, 1.0):
                row = {"order": on, "efficiency": en, "k_t": kt}
                for s in ("S1", "S3"):
                    sc = cfg["scenarios"][s]
                    pv, cr, au = profiles.hourly_profiles(sc["pv_wp"], o, c["k_der"], sc["p_base_w"], c["p_light_w"],
                                                          c["light_on_hour"], c["light_hours"])
                    r = energy_sim.simulate(pv, cr, au, e_eff_wh=kt * sc["v_bus"] * sc["battery_ah"], eta_dc=sc["eta_dc"],
                                            eta_ch=ec, eta_dis=ed, soc_min=1 - c["dod"])
                    row[f"min_soc_{s}"] = r.metrics()["min_soc"]
                out["reconciliation"].append(row)
    # Controller replay on a down-sized S1 (12.8 V / 100 Ah) that actually produces a deficit
    sc = cfg["scenarios"]["S1"]
    pv, cr, au = profiles.hourly_profiles(sc["pv_wp"], c["psh_14d"], c["k_der"], sc["p_base_w"], c["p_light_w"],
                                          c["light_on_hour"], c["light_hours"])
    e_eff = c["k_t"] * 12.8 * 100
    cold = profiles.pv_shape() * sc["pv_wp"] * 1.8 * c["k_der"]
    for pol in ("C0", "C1", "C2"):
        hp = HourlyPolicy(pol, pcfg, pv, cr / sc["eta_dc"], au / sc["eta_dc"], e_eff, c["eta_ch"], c["eta_dis"], cold)
        r = energy_sim.simulate(pv, cr, au, e_eff_wh=e_eff, eta_dc=sc["eta_dc"], eta_ch=c["eta_ch"], eta_dis=c["eta_dis"],
                                soc_min=1 - c["dod"], aux_policy=hp)
        m = r.metrics()
        out["controller_replay"][pol] = {**m, "commands": hp.cmds, "switches": hp.switches, "soc": r.soc.tolist(),
                                         "aux_served_wh": float(((au - r.p_aux_unserved_term) * 1.0).sum()),
                                         "aux_demand_wh": float(au.sum()), "critical_served_wh": float((cr - r.p_crit_unserved_term).sum()),
                                         "model_hours": len(pv), "lockstep": True}
    return out
