"""End-to-end and reporting integration tests."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from aegis_uav.config import config_hash, load_experiment, load_scenario
from aegis_uav.schemas import ExperimentConfig


def test_config_hash_stable_and_sensitive():
    e1 = ExperimentConfig()
    e2 = ExperimentConfig()
    assert config_hash(e1) == config_hash(e2)
    e2.ada.kappa = 9.9
    assert config_hash(e1) != config_hash(e2)


def test_smoke_config_loads():
    exp = load_experiment("configs/experiments/smoke.yaml")
    scenario = load_scenario(exp.scenario)
    assert exp.run_group == "smoke"
    assert scenario.fleet_size >= 1
    assert abs(exp.dataset.train_frac + exp.dataset.val_frac + exp.dataset.test_frac - 1.0) < 1e-6


@pytest.mark.slow
def test_run_core_produces_all_blocks():
    from aegis_uav.experiments.pipeline import run_core

    exp = load_experiment("configs/experiments/smoke.yaml")
    exp.dataset.missions_per_class = 3  # minimum for a train/val/test split
    scenario = load_scenario(exp.scenario)
    res = run_core(scenario, exp, seed=0)
    assert 55 <= res.feature_dim <= 85
    assert "fused_framework" in res.detection
    for key in ("precision", "recall", "f1", "fpr"):
        assert 0.0 <= res.detection["fused_framework"][key] <= 1.0
    assert "hierarchical" in res.attribution and "flat" in res.attribution
    assert res.confusion is not None
    assert res.overhead["processing_latency_ms"] > 0


def test_reporting_from_synthetic_metrics(tmp_path):
    """build_report must generate tables/figures from metrics CSVs alone."""
    from aegis_uav import ALL_LABELS
    from aegis_uav.reporting.report import build_report

    rg = "unit"
    md = tmp_path / "metrics" / rg
    md.mkdir(parents=True)
    seeds = [0, 1, 2]
    det_rows = []
    for s in seeds:
        for method, f1 in (("fused_framework", 0.9), ("telemetry_only", 0.5),
                           ("traffic_only", 0.6), ("behaviour_only", 0.7),
                           ("rf_flow_baseline", 0.55)):
            det_rows.append({"seed": s, "method": method, "precision": f1, "recall": f1,
                             "f1": f1 + 0.01 * s, "fpr": 0.02, "auroc": 0.95, "auprc": 0.9})
    pd.DataFrame(det_rows).to_csv(md / "detection_per_seed.csv", index=False)
    pd.DataFrame([{"seed": s, "method": m, **{c: 0.8 for c in
                  ("T1", "T2", "T3", "T4", "T5", "T6")}}
                  for s in seeds for m in ("fused_framework",)]
                 ).to_csv(md / "detection_per_class_recall.csv", index=False)
    pd.DataFrame([{"seed": s, "variant": v, "leaf_accuracy": 0.9, "macro_accuracy": 0.9,
                   "macro_f1": 0.8 if v == "hierarchical" else 0.5, "ece": 0.05, "brier": 0.03}
                  for s in seeds for v in ("hierarchical", "flat")]
                 ).to_csv(md / "attribution_per_seed.csv", index=False)
    pd.DataFrame([{"seed": s, "policy": p, "n_incidents": 10, "n_attack_incidents": 6,
                   "contained_before_impact_rate": 0.7, "harmful_response_rate": 0.0,
                   "unnecessary_response_rate": 0.0, "escalation_rate": 0.2,
                   "rollback_rate": 0.05, "origin_accuracy": 0.6,
                   "attribution_accuracy_incident": 0.85}
                  for s in seeds for p in ("utility_rsa", "static_policy")]
                 ).to_csv(md / "response_per_seed.csv", index=False)
    pd.DataFrame([{"seed": s, "policy": "utility_rsa", "latency_s": 1.2} for s in seeds]
                 ).to_csv(md / "containment_latency.csv", index=False)
    pd.DataFrame([{"seed": s, "attack_class": "T1", "latency_s": 2.0} for s in seeds]
                 ).to_csv(md / "detection_latency.csv", index=False)
    pd.DataFrame([{"seed": s, "processing_latency_ms": 1.5, "cpu_percent": 50.0,
                   "ram_mb": 200.0, "probe_bandwidth_kbps": 10.0,
                   "throughput_windows_per_s": 500.0, "fleet_size": 6} for s in seeds]
                 ).to_csv(md / "overhead_per_seed.csv", index=False)
    cm = np.eye(len(ALL_LABELS), dtype=int) * 10
    pd.DataFrame(cm, index=list(ALL_LABELS), columns=list(ALL_LABELS)).to_csv(
        md / "confusion_matrix.csv")
    pd.DataFrame([{"parameter": "feature_dimension_d", "value": 60}]).to_csv(
        md / "parameters.csv", index=False)

    report_dir = build_report(rg, tmp_path)
    assert (report_dir / "table_3_detection.csv").exists()
    assert (report_dir / "table_3_detection.tex").exists()
    assert (report_dir / "table_3_detection.md").exists()
    assert (tmp_path / "figures" / rg / "fig_4_confusion_matrix.png").exists()
    assert (tmp_path / "figures" / rg / "fig_5_latency.svg").exists()
