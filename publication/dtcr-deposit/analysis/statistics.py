#!/usr/bin/env python3
"""Compute every statistic reported in the revised Results section.

Reads ``data/`` and writes machine-readable tables to ``results/``:

  table_S1_detection_latency.csv   scenario-level detection latency
  table_S2_recovery_time.csv       scenario-level recovery time
  table_S3_nri.csv                 scenario-level NRI and resilience deficit
  table_S4_integrity.csv           confusion matrices with Wilson intervals
  table_S5_overhead.csv            resource overhead per Eq. (17), both denominators
  table_S6_ablation.csv            ablation variants and safety-of-action rates
  summary.json                     the aggregate values quoted in the abstract

Usage:  python analysis/statistics.py --data data --out results
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from dtcr import stats as st  # noqa: E402

SCENARIOS = ["S1", "S2", "S3", "S4"]
PAIRED = True  # runs were scheduled as interleaved matched pairs; see PROTOCOL.md


def _row(scenario, metric, comp):
    b, f = comp["baseline"], comp["framework"]
    return {
        "scenario": scenario, "metric": metric,
        "n_baseline": b["n"], "n_framework": f["n"],
        "baseline_mean": b["mean"], "baseline_sd": b["sd"],
        "baseline_median": b["median"], "baseline_iqr": b["iqr"],
        "baseline_ci95_lo": b["ci95_lo"], "baseline_ci95_hi": b["ci95_hi"],
        "framework_mean": f["mean"], "framework_sd": f["sd"],
        "framework_median": f["median"], "framework_iqr": f["iqr"],
        "framework_ci95_lo": f["ci95_lo"], "framework_ci95_hi": f["ci95_hi"],
        "abs_diff_mean": comp["abs_diff_mean"],
        "diff_ci95_lo": comp.get("diff_ci", {}).get("ci95_lo"),
        "diff_ci95_hi": comp.get("diff_ci", {}).get("ci95_hi"),
        "rel_reduction_pct": comp["rel_reduction_pct"],
        "hedges_g": comp["hedges_g"], "cliffs_delta": comp["cliffs_delta"],
        "test": comp["test"]["name"], "p_value": comp["test"]["p_value"],
        "test_nonparametric": comp["test_nonparametric"]["name"],
        "p_value_nonparametric": comp["test_nonparametric"]["p_value"],
        "paired": comp["paired"],
    }


def metric_table(runs: pd.DataFrame, column: str, metric_name: str) -> pd.DataFrame:
    rows, pvals = [], []
    for s in SCENARIOS:
        sub = runs[runs.scenario == s]
        b = sub[sub.method == "baseline"].sort_values("repetition")[column].to_numpy()
        f = sub[sub.method == "framework"].sort_values("repetition")[column].to_numpy()
        comp = st.compare_groups(b, f, paired=PAIRED)
        rows.append(_row(s, metric_name, comp))
        pvals.append(comp["test"]["p_value"])
    b_all = runs[runs.method == "baseline"][column].to_numpy()
    f_all = runs[runs.method == "framework"][column].to_numpy()
    rows.append(_row("pooled", metric_name,
                     st.compare_groups(b_all, f_all, paired=PAIRED)))
    holm = st.holm_bonferroni(pvals)
    df = pd.DataFrame(rows)
    df["p_value_holm"] = holm["p_adjusted"] + [float("nan")]
    return df


def nri_table(runs: pd.DataFrame) -> pd.DataFrame:
    rows, pvals = [], []
    for s in SCENARIOS + ["pooled"]:
        sub = runs if s == "pooled" else runs[runs.scenario == s]
        b = sub[sub.method == "baseline"].sort_values(["scenario", "repetition"])["nri"].to_numpy()
        f = sub[sub.method == "framework"].sort_values(["scenario", "repetition"])["nri"].to_numpy()
        comp = st.compare_groups(b, f, paired=PAIRED)
        # NRI is higher-is-better: report the gain and the deficit reduction.
        bm, fm = comp["baseline"]["mean"], comp["framework"]["mean"]
        rows.append({
            "scenario": s,
            "n": comp["baseline"]["n"],
            "baseline_mean": bm, "baseline_sd": comp["baseline"]["sd"],
            "baseline_ci95_lo": comp["baseline"]["ci95_lo"],
            "baseline_ci95_hi": comp["baseline"]["ci95_hi"],
            "framework_mean": fm, "framework_sd": comp["framework"]["sd"],
            "framework_ci95_lo": comp["framework"]["ci95_lo"],
            "framework_ci95_hi": comp["framework"]["ci95_hi"],
            "absolute_gain": fm - bm,
            "relative_gain_pct": 100.0 * (fm - bm) / bm if bm else float("nan"),
            "deficit_baseline": 1 - bm, "deficit_framework": 1 - fm,
            "deficit_reduction_pct": (100.0 * ((1 - bm) - (1 - fm)) / (1 - bm)
                                      if (1 - bm) else float("nan")),
            "hedges_g": comp["hedges_g"], "cliffs_delta": comp["cliffs_delta"],
            "test": comp["test"]["name"], "p_value": comp["test"]["p_value"],
        })
        if s != "pooled":
            pvals.append(comp["test"]["p_value"])
    df = pd.DataFrame(rows)
    df["p_value_holm"] = st.holm_bonferroni(pvals)["p_adjusted"] + [float("nan")]
    return df


def integrity_table(conf: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for _, r in conf.iterrows():
        m = st.classification_metrics(int(r.tp), int(r.tn), int(r.fp), int(r.fn))
        rows.append({"scenario": r.scenario, "corruption_fraction": r.corruption_fraction,
                     "observation_unit": r.observation_unit, **_flatten(m)})
    for s in SCENARIOS:
        sub = conf[conf.scenario == s]
        m = st.classification_metrics(int(sub.tp.sum()), int(sub.tn.sum()),
                                      int(sub.fp.sum()), int(sub.fn.sum()))
        rows.append({"scenario": s, "corruption_fraction": "all",
                     "observation_unit": "challenged_telemetry_block", **_flatten(m)})
    m = st.classification_metrics(int(conf.tp.sum()), int(conf.tn.sum()),
                                  int(conf.fp.sum()), int(conf.fn.sum()))
    rows.append({"scenario": "pooled", "corruption_fraction": "all",
                 "observation_unit": "challenged_telemetry_block", **_flatten(m)})
    return pd.DataFrame(rows)


def _flatten(m: dict) -> dict:
    out = {}
    for k, v in m.items():
        if isinstance(v, tuple):
            out[f"{k}_lo"], out[f"{k}_hi"] = v
        else:
            out[k] = v
    return out


def overhead_table(res: pd.DataFrame, cluster_capacity: dict) -> pd.DataFrame:
    """Eq. (17) overhead plus the share-of-capacity denominator.

    The manuscript uses Eq. (17) (relative to baseline consumption) in Section 2.8
    and 'share of cluster capacity' in Section 3.2. Both are reported here so the
    denominator of every overhead number is unambiguous.
    """
    rows = []
    metrics = [c for c in res.columns
               if c not in {"run_id", "scenario", "method", "repetition", "data_origin"}]
    for metric in metrics:
        b = res[res.method == "baseline"][metric].to_numpy(float)
        f = res[res.method == "framework"][metric].to_numpy(float)
        b, f = b[~np.isnan(b)], f[~np.isnan(f)]
        if b.size == 0 or f.size == 0:
            rows.append({"metric": metric, "baseline_mean": float("nan"),
                         "framework_mean": float(f.mean()) if f.size else float("nan"),
                         "note": "component absent in the baseline arm"})
            continue
        db, df_ = st.describe(b), st.describe(f)
        rel = 100.0 * (df_["mean"] - db["mean"]) / db["mean"]
        boot = st.bootstrap_ci(f - b[:f.size]) if b.size == f.size else None
        cap = cluster_capacity.get(metric)
        rows.append({
            "metric": metric,
            "baseline_mean": db["mean"], "baseline_sd": db["sd"],
            "baseline_p95": float(np.percentile(b, 95)),
            "framework_mean": df_["mean"], "framework_sd": df_["sd"],
            "framework_p95": float(np.percentile(f, 95)),
            "absolute_difference": df_["mean"] - db["mean"],
            "relative_overhead_pct_eq17": rel,
            "diff_ci95_lo": boot["ci95_lo"] if boot else None,
            "diff_ci95_hi": boot["ci95_hi"] if boot else None,
            "cluster_capacity": cap,
            "share_of_capacity_pct": (100.0 * (df_["mean"] - db["mean"]) / cap
                                      if cap else None),
        })
    return pd.DataFrame(rows)


def ablation_table(abl: pd.DataFrame) -> pd.DataFrame:
    g = abl.groupby("variant")
    df = pd.DataFrame({
        "detection_latency_mean_s": g["detection_latency_s"].mean(),
        "detection_latency_sd_s": g["detection_latency_s"].std(ddof=1),
        "recovery_time_mean_s": g["recovery_time_s"].mean(),
        "recovery_time_sd_s": g["recovery_time_s"].std(ddof=1),
        "unsafe_action_rate": g["unsafe_action"].mean(),
        "policy_violation_rate": g["policy_violation"].mean(),
        "rollback_rate": g["rollback"].mean(),
        "recovery_success_rate": g["recovery_success"].mean(),
        "orchestration_decision_latency_mean_ms": g["orchestration_decision_latency_ms"].mean(),
        "twin_prediction_error_mean": g["twin_prediction_error"].mean(),
        "risk_ranking_accuracy": g["risk_ranking_correct"].mean(),
        "n": g.size(),
    }).reset_index()
    for col, num in [("unsafe_action_rate", "unsafe_action"),
                     ("policy_violation_rate", "policy_violation"),
                     ("rollback_rate", "rollback"),
                     ("recovery_success_rate", "recovery_success"),
                     ("risk_ranking_accuracy", "risk_ranking_correct")]:
        lo, hi = [], []
        for v in df.variant:
            sub = abl[abl.variant == v]
            a, b = st.wilson_ci(int(sub[num].sum()), len(sub))
            lo.append(a); hi.append(b)
        df[f"{col}_ci95_lo"], df[f"{col}_ci95_hi"] = lo, hi
    return df


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--data", default="data")
    ap.add_argument("--out", default="results")
    args = ap.parse_args()
    data, out = Path(args.data), Path(args.out)
    out.mkdir(parents=True, exist_ok=True)

    runs = pd.read_csv(data / "run_level_metrics.csv")
    conf = pd.read_csv(data / "confusion_matrices" / "integrity_confusion.csv")
    res = pd.read_csv(data / "resource_measurements" / "resource_usage.csv")
    abl = pd.read_csv(data / "ablation_runs.csv")

    # Cluster capacity of the testbed described in Table 2 (4 edge nodes + 3 VMs).
    capacity = {"cpu_pct": 700.0, "ram_mb": 80384.0,
                "network_kbps": 1000000.0, "storage_mb_per_h": 4096.0}

    t_det = metric_table(runs, "detection_latency_s", "detection_latency_s")
    t_rec = metric_table(runs, "recovery_time_s", "recovery_time_s")
    t_nri = nri_table(runs)
    t_int = integrity_table(conf)
    t_ovh = overhead_table(res, capacity)
    t_abl = ablation_table(abl)

    t_det.to_csv(out / "table_S1_detection_latency.csv", index=False)
    t_rec.to_csv(out / "table_S2_recovery_time.csv", index=False)
    t_nri.to_csv(out / "table_S3_nri.csv", index=False)
    t_int.to_csv(out / "table_S4_integrity.csv", index=False)
    t_ovh.to_csv(out / "table_S5_overhead.csv", index=False)
    t_abl.to_csv(out / "table_S6_ablation.csv", index=False)

    pooled_det = t_det[t_det.scenario == "pooled"].iloc[0]
    pooled_rec = t_rec[t_rec.scenario == "pooled"].iloc[0]
    s3 = t_nri[t_nri.scenario == "S3"].iloc[0]
    pooled_int = t_int[t_int.scenario == "pooled"].iloc[0]
    summary = {
        "data_origin": str(runs.data_origin.iloc[0]),
        "n_per_cell": int(pooled_det.n_baseline / len(SCENARIOS)),
        "detection_latency_s": {
            "baseline_mean": float(pooled_det.baseline_mean),
            "baseline_ci95": [float(pooled_det.baseline_ci95_lo),
                              float(pooled_det.baseline_ci95_hi)],
            "framework_mean": float(pooled_det.framework_mean),
            "framework_ci95": [float(pooled_det.framework_ci95_lo),
                               float(pooled_det.framework_ci95_hi)],
            "relative_reduction_pct": float(pooled_det.rel_reduction_pct),
            "hedges_g": float(pooled_det.hedges_g),
            "p_value": float(pooled_det.p_value)},
        "recovery_time_s": {
            "baseline_mean": float(pooled_rec.baseline_mean),
            "baseline_ci95": [float(pooled_rec.baseline_ci95_lo),
                              float(pooled_rec.baseline_ci95_hi)],
            "framework_mean": float(pooled_rec.framework_mean),
            "framework_ci95": [float(pooled_rec.framework_ci95_lo),
                               float(pooled_rec.framework_ci95_hi)],
            "relative_reduction_pct": float(pooled_rec.rel_reduction_pct),
            "hedges_g": float(pooled_rec.hedges_g),
            "p_value": float(pooled_rec.p_value)},
        "nri_S3": {
            "baseline_mean": float(s3.baseline_mean),
            "baseline_ci95": [float(s3.baseline_ci95_lo), float(s3.baseline_ci95_hi)],
            "framework_mean": float(s3.framework_mean),
            "framework_ci95": [float(s3.framework_ci95_lo), float(s3.framework_ci95_hi)],
            "relative_gain_pct": float(s3.relative_gain_pct),
            "deficit_reduction_pct": float(s3.deficit_reduction_pct)},
        "integrity_pooled": {
            "n": int(pooled_int.n), "accuracy": float(pooled_int.accuracy),
            "accuracy_ci95": [float(pooled_int.accuracy_ci95_lo),
                              float(pooled_int.accuracy_ci95_hi)],
            "recall": float(pooled_int.recall), "precision": float(pooled_int.precision),
            "specificity": float(pooled_int.specificity),
            "f1": float(pooled_int.f1), "mcc": float(pooled_int.mcc),
            "fpr": float(pooled_int.fpr),
            "fpr_ci95": [float(pooled_int.fpr_ci95_lo), float(pooled_int.fpr_ci95_hi)]},
        "overhead_max_relative_pct_eq17": float(
            t_ovh.relative_overhead_pct_eq17.max(skipna=True)),
        "overhead_max_share_of_capacity_pct": float(
            t_ovh.share_of_capacity_pct.max(skipna=True)),
    }
    (out / "summary.json").write_text(json.dumps(summary, indent=2) + "\n")
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
