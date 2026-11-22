"""Aggregate the simulation outputs into the numbers and tables reported in the article."""
import json
import os

import numpy as np
import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
R = os.path.join(ROOT, "results")
df = pd.read_csv(os.path.join(R, "main_runs.csv"))
order = ["AD", "CO", "RO", "GN", "EB", "ET"]
out = {}


def ci(x):
    """Mean and half-width of the 95% confidence interval (Student t, n - 1 degrees of freedom)."""
    from scipy import stats
    x = np.asarray(x, float)
    h = stats.t.ppf(0.975, len(x) - 1) * x.std(ddof=1) / np.sqrt(len(x))
    return float(x.mean()), float(h)


# per-scenario expected cost J and UER
tabJ = df.groupby(["scenario", "policy"]).J.mean().unstack()[order]
tabU = df.groupby(["scenario", "policy"]).UER.mean().unstack()[order]
tabJ.round(3).to_csv(os.path.join(R, "table_J_by_scenario.csv"))
tabU.round(1).to_csv(os.path.join(R, "table_UER_by_scenario.csv"))
out["J_by_scenario"] = tabJ.round(3).to_dict()
out["best_J_by_scenario"] = {s: tabJ.loc[s].idxmin() for s in tabJ.index}

# detailed S0 / S7 tables
det = {}
for sc in ("S0", "S7"):
    d = df[df.scenario == sc]
    rows = {}
    for p in order:
        x = d[d.policy == p]
        u, uh = ci(x.UER)
        j, jh = ci(x.J)
        rows[p] = dict(UER=u, UER_h=uh, CVR=float(x.viol.sum() / max(1, x.n_auto.sum()) * 100),
                       DMR=float(x.miss.sum() / x.n_mal.sum() * 100), ESC=float(x.esc.sum() / x.n.sum() * 100),
                       TTC_med=float(x.TTC_med.mean()), TTC_p95=float(x.TTC_p95.mean()),
                       adv=f"{int(x.adv_exec.sum())}/{int(x.n_adv.sum())}", J=j, J_h=jh)
    det[sc] = rows
out["detail"] = det

# pooled across all scenarios
pool = {}
for p in order:
    x = df[df.policy == p]
    pool[p] = dict(UER=float(x.unsafe.sum() / x.n.sum() * 1000), CVR=float(x.viol.sum() / x.n_auto.sum() * 100),
                   viol=int(x.viol.sum()), n_auto=int(x.n_auto.sum()),
                   DMR=float(x.miss.sum() / x.n_mal.sum() * 100), ESC=float(x.esc.sum() / x.n.sum() * 100),
                   J=float(x.J.mean()), adv_exec=int(x.adv_exec.sum()), n_adv=int(x.n_adv.sum()),
                   n=int(x.n.sum()), unsafe=int(x.unsafe.sum()), miss=int(x.miss.sum()), esc=int(x.esc.sum()),
                   TTC_med=float(x.TTC_med.mean()), TTC_p95=float(x.TTC_p95.mean()))
out["pooled"] = pool

# break-even unsafe-cost ratio c_U* (c_M = 5, c_E = 1) for pairs of policies
def per_prop(p):
    x = df[df.policy == p]
    n = x.n.sum()
    return x.unsafe.sum() / n, x.miss.sum() / n, x.esc.sum() / n


be = {}
for a, b in (("EB", "GN"), ("EB", "CO"), ("ET", "EB"), ("GN", "CO")):
    ua, ma, ea = per_prop(a)
    ub, mb, eb = per_prop(b)
    du = ub - ua
    rhs = 5 * (ma - mb) + (ea - eb)
    be[f"{a}_vs_{b}"] = dict(dU=float(du), dM=float(ma - mb), dE=float(ea - eb),
                             cU_star=float(rhs / du) if du != 0 else None)
out["break_even"] = be

# per-scenario break-even EB vs GN
bes = {}
for sc in sorted(df.scenario.unique()):
    d = df[df.scenario == sc]
    def pp(p):
        x = d[d.policy == p]
        n = x.n.sum()
        return x.unsafe.sum() / n, x.miss.sum() / n, x.esc.sum() / n
    ua, ma, ea = pp("EB")
    ub, mb, eb = pp("GN")
    du = ub - ua
    rhs = 5 * (ma - mb) + (ea - eb)
    bes[sc] = dict(dU_per1000=float(du * 1000), cU_star=float(rhs / du) if du > 0 else None)
out["break_even_EB_GN_by_scenario"] = bes

# windows / Proposition 2
from ebaw_paths import scenario_rate  # noqa: E402

w = pd.read_csv(os.path.join(R, "windows.csv"))
wr = {}
for sc in ("S0", "S3", "S6", "S7"):
    lam = scenario_rate(sc)
    for p in ("CO", "GN", "EB"):
        d = w[(w.scenario == sc) & (w.policy == p)]
        wr[f"{sc}_{p}"] = dict(n=int(len(d)), W_med=float(d.window.median()), W_mean=float(d.window.mean()),
                               W_p95=float(np.percentile(d.window, 95)), P_v_sim=float(d.change_v.mean()),
                               P_v_pred=float(1 - np.mean(np.exp(-lam * d.window))),
                               P_any=float(d.change.mean()), viol=float(d.violation.mean()))
dd = w[w.policy == "GN"]
wr["GN_all"] = dict(n=int(len(dd)), W_med=float(dd.window.median()), W_p95=float(np.percentile(dd.window, 95)),
                    P_any=float(dd.change.mean()), viol=float(dd.violation.mean()))
de = w[w.policy == "EB"]
wr["EB_all"] = dict(n=int(len(de)), W_med=float(de.window.median()), W_p95=float(np.percentile(de.window, 95)),
                    P_any=float(de.change.mean()), viol=float(de.violation.mean()))
out["windows"] = wr
gnv = w[(w.policy == "GN") & (w.violation)].viol_set.value_counts()
out["GN_violation_sets"] = gnv.to_dict()

# Proposition 1
p1 = pd.read_csv(os.path.join(R, "prop1.csv"))
p1["diff_pp"] = (p1.P_sim - p1.P_an) * 100
out["prop1_max_abs_diff_pp"] = float(p1.diff_pp.abs().max())
out["prop1"] = p1.round(4).to_dict(orient="records")

# lattice
lat = pd.read_csv(os.path.join(R, "lattice_runs.csv"), dtype={"subset": str})
m = lat.groupby("subset")[["UER", "CVR", "DMR", "ESC", "J"]].mean()
out["lattice"] = m.round(3).to_dict(orient="index")
out["lattice_minJ"] = m.J.idxmin()
out["lattice_minUER"] = m.UER.idxmin()

out["friedman"] = json.load(open(os.path.join(R, "friedman.json")))
json.dump(out, open(os.path.join(R, "summary.json"), "w"), indent=1)
print(json.dumps({k: out[k] for k in ("pooled", "detail", "break_even", "break_even_EB_GN_by_scenario",
                                       "best_J_by_scenario", "prop1_max_abs_diff_pp", "lattice_minJ",
                                       "lattice_minUER")}, indent=1))
print(json.dumps(out["windows"], indent=1))
print(out["GN_violation_sets"])
