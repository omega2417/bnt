"""Supplementary analyses reported in Sections 4-5 of the article.

1. FIFO ablation of expiry-ordered (EDF) dispatch for the full (EB) and tier-scoped (ET) gateways.
2. Time to containment restricted to autonomous executions (EB versus CO).
3. Attribution of the additional deadline misses of EB relative to CO (paired, per proposal).
4. Pooled per-scenario rates for S6 (alert storms).

Outputs: results/ablation_fifo.csv, results/extra.json
"""
from __future__ import annotations

import json
import os
import sys
import time

import numpy as np
import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from ebaw.model import BASE, SCENARIOS, Calibrator, scenario_params  # noqa: E402
from ebaw.sim import MAIN_POLICIES, SHORT, Policy, generate, run, summarize  # noqa: E402

NREP = int(os.environ.get("EBAW_NREP", "30"))
OUT = os.path.join(ROOT, "results")
INF = float("inf")


def fifo(pol: Policy) -> Policy:
    return Policy(pol.name + " [FIFO]", pol.kind, pol.S, pol.reval, pol.tiered, edf=False)


def peak_dispatch_queue(R):
    """Maximum number of issued warrants waiting for an orchestrator worker."""
    ev = []
    for r in R:
        if r["t_iss"] < INF and r["t_disp"] < INF and r["t_disp"] >= r["t_iss"]:
            ev.append((r["t_iss"], 1))
            ev.append((r["t_disp"], -1))
    ev.sort(key=lambda e: (e[0], e[1]))
    cur = best = 0
    for _, d in ev:
        cur += d
        best = max(best, cur)
    return best


def met(r, D):
    return r["executed"] and not r["unsafe"] and (r["t_done"] - r["t_obs"]) <= D


def classify_miss(r, D):
    """Mutually exclusive cause of a deadline miss of the gateway (first matching rule)."""
    if r["executed"] and not r["unsafe"] and (r["t_done"] - r["t_obs"]) > D:
        late = "late execution"
    else:
        late = None
    if r["escalated"] and r["urgent"]:
        return "deadline-triggered escalation (P5)"
    if r["lc_timeout"]:
        return "confirmation not obtained within the admissible wait"
    if r["escalated"] and "C" in r["fails_first"]:
        return "VERIFY escalation finished late"
    if r["reverified"] > 0:
        return "freshness refresh (P1)"
    if late:
        return late
    if r["escalated"]:
        return "other escalation"
    return "other: " + str(r["outcome"])


def main():
    t0 = time.time()
    cal = Calibrator(BASE, 42)
    pols = {SHORT[p.name]: p for p in MAIN_POLICIES}
    abl_rows = []
    ttc_rows = []
    attr = {}
    attr_by_sc = {}
    n_extra = 0
    paired = dict(eb_only_miss=0, co_only_miss=0, both=0)
    pk_rows = []
    for key in SCENARIOS:
        P = scenario_params(key)
        for rep in range(NREP):
            props = generate(P, 42 + rep, cal)
            Dm = {p.pid: p.D for p in props}
            res = {}
            for code in ("CO", "EB", "ET"):
                res[code] = run(P, props, pols[code])
            for code in ("EB", "ET"):
                Rf = run(P, props, fifo(pols[code]))
                s = summarize(Rf, props)
                s.update(scenario=key, rep=rep, policy=code, dispatch="FIFO", peak_q=peak_dispatch_queue(Rf))
                abl_rows.append(s)
                s = summarize(res[code], props)
                s.update(scenario=key, rep=rep, policy=code, dispatch="EDF", peak_q=peak_dispatch_queue(res[code]))
                abl_rows.append(s)
            # TTC restricted to autonomous executions
            for code in ("CO", "EB", "ET"):
                R = res[code]
                ttc_all = [r["t_done"] - r["t_obs"] for r in R
                           if r["kind"] == "gen" and r["y"] == 1 and r["executed"] and not r["unsafe"]]
                ttc_auto = [r["t_done"] - r["t_obs"] for r in R
                            if r["kind"] == "gen" and r["y"] == 1 and r["executed"] and not r["unsafe"]
                            and not r["manual"]]
                ttc_rows.append(dict(scenario=key, rep=rep, policy=code,
                                     TTC_all_med=float(np.median(ttc_all)) if ttc_all else np.nan,
                                     TTC_auto_med=float(np.median(ttc_auto)) if ttc_auto else np.nan,
                                     n_auto_mal=len(ttc_auto), n_all_mal=len(ttc_all)))
            # paired miss attribution EB versus CO (genuine malicious proposals only)
            Rc, Re = res["CO"], res["EB"]
            for rc, re_ in zip(Rc, Re):
                if not (rc["kind"] == "gen" and rc["y"] == 1):
                    continue
                D = Dm[rc["pid"]]
                mc, me = met(rc, D), met(re_, D)
                if mc and not me:
                    paired["eb_only_miss"] += 1
                    c = classify_miss(re_, D)
                    attr[c] = attr.get(c, 0) + 1
                    attr_by_sc.setdefault(key, {}).setdefault(c, 0)
                    attr_by_sc[key][c] += 1
                    n_extra += 1
                elif me and not mc:
                    paired["co_only_miss"] += 1
                elif not mc and not me:
                    paired["both"] += 1
        print(f"{key} done ({time.time() - t0:.0f} s)", flush=True)

    abl = pd.DataFrame(abl_rows)
    abl.to_csv(os.path.join(OUT, "ablation_fifo.csv"), index=False)
    ttc = pd.DataFrame(ttc_rows)
    ttc.to_csv(os.path.join(OUT, "ttc_auto.csv"), index=False)

    out = {}
    # ---- FIFO ablation summary
    ab = {}
    for (code, disp), x in abl.groupby(["policy", "dispatch"]):
        ab[f"{code}_{disp}"] = dict(
            UER=float(x.unsafe.sum() / x.n.sum() * 1000), DMR=float(x.miss.sum() / x.n_mal.sum() * 100),
            ESC=float(x.esc.sum() / x.n.sum() * 100), J=float(x.J.mean()), CVR=float(x.viol.sum() / x.n_auto.sum() * 100))
        for sc in ("S0", "S6", "S7"):
            y = x[x.scenario == sc]
            ab[f"{code}_{disp}"][sc] = dict(
                DMR=float(y.miss.sum() / y.n_mal.sum() * 100), ESC=float(y.esc.sum() / y.n.sum() * 100),
                J=float(y.J.mean()), UER=float(y.unsafe.sum() / y.n.sum() * 1000),
                peak_q_mean=float(y.peak_q.mean()), peak_q_max=int(y.peak_q.max()),
                peak_q_rep0=int(y[y.rep == 0].peak_q.iloc[0]))
    # paired difference in J (FIFO - EDF) per scenario for EB, with t-interval over replications
    from scipy import stats
    pdiff = {}
    for code in ("EB", "ET"):
        for sc in sorted(abl.scenario.unique()):
            a = abl[(abl.policy == code) & (abl.scenario == sc)].set_index(["rep", "dispatch"]).J.unstack()
            d = (a["FIFO"] - a["EDF"]).to_numpy()
            h = stats.t.ppf(0.975, len(d) - 1) * d.std(ddof=1) / np.sqrt(len(d)) if d.std(ddof=1) > 0 else 0.0
            pdiff[f"{code}_{sc}"] = dict(mean=float(d.mean()), h=float(h))
    ab["paired_J_diff_FIFO_minus_EDF"] = pdiff
    out["fifo_ablation"] = ab

    # ---- TTC
    tt = {}
    for code, x in ttc.groupby("policy"):
        tt[code] = dict(TTC_all=float(x.TTC_all_med.mean()), TTC_auto=float(x.TTC_auto_med.mean()),
                        n_auto=int(x.n_auto_mal.sum()), n_all=int(x.n_all_mal.sum()))
        for sc in ("S0", "S7"):
            y = x[x.scenario == sc]
            tt[code][sc] = dict(TTC_all=float(y.TTC_all_med.mean()), TTC_auto=float(y.TTC_auto_med.mean()))
    out["ttc"] = tt

    # ---- attribution
    out["miss_attribution_EB_vs_CO"] = dict(
        n_extra=n_extra, paired=paired,
        shares={k: dict(n=v, pct=100.0 * v / max(1, n_extra)) for k, v in sorted(attr.items(), key=lambda kv: -kv[1])},
        by_scenario=attr_by_sc)

    # ---- pooled S6 rates for every main policy
    df = pd.read_csv(os.path.join(OUT, "main_runs.csv"))
    s6 = {}
    for code, x in df[df.scenario == "S6"].groupby("policy"):
        s6[code] = dict(DMR=float(x.miss.sum() / x.n_mal.sum() * 100), ESC=float(x.esc.sum() / x.n.sum() * 100),
                        UER=float(x.unsafe.sum() / x.n.sum() * 1000), J=float(x.J.mean()))
    s0 = {}
    for code, x in df[df.scenario == "S0"].groupby("policy"):
        s0[code] = dict(DMR=float(x.miss.sum() / x.n_mal.sum() * 100), ESC=float(x.esc.sum() / x.n.sum() * 100))
    out["pooled_S6"] = s6
    out["pooled_S0"] = s0
    json.dump(out, open(os.path.join(OUT, "extra.json"), "w"), indent=1)
    print(json.dumps(out, indent=1))
    print(f"done ({time.time() - t0:.0f} s)")


if __name__ == "__main__":
    main()
