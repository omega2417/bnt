"""Run all simulation experiments reported in the article.

Outputs (results/):
  main_runs.csv        scenario x replication x policy metrics (6 policies, 8 scenarios, 30 reps)
  lattice_runs.csv     32 predicate subsets (with revalidation) under S7, 30 reps
  upset_EB_S7.csv      per-proposal failing-predicate sets for the full gateway under S7
  cfd_S6_rep0.csv      per-proposal lifecycle timestamps (EB and GN) under S6, replication 0
  windows.csv          check-to-act windows for GN and EB executions
  traces.json          per-proposal records used for the timing diagram
  prop1.csv            analytic vs simulated timing admissibility per action class
Seed policy: replication r uses seed 42 + r for every scenario and policy (synchronised CRN).
"""
from __future__ import annotations

import json
import math
import os
import sys
import time

import numpy as np
import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from ebaw.model import (ACTIONS, ACTION_NAMES, BASE, SCENARIOS, TAU_SIGMA, Calibrator,  # noqa: E402
                        scenario_params, PREDICATES)
from ebaw.sim import (MAIN_POLICIES, SHORT, Policy, generate, lattice_policies, run,  # noqa: E402
                      summarize)

NREP = int(os.environ.get("EBAW_NREP", "30"))
OUT = os.path.join(ROOT, "results")
os.makedirs(OUT, exist_ok=True)


def main():
    t0 = time.time()
    cal = Calibrator(BASE, 42)
    rows, win_rows = [], []
    upset_rows, cfd_rows = [], []
    trace_store = {}
    for key in SCENARIOS:
        P = scenario_params(key)
        for rep in range(NREP):
            props = generate(P, 42 + rep, cal)
            for pol in MAIN_POLICIES:
                R = run(P, props, pol)
                s = summarize(R, props)
                s.update(scenario=key, rep=rep, policy=SHORT[pol.name])
                rows.append(s)
                code = SHORT[pol.name]
                if code in ("GN", "EB", "CO"):
                    for r in R:
                        if r["executed"] and not r["manual"]:
                            win_rows.append(dict(scenario=key, rep=rep, policy=code, window=r["window"],
                                                 change=r["window_change"], change_v=r["window_change_v"],
                                                 violation=r["violation"],
                                                 viol_set=r["viol_set"], unsafe=r["unsafe"]))
                if key == "S7" and code == "EB":
                    for r in R:
                        upset_rows.append(dict(rep=rep, pid=r["pid"], kind=r["kind"], y=r["y"],
                                               fails_first=r["fails_first"], fails_reval=r["fails_reval"],
                                               fails_all="".join(x for x in "FCLVD" if x in r["fails_all"]),
                                               outcome=r["outcome"]))
                if key == "S6" and rep == 0 and code in ("EB", "GN"):
                    for r in R:
                        cfd_rows.append(dict(policy=code, pid=r["pid"], kind=r["kind"], t_prop=r["t_prop"],
                                             t_decided=r["t_decided"], t_disp=r["t_disp"], t_x=r["t_x"],
                                             t_done=r["t_done"], t_closed=r["t_closed"], outcome=r["outcome"],
                                             escalated=r["escalated"]))
                if key in ("S3", "S7") and code in ("EB", "GN") and rep < 3:
                    for r in R:
                        p = props[r["pid"]]
                        rec = {k: (v if not isinstance(v, set) else "".join(sorted(v))) for k, v in r.items()}
                        rec.update(t_pc1=p.t_pc1, t_pc2=p.t_pc2, f1=p.f1, f2=p.f2, t_ret=p.t_ret,
                                   t_drift=p.t_drift, t_conf=p.t_conf, t_avail=p.t_avail, Phi=p.Phi, D=p.D,
                                   tau=p.tau, c_gw=p.c_gw, prep=p.prep, dg=p.dg, dc=p.dc, dq=p.dq)
                        trace_store.setdefault(f"{key}|{rep}|{r['pid']}", {})[code] = {
                            k: (None if (isinstance(v, float) and not math.isfinite(v)) else v)
                            for k, v in rec.items()}
        print(f"{key} done ({time.time() - t0:.0f} s)", flush=True)
    pd.DataFrame(rows).to_csv(os.path.join(OUT, "main_runs.csv"), index=False)
    pd.DataFrame(win_rows).to_csv(os.path.join(OUT, "windows.csv"), index=False)
    pd.DataFrame(upset_rows).to_csv(os.path.join(OUT, "upset_EB_S7.csv"), index=False)
    pd.DataFrame(cfd_rows).to_csv(os.path.join(OUT, "cfd_S6_rep0.csv"), index=False)
    # keep only traces where GN executed with a version violation and EB did not execute
    keep = {}
    for k, d in trace_store.items():
        if "GN" in d and "EB" in d:
            g, e = d["GN"], d["EB"]
            if g["executed"] and "V" in (g["viol_set"] or "") and not e["executed"] and g["kind"] == "gen":
                keep[k] = d
    with open(os.path.join(OUT, "traces.json"), "w") as f:
        json.dump(keep, f, indent=1, default=str)

    # ---- lattice of predicate subsets under S7
    lat_rows = []
    P = scenario_params("S7")
    for rep in range(NREP):
        props = generate(P, 42 + rep, cal)
        for pol in lattice_policies():
            R = run(P, props, pol)
            s = summarize(R, props)
            s.update(rep=rep, subset="".join(x for x in PREDICATES if x in pol.S) or "0")
            lat_rows.append(s)
    pd.DataFrame(lat_rows).to_csv(os.path.join(OUT, "lattice_runs.csv"), index=False)
    print(f"lattice done ({time.time() - t0:.0f} s)", flush=True)

    # ---- Proposition 1: analytic vs simulated timing admissibility (node {F,L,D} with revalidation)
    pol_t = Policy("GW{FLD}", "GW", frozenset({"F", "L", "D"}), True)
    p1_rows = []
    for key in ("S0", "S2"):
        P = scenario_params(key)
        sim_ok = {a: [0, 0] for a in ACTION_NAMES}
        for rep in range(NREP):
            props = generate(P, 42 + rep, cal)
            R = run(P, props, pol_t)
            for r in R:
                if r["kind"] != "gen":
                    continue
                timing_fail = ("F" in r["fails_all"]) or ("D" in r["fails_all"]) or r["lc_timeout"]
                sim_ok[r["action"]][0] += int(not timing_fail)
                sim_ok[r["action"]][1] += 1
        an = analytic_admissibility(P, n=400000, seed=7)
        for a in ACTION_NAMES:
            d = an[a]
            p1_rows.append(dict(scenario=key, action=a, B=d["B"], mean=d["mean"], sd=d["sd"],
                                cantelli=d["cantelli"], cantelli_ok=d["cantelli"] <= d["B"],
                                q95=d["q95"], P_an=d["P"], P_sim=sim_ok[a][0] / max(1, sim_ok[a][1]),
                                n_sim=sim_ok[a][1]))
    pd.DataFrame(p1_rows).to_csv(os.path.join(OUT, "prop1.csv"), index=False)
    print(f"all done ({time.time() - t0:.0f} s)", flush=True)


def analytic_admissibility(P, n=200000, seed=7, eta=0.05):
    """Monte Carlo evaluation of Proposition 1 with independent latency components and
    no orchestrator queueing:  Lambda = a0 + max(Delta_a, ds + Lc) + dq + dg + prep + dr."""
    rng = np.random.default_rng(seed)
    ing = P["ing_median"] * np.exp(P["ing_sigma"] * rng.standard_normal(n))
    stale = rng.random(n) < P["stale_p"]
    ing = ing + stale * rng.uniform(P["stale_lo"], P["stale_hi"], n)
    agent = P["agent_median"] * np.exp(P["agent_sigma"] * rng.standard_normal(n))
    u = rng.random(n)
    lc = P["lc_median"] * np.exp(P["lc_sigma"] * rng.standard_normal(n))
    lc = np.where(u < P["lc_stall_p"], rng.uniform(P["lc_stall_lo"], P["lc_stall_hi"], n), lc)
    lc = np.where((u >= P["lc_stall_p"]) & (u < P["lc_stall_p"] + P["lc_delay_p"]),
                  rng.uniform(P["lc_delay_lo"], P["lc_delay_hi"], n), lc)
    sg = P["lat_sigma"]
    dq = P["dq_median"] * np.exp(sg * rng.standard_normal(n))
    dg = P["dg_median"] * np.exp(sg * rng.standard_normal(n))
    dr = P["dg_median"] * np.exp(sg * rng.standard_normal(n))
    prep = P["prep_median"] * np.exp(P["prep_sigma"] * rng.standard_normal(n))
    lam = ing + np.maximum(agent, P["ds"] + lc) + dq + dg + prep + dr
    out = {}
    k = math.sqrt((1 - eta) / eta)
    for a in ACTION_NAMES:
        A = ACTIONS[a]
        tau = A["tau"] * np.exp(TAU_SIGMA * rng.standard_normal(n))
        tau_hat = A["tau"] * math.exp(1.2816 * TAU_SIGMA)
        B = min(A["Phi"], A["D"] - tau_hat)
        ok = (lam <= A["Phi"]) & (lam + tau <= A["D"])
        out[a] = dict(B=B, mean=float(lam.mean()), sd=float(lam.std()), cantelli=float(lam.mean() + k * lam.std()),
                      q95=float(np.quantile(lam, 0.95)), P=float(ok.mean()))
    return out


if __name__ == "__main__":
    main()
