"""Gate 3: pilot calibration, power analysis and protocol freeze.

Run BEFORE the confirmatory series. Every decision taken here is copied into
protocol/preregistration.yaml and frozen; this script must never be re-executed
against confirmatory data.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats as sps

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from dtcr import stats
from harness import runner
from harness.scenarios import ACTION_MODELS, SCENARIOS

# Minimum practically relevant effects, declared before the pilot was inspected.
MDE = {"detection_rate": 0.25,          # 25 percentage points
       "containment_latency": 15.0,     # s
       "blast_recall": 0.15,
       "policy_violation_rate": 0.25,
       "whatif_abs_err": 0.10}

# Primary endpoint of each pre-registered hypothesis.
PRIMARY = {
    "H1": dict(metric="detected", kind="proportion", ref="A0", test="A5", scope="all"),
    "H2": dict(metric="containment_latency", kind="paired", ref="A1", test="A5", scope="all"),
    "H3": dict(metric="detected", kind="proportion", ref="A3", test="A5", scope=["S2"]),
    "H4": dict(metric="policy_violation", kind="proportion", ref="A2", test="A5", scope=["S4"]),
    "H5": dict(metric="fp_rate_holdout", kind="noninferiority", ref="A0", test="A5",
               scope="all", margin=0.02),
    "H6": dict(metric="whatif_abs_err", kind="one_sample", ref=None, test="A5",
               scope="all", tolerance=0.10),
}


def n_for_proportion(p1: float, p2: float, alpha: float = 0.05, power: float = 0.80) -> int:
    """Two-proportion sample size; the paired design makes this conservative."""
    if abs(p1 - p2) < 1e-9:
        return 10_000
    pb = (p1 + p2) / 2
    za, zb = sps.norm.ppf(1 - alpha / 2), sps.norm.ppf(power)
    n = (za * np.sqrt(2 * pb * (1 - pb)) + zb * np.sqrt(p1 * (1 - p1) + p2 * (1 - p2))) ** 2 \
        / (p1 - p2) ** 2
    return int(np.ceil(n))


def mu_scale_check() -> dict:
    """Diagnostic for finding F-04: are the two terms of Eq. (12) commensurate?

    With the printed Eq. (12) the risk term is an ABSOLUTE sum over assets while the
    cost term is normalised to [0,1]; their ratio therefore depends on the size of
    the graph. The implementation normalises the risk term by the pre-action level,
    which makes both terms dimensionless. This function reports the ratio that the
    printed form would have produced on the pilot worlds.
    """
    ratios = []
    for scenario in SCENARIOS:
        for rep in range(1, 6):
            w = runner.build_world(scenario, rep)
            r = runner.execute_run(scenario, "A5", rep, "pilot", w, runner.fit_detectors(w))
            realised = r.raw["realised_risk_by_action"]
            risk_range = max(realised.values()) - min(realised.values())
            mu0 = np.asarray(runner.MU_OVERHEAD)
            base = np.array([mu0 @ np.asarray(m.overhead) + m.disruption
                             for m in ACTION_MODELS.values()])
            ratios.append(risk_range / float(base.max() - base.min()))
    return {"absolute_risk_range_over_cost_range": {
        "median": float(np.median(ratios)), "min": float(np.min(ratios)),
        "max": float(np.max(ratios)),
        "note": "values far from 1 mean one term of the printed Eq. (12) dominates"}}


def power_analysis(df: pd.DataFrame) -> dict:
    out = {}
    for hid, spec in PRIMARY.items():
        scopes = sorted(df.scenario.unique()) if spec["scope"] == "all" else spec["scope"]
        per_scenario, required = {}, []
        for sc in scopes:
            d = df[df.scenario == sc]
            if spec["kind"] == "proportion":
                p1 = float(d[d.arm == spec["ref"]][spec["metric"]].mean())
                p2 = float(d[d.arm == spec["test"]][spec["metric"]].mean())
                # Size for the DECLARED minimum effect at the observed reference rate,
                # not for the observed difference: sizing on the observed difference
                # would demand an infinite n wherever the pilot happened to show none.
                mde = MDE["detection_rate" if spec["metric"] == "detected"
                          else "policy_violation_rate"]
                p_alt = float(np.clip(p1 + (mde if p1 <= 0.5 else -mde), 0.001, 0.999))
                n = n_for_proportion(p1, p_alt)
                per_scenario[sc] = {"p_ref": p1, "p_test": p2, "mde": mde,
                                    "n_for_mde": n}
                required.append(n)
            elif spec["kind"] in ("paired", "noninferiority"):
                x = d[d.arm == spec["ref"]].sort_values("repetition")[spec["metric"]].to_numpy(float)
                y = d[d.arm == spec["test"]].sort_values("repetition")[spec["metric"]].to_numpy(float)
                k = min(x.size, y.size)
                mde = spec.get("margin", MDE.get(spec["metric"], 0.1))
                res = stats.paired_power((x[:k] - y[:k]).tolist(), mde)
                per_scenario[sc] = res
                if res["n_required"]:
                    required.append(res["n_required"])
            else:  # one_sample
                v = d[d.arm == spec["test"]][spec["metric"]].to_numpy(float)
                v = v[np.isfinite(v)]
                per_scenario[sc] = {"mean": float(v.mean()) if v.size else float("nan"),
                                    "sd": float(v.std(ddof=1)) if v.size > 1 else float("nan"),
                                    "tolerance": spec["tolerance"]}
        out[hid] = {"spec": {k: v for k, v in spec.items()}, "per_scenario": per_scenario,
                    "n_required_max": max(required) if required else None}
    return out


def main():
    df = pd.read_csv(ROOT / "data" / "pilot" / "runs.csv")
    pw = power_analysis(df)
    feasible = [v["n_required_max"] for v in pw.values()
                if v["n_required_max"] and v["n_required_max"] <= 200]
    n_plan = max([20] + feasible)
    underpowered = {k: v["n_required_max"] for k, v in pw.items()
                    if v["n_required_max"] and v["n_required_max"] > n_plan}
    rep = {
        "gate": "Gate 3 - pilot complete, protocol frozen",
        "n_pilot_runs": int(len(df)),
        "cells": int(df.groupby(["scenario", "arm"]).ngroups),
        "runs_per_cell": int(len(df) / df.groupby(["scenario", "arm"]).ngroups),
        "censored_restore_runs": int(df.censored_restore.sum()),
        "detection_rate": df.pivot_table(index="scenario", columns="arm",
                                         values="detected").round(3).to_dict(),
        "eq12_scale_diagnostic": mu_scale_check(),
        "power_analysis": pw,
        "n_confirmatory_per_cell": int(n_plan),
        "underpowered_contrasts": underpowered,
        "declaration": (
            "n_confirmatory_per_cell is the maximum feasible requirement across "
            "primary endpoints, floored at the protocol minimum of 20. Contrasts "
            "listed under underpowered_contrasts are reported with confidence "
            "intervals and explicitly flagged as underpowered; no significance "
            "claim is made for them."),
    }
    (ROOT / "analysis" / "pilot_report.json").write_text(json.dumps(rep, indent=2, default=str))
    print(json.dumps({k: rep[k] for k in
                      ("gate", "n_pilot_runs", "eq12_scale_diagnostic",
                       "n_confirmatory_per_cell", "underpowered_contrasts")},
                     indent=2, default=str))
    for h, v in pw.items():
        print(f"{h}: n_required_max = {v['n_required_max']}")


if __name__ == "__main__":
    main()
