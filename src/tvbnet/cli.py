"""Command-line driver: python -m tvbnet.cli all --config config/pipeline.yaml --out build"""
from __future__ import annotations

import argparse
import json
import os
import platform
import time
from datetime import datetime, timezone

import numpy as np
import pandas as pd

from . import release as Q
from . import validate as V
from .design import L9, l9_balance
from .package import verify_checksums, write_package
from .pipeline import load_config, run

FACTORS = ["topology", "family", "depth", "effectiveness_mean", "input_reliability", "impact_multiplier", "budget_fraction"]


def eta_squared(df: pd.DataFrame, y: str) -> dict:
    d = df[np.isfinite(df[y])]
    sst = ((d[y] - d[y].mean()) ** 2).sum()
    return {f: float(d.groupby(f)[y].agg(lambda s: len(s) * (s.mean() - d[y].mean()) ** 2).sum() / sst) for f in FACTORS}


def ts():
    return datetime.now(timezone.utc).isoformat()


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("stage", choices=["all"])
    ap.add_argument("--config", default="config/pipeline.yaml")
    ap.add_argument("--out", default="build")
    ap.add_argument("--workers", type=int, default=None)
    a = ap.parse_args(argv)
    cfg = load_config(a.config)
    os.makedirs(a.out, exist_ok=True)
    acts, rep = [], {"release": cfg["release"], "seed": cfg["seed"], "python": platform.python_version(),
                     "numpy": np.__version__, "pandas": pd.__version__,
                     "PROVENANCE_WARNING": "SYNTHETIC REHEARSAL: no row in this package is an operational measurement."}
    t0 = ts(); tic = time.time()
    res = run(cfg, a.workers)
    clean = res["tables"]
    acts.append({"name": "generate_and_derive", "start": t0, "end": ts(), "used": ["config/pipeline.yaml"],
                 "generated": [f"tables/{t}.parquet" for t in clean]})
    rep["runtime_generate_s"] = time.time() - tic
    rep["design"] = {"cells": int(clean["scenarios"]["cell_id"].nunique()), "scenarios": len(clean["scenarios"]),
                     "l9_pairwise_balanced": l9_balance(L9)}
    rep["counts"] = {t: int(len(df)) for t, df in clean.items()}

    # ---- raw delivery with injected defects
    t0 = ts()
    raw, log = Q.inject(clean, cfg)
    s_raw = V.structural_checks(raw)
    c_raw = V.consistency_checks(raw, cfg)
    acts.append({"name": "inject_and_validate_raw", "start": t0, "end": ts(), "used": [f"tables/{t}.parquet" for t in clean],
                 "generated": ["report/validation_report.json#raw"]})
    # ---- quarantine and deterministic redelivery
    t0 = ts()
    q = Q.quarantine_and_redeliver(raw, clean, cfg)
    det = Q.detection_metrics(log, q)
    rel = q["tables"]
    eq = []
    for t in clean:
        pk = V.SCHEMA[t][0]; by = list(pk) if isinstance(pk, tuple) else [pk]
        eq.append(Q.table_digest(clean[t].sort_values(by)[clean[t].columns]) ==
                  Q.table_digest(rel[t].sort_values(by)[clean[t].columns]))
    equiv = float(np.mean(eq))
    acts.append({"name": "quarantine_redeliver", "start": t0, "end": ts(), "used": ["raw delivery"],
                 "generated": [f"tables/{t}.parquet" for t in rel]})
    s_rel = V.structural_checks(rel)
    c_rel = V.consistency_checks(rel, cfg)
    inv = V.invariance_check(rel, cfg)
    man = Q.manifests(rel["scenarios"], cfg)
    aud = Q.audit_manifests(rel["scenarios"], man, cfg)
    t0 = ts()
    pkg = write_package(f"{a.out}/dataset", rel, man, cfg, acts + [{"name": "package", "start": t0, "end": ts(),
                        "used": [f"tables/{t}.parquet" for t in rel], "generated": ["ro-crate-metadata.json", "checksums_sha256.txt"]}])
    ck = verify_checksums(f"{a.out}/dataset")
    rep["gates_raw"] = Q.gates(s_raw, c_raw, None, aud, inv, ck, None)
    rep["gates_release"] = Q.gates(s_rel, c_rel, det, aud, inv, ck, equiv)
    rep["defect_detection"] = det
    rep["quarantine_counts"] = {t: len(v) for t, v in q["flags"].items() if v}
    rep["consistency"] = {"max_rel_err": c_rel["max_rel_err"], "n_checked": c_rel["n_checked"],
                          "monotonicity_violations": c_rel["monotonicity_violations"],
                          "dominance_violations": c_rel["dominance_violations"]}
    rep["invariance"] = inv
    rep["manifests"] = aud
    rep["package"] = pkg
    rep["completeness_release"] = s_rel["metrics"]["completeness"]

    # ---- analyses reported in the Descriptor (all model-derived)
    sc, cf = rel["scenarios"], rel["configurations"]
    piv = cf.pivot_table(index="scenario_id", columns="method", values="relative_residual_risk")
    gap = cf.pivot_table(index="scenario_id", columns="method", values="optimality_gap")
    d = sc.set_index("scenario_id").join(piv["exact"].rename("rrr_exact")).join(
        gap["exact_est"].rename("regret_exact_est")).join(gap["greedy_est"].rename("regret_greedy_est"))
    d["log_rrr"] = np.log10(d["rrr_exact"])
    feas = cf.pivot_table(index="scenario_id", columns="method", values="feasible")
    d["viol_exact_est"] = ~feas["exact_est"].astype(bool)
    rep["methods"] = {m: {"median_gap": float(gap[m].median()), "p95_gap": float(gap[m].quantile(0.95)),
                          "share_optimal": float((gap[m].abs() <= 1e-12).mean()),
                          "median_rrr": float(piv[m].median()),
                          "feasible_share": float(feas[m].astype(bool).mean())} for m in piv.columns}
    rep["by_reliability"] = {str(r): {"median_regret_exact_est": float(g["regret_exact_est"].median()),
                                      "p90_regret_exact_est": float(g["regret_exact_est"].quantile(0.9)),
                                      "mean_regret_exact_est": float(g["regret_exact_est"].mean()),
                                      "median_regret_greedy_est": float(g["regret_greedy_est"].median()),
                                      "budget_violation_rate": float(g["viol_exact_est"].mean())}
                             for r, g in d.groupby("input_reliability")}
    rep["by_budget"] = {str(b): float(g["rrr_exact"].median()) for b, g in d.groupby("budget_fraction")}
    rep["by_depth"] = {str(b): float(g["rrr_exact"].median()) for b, g in d.groupby("depth")}
    rep["by_effectiveness"] = {str(b): float(g["rrr_exact"].median()) for b, g in d.groupby("effectiveness_mean")}
    rep["eta2_log_rrr"] = eta_squared(d, "log_rrr")
    rep["eta2_regret"] = eta_squared(d, "regret_exact_est")
    ex = cf[cf.method == "exact"]
    rep["exact_indicators"] = {k: {"median": float(ex[k].median()), "p05": float(ex[k].quantile(0.05)),
                                   "p95": float(ex[k].quantile(0.95))}
                               for k in ["ch_coverage", "mean_coverage_depth", "mean_threat_coverage",
                                         "min_threat_coverage", "rosi", "n_selected", "n_layers_used"]}
    rep["degenerate_budget_share"] = float((ex["n_selected"] == 0).mean())
    rep["frontier_size"] = {"median": float(sc["frontier_size"].median()), "min": int(sc["frontier_size"].min()),
                            "max": int(sc["frontier_size"].max()), "total_points": int(len(rel["frontier"]))}
    rep["baseline_risk"] = {"median": float(sc["baseline_risk_kcu"].median()),
                            "p05": float(sc["baseline_risk_kcu"].quantile(0.05)),
                            "p95": float(sc["baseline_risk_kcu"].quantile(0.95))}
    os.makedirs(f"{a.out}/report", exist_ok=True)
    json.dump(rep, open(f"{a.out}/report/validation_report.json", "w"), indent=2, default=float)
    json.dump({k: v for k, v in res["cascades"].items()}, open(f"{a.out}/report/cascades.json", "w"))
    print(json.dumps({"gates_release": [(g["gate"], g["status"]) for g in rep["gates_release"]],
                      "runtime_s": rep["runtime_generate_s"]}, indent=1))


if __name__ == "__main__":
    main()
