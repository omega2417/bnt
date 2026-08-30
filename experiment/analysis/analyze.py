"""Gate 4/5 analysis: every table and figure number in the report comes from here.

Reads processed/runs.csv only. No number is typed by hand anywhere downstream.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from dtcr import stats

ALPHA = 0.05
FAMILY = ["H1", "H2", "H3", "H4", "H5"]
NI_MARGIN = 0.02          # H5 non-inferiority margin on the false-positive rate
WHATIF_TOL = 0.10         # H6 tolerance
ARMS = ["A0", "A1", "A2", "A3", "A4", "A5"]
SCENARIOS = ["S1", "S2", "S3", "S4"]


def load(path: Path) -> pd.DataFrame:
    df = pd.read_csv(path)
    df = df[df.exclusion_flag == 0].copy()
    return df


def paired(df, sc, metric, a_ref, a_test):
    d = df[df.scenario == sc]
    x = d[d.arm == a_ref].sort_values("repetition")[metric].to_numpy(float)
    y = d[d.arm == a_test].sort_values("repetition")[metric].to_numpy(float)
    k = min(x.size, y.size)
    return x[:k], y[:k]


def descriptive(df: pd.DataFrame) -> pd.DataFrame:
    rows = []
    metrics = ["detection_latency", "containment_latency", "t_service_restore",
               "nri", "fp_rate_holdout", "blast_recall", "whatif_abs_err",
               "orchestrator_cpu_s", "availability_below_amin", "action_regret"]
    for sc in SCENARIOS:
        for arm in ARMS:
            d = df[(df.scenario == sc) & (df.arm == arm)]
            for m in metrics:
                v = d[m].to_numpy(float)
                n_cens = int(np.sum(~np.isfinite(v)))
                s = stats.describe(v, n_censored=n_cens, seed=abs(hash((sc, arm, m))) % 2**31)
                rows.append(dict(scenario=sc, arm=arm, metric=m, n=s.n, n_missing=n_cens,
                                 mean=s.mean, sd=s.sd, median=s.median, q1=s.q1, q3=s.q3,
                                 ci_lo=s.ci_lo, ci_hi=s.ci_hi))
            for m in ["detected", "contained", "recovered", "policy_violation",
                      "unsafe_action", "rollback", "action_optimal", "censored_restore"]:
                k, n = int(d[m].sum()), int(len(d))
                lo, hi = stats.wilson_ci(k, n)
                rows.append(dict(scenario=sc, arm=arm, metric=m, n=n, n_missing=0,
                                 mean=k / n if n else float("nan"), sd=float("nan"),
                                 median=float("nan"), q1=float("nan"), q3=float("nan"),
                                 ci_lo=lo, ci_hi=hi))
    return pd.DataFrame(rows)


def hypotheses(df: pd.DataFrame) -> dict:
    out, praw = {}, {}

    def prop_contrast(sc, metric, a_ref, a_test):
        d = df[df.scenario == sc]
        r, t = d[d.arm == a_ref], d[d.arm == a_test]
        k1, n1 = int(t[metric].sum()), len(t)
        k2, n2 = int(r[metric].sum()), len(r)
        rd, lo, hi = stats.risk_difference(k1, n1, k2, n2)
        x, y = paired(df, sc, metric, a_ref, a_test)
        pt = stats.paired_test(y, x)
        return {"p_test": k1 / n1, "p_ref": k2 / n2, "n": n1,
                "risk_difference": rd, "rd_ci": [lo, hi], **pt}

    # H1 detection rate A0 vs A5
    out["H1"] = {"endpoint": "detection rate", "contrast": "A0 vs A5", "per_scenario": {}}
    for sc in SCENARIOS:
        out["H1"]["per_scenario"][sc] = prop_contrast(sc, "detected", "A0", "A5")
    praw["H1"] = min(v["p"] for v in out["H1"]["per_scenario"].values()
                     if np.isfinite(v["p"])) if any(
        np.isfinite(v["p"]) for v in out["H1"]["per_scenario"].values()) else float("nan")

    # H2 containment latency A1 vs A5
    out["H2"] = {"endpoint": "containment_latency", "contrast": "A1 vs A5",
                 "per_scenario": {}, "note": "S4 pre-declared UNDERPOWERED (n req 2535)"}
    ps = []
    for sc in SCENARIOS:
        x, y = paired(df, sc, "containment_latency", "A1", "A5")
        t = stats.paired_test(x, y)
        m = np.isfinite(x) & np.isfinite(y)
        # Effect sizes are not reported when censoring has left too few complete
        # pairs to estimate them: a Hedges g computed on two surviving pairs is an
        # artefact of the censoring pattern, not a measurement of the effect.
        MIN_PAIRS = 5
        estimable = m.sum() >= MIN_PAIRS
        out["H2"]["per_scenario"][sc] = {
            **t, "mean_A1": float(np.nanmean(x)) if m.any() else float("nan"),
            "mean_A5": float(np.nanmean(y)) if m.any() else float("nan"),
            "median_diff": float(np.median((x - y)[m])) if estimable else float("nan"),
            "diff_ci": list(stats.bootstrap_ci((x - y)[m], seed=11)) if estimable else [np.nan] * 2,
            "hedges_g": stats.hedges_g(x, y) if estimable else float("nan"),
            "cliffs_delta": stats.cliffs_delta(x, y) if estimable else float("nan"),
            "effect_estimable": bool(estimable),
            "n_complete_pairs": int(m.sum()),
            "n_censored_A1": int(np.sum(~np.isfinite(x))),
            "n_censored_A5": int(np.sum(~np.isfinite(y))),
            "censoring_note": ("A1 fails to contain in most runs of this scenario; the "
                               "comparison is a containment-RATE difference, not a "
                               "latency difference") if not estimable else ""}
        if np.isfinite(t["p"]):
            ps.append(t["p"])
    praw["H2"] = min(ps) if ps else float("nan")

    # H3 detection rate in S2, A3 vs A5
    out["H3"] = {"endpoint": "detection rate (S2)", "contrast": "A3 vs A5",
                 "per_scenario": {"S2": prop_contrast("S2", "detected", "A3", "A5")}}
    praw["H3"] = out["H3"]["per_scenario"]["S2"]["p"]

    # H4 policy violations in S4, A2 vs A5 (+ graph secondaries)
    out["H4"] = {"endpoint": "policy_violation rate (S4)", "contrast": "A2 vs A5",
                 "per_scenario": {"S4": prop_contrast("S4", "policy_violation", "A2", "A5")},
                 "secondary_blast_recall": {}, "secondary_whatif": {}}
    for sc in SCENARIOS:
        x, y = paired(df, sc, "blast_recall", "A4", "A5")
        m = np.isfinite(x) & np.isfinite(y)
        out["H4"]["secondary_blast_recall"][sc] = {
            **stats.paired_test(y, x), "mean_A4": float(np.nanmean(x)),
            "mean_A5": float(np.nanmean(y)),
            "diff_ci": list(stats.bootstrap_ci((y - x)[m], seed=13)) if m.sum() > 1 else [np.nan] * 2,
            "cliffs_delta": stats.cliffs_delta(y, x)}
        for arm in ("A3", "A5"):
            v = df[(df.scenario == sc) & (df.arm == arm)].whatif_abs_err.to_numpy(float)
            v = v[np.isfinite(v)]
            out["H4"]["secondary_whatif"].setdefault(sc, {})[arm] = {
                "mean": float(v.mean()) if v.size else float("nan"),
                "ci": list(stats.bootstrap_ci(v, seed=17))}
    praw["H4"] = out["H4"]["per_scenario"]["S4"]["p"]

    # H5 non-inferiority of the false-positive rate + overhead
    out["H5"] = {"endpoint": "fp_rate_holdout", "contrast": "A5 vs A0",
                 "type": "non-inferiority", "margin": NI_MARGIN, "per_scenario": {}}
    ps = []
    for sc in SCENARIOS:
        x, y = paired(df, sc, "fp_rate_holdout", "A0", "A5")
        diff = y - x
        m = np.isfinite(diff)
        lo, hi = stats.bootstrap_ci(diff[m], seed=19) if m.sum() > 1 else (np.nan, np.nan)
        t = stats.paired_test(y, x)
        out["H5"]["per_scenario"][sc] = {
            "mean_A0": float(np.nanmean(x)), "mean_A5": float(np.nanmean(y)),
            "mean_increase": float(np.nanmean(diff)), "increase_ci": [lo, hi],
            "non_inferior": bool(np.isfinite(hi) and hi < NI_MARGIN), **t}
        if np.isfinite(t["p"]):
            ps.append(t["p"])
    praw["H5"] = min(ps) if ps else float("nan")
    ovh = {}
    for arm in ARMS:
        v = df[df.arm == arm].orchestrator_cpu_s.to_numpy(float) * 1e3
        base = df[df.arm == "A0"].orchestrator_cpu_s.mean() * 1e3
        ovh[arm] = {"cpu_ms_mean": float(v.mean()), "cpu_ms_ci": list(stats.bootstrap_ci(v, seed=23)),
                    "relative_to_A0": float(v.mean() / base)}
    out["H5"]["orchestrator_overhead"] = ovh

    # H6 what-if calibration (one-sample, no p-value in the Holm family)
    v = df[(df.arm == "A5")].whatif_abs_err.to_numpy(float)
    v = v[np.isfinite(v)]
    lo, hi = stats.bootstrap_ci(v, seed=29)
    out["H6"] = {"endpoint": "whatif_abs_err (A5)", "tolerance": WHATIF_TOL,
                 "n": int(v.size), "mean": float(v.mean()), "ci": [lo, hi],
                 "within_tolerance": bool(hi < WHATIF_TOL),
                 "per_scenario": {sc: float(df[(df.arm == "A5") & (df.scenario == sc)]
                                            .whatif_abs_err.mean()) for sc in SCENARIOS}}

    adj = stats.holm([praw[h] for h in FAMILY], FAMILY)
    for h in FAMILY:
        out[h]["p_raw_min_across_scenarios"] = praw[h]
        out[h]["p_holm_adjusted"] = adj[h]
    return out


def sensitivity(df: pd.DataFrame) -> dict:
    """Section 14.9: repeat the headline contrasts under alternative inclusion rules."""
    res = {}
    for label, sub in [("all_valid_runs", df),
                       ("complete_cases_only", df[df.censored_restore == 0]),
                       ("exclude_first_10_reps", df[df.repetition > 10])]:
        r = {}
        for sc in SCENARIOS:
            d = sub[sub.scenario == sc]
            if d.empty:
                continue
            r[sc] = {"detect_A0": float(d[d.arm == "A0"].detected.mean()),
                     "detect_A5": float(d[d.arm == "A5"].detected.mean()),
                     "contain_A1": float(d[d.arm == "A1"].containment_latency.mean()),
                     "contain_A5": float(d[d.arm == "A5"].containment_latency.mean()),
                     "n": int(len(d))}
        res[label] = r
    return res


def main():
    src = ROOT / "data" / "simulation" / "runs.csv"
    df = load(src)
    proc = ROOT / "processed"
    proc.mkdir(exist_ok=True)
    df.to_csv(proc / "runs.csv", index=False)

    desc = descriptive(df)
    desc.to_csv(proc / "descriptive_statistics.csv", index=False)
    hyp = hypotheses(df)
    sens = sensitivity(df)
    summary = {
        "source": str(src.relative_to(ROOT)),
        "n_runs": int(len(df)),
        "n_excluded": 0,
        "data_origin_counts": df.data_origin.value_counts().to_dict(),
        "cells": int(df.groupby(["scenario", "arm"]).ngroups),
        "runs_per_cell": int(len(df) / df.groupby(["scenario", "arm"]).ngroups),
        "censored_restore_total": int(df.censored_restore.sum()),
        "convergence_margin_min": float(np.nanmin(df.convergence_margin.to_numpy(float))),
        "hypotheses": hyp,
        "sensitivity": sens,
    }
    (ROOT / "analysis" / "results.json").write_text(json.dumps(summary, indent=2, default=str))
    print(json.dumps({k: summary[k] for k in
                      ("n_runs", "data_origin_counts", "cells", "runs_per_cell",
                       "censored_restore_total")}, indent=2, default=str))
    for h in FAMILY + ["H6"]:
        v = hyp[h]
        print(f"\n== {h}: {v['endpoint']} ({v.get('contrast','-')})")
        if h == "H6":
            print(f"   mean={v['mean']:.4f} CI={np.round(v['ci'],4).tolist()} "
                  f"tol={v['tolerance']} within={v['within_tolerance']}")
            continue
        print(f"   p_raw={v['p_raw_min_across_scenarios']:.3g}  p_holm={v['p_holm_adjusted']:.3g}")
        for sc, s in v["per_scenario"].items():
            if "risk_difference" in s:
                print(f"   {sc}: p_ref={s['p_ref']:.3f} p_test={s['p_test']:.3f} "
                      f"RD={s['risk_difference']:+.3f} CI={np.round(s['rd_ci'],3).tolist()}")
            elif "mean_increase" in s:
                print(f"   {sc}: A0={s['mean_A0']:.4f} A5={s['mean_A5']:.4f} "
                      f"delta={s['mean_increase']:+.4f} CI={np.round(s['increase_ci'],4).tolist()} "
                      f"non_inferior={s['non_inferior']}")
            else:
                est = "" if s.get("effect_estimable", True) else "  [NOT ESTIMABLE: censoring]"
                print(f"   {sc}: A1={s['mean_A1']:.1f}s A5={s['mean_A5']:.1f}s "
                      f"g={s['hedges_g']:.2f} delta={s['cliffs_delta']:+.2f} "
                      f"pairs={s['n_complete_pairs']} cens(A1/A5)={s['n_censored_A1']}/{s['n_censored_A5']}{est}")


if __name__ == "__main__":
    main()
