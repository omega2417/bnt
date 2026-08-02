"""Close the loop to the publication: map every manuscript ``[DATA REQUIRED]``
item to its computed value and evidence file.

The output (``manuscript_data_map.{md,json}``) is the single place the authors
consult to fill Sections 5-7 of the paper — each row carries the value and the
machine-readable artifact it came from, so no number is ever transcribed by hand.
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

from ..evaluation.statistics import bootstrap_ci
from ..features.pipeline import BASE_NUMERIC_FEATURES, PHASE_FEATURES
from ..logging_utils import get_logger
from .formats import write_table

log = get_logger("reporting")

__all__ = ["build_manuscript_map"]


def build_manuscript_map(run_group: str, out: Path) -> Path:
    md = out / "metrics" / run_group
    tables_dir = out / "tables" / run_group
    figs = f"artifacts/figures/{run_group}"
    tabs = f"artifacts/tables/{run_group}"
    mets = f"artifacts/metrics/{run_group}"

    params = _params(md)
    rows: list[dict] = []

    def add(item: str, value, evidence: str) -> None:
        rows.append({"manuscript_item": item, "value": str(value), "evidence": evidence})

    # -- Parameters (Section 4-5) ------------------------------------------- #
    add("Feature vector dimension d",
        params.get("feature_dimension_d"), f"{tabs}/table_2_parameters.csv")
    add("Final feature list",
        f"{len(BASE_NUMERIC_FEATURES)} numeric + {len(PHASE_FEATURES)} one-hot phase",
        "src/aegis_uav/features/windowing.py")
    add("Fleet size N", params.get("fleet_size_N"), f"{tabs}/table_2_parameters.csv")
    add("Window length Delta (s)", params.get("window_length_delta_s"),
        f"{tabs}/table_2_parameters.csv")
    add("EWMA kappa", params.get("ewma_kappa"), f"{tabs}/table_2_parameters.csv")
    add("EWMA alpha", params.get("ewma_alpha"), f"{tabs}/table_2_parameters.csv")
    add("Severity floor tau_e", params.get("severity_floor_tau_e"),
        f"{tabs}/table_2_parameters.csv")
    add("Modality weights w_m", params.get("modality_weights_w_m"),
        f"{tabs}/table_2_parameters.csv")
    add("Confidence floor pi_min", params.get("confidence_floor_pi_min"),
        f"{tabs}/table_2_parameters.csv")
    add("Utility lambda1", params.get("utility_lambda1"), f"{tabs}/table_2_parameters.csv")
    add("Utility lambda2", params.get("utility_lambda2"), f"{tabs}/table_2_parameters.csv")
    add("Autoencoder architecture",
        f"input -> {params.get('ada_hidden_sizes')} -> latent "
        f"{params.get('ada_latent_dim')} -> mirror -> output",
        "configs/models/ada.yaml")
    add("Attribution classifier",
        f"{params.get('aaa_classifier')} (calibration: {params.get('aaa_calibration')})",
        "configs/models/aaa_hierarchical.yaml")
    add("Number of runs / seeds",
        f"{params.get('n_runs_seeds')} seeds = {params.get('seeds')}",
        f"{tabs}/table_2_parameters.csv")
    add("Train/validation/test split", params.get("train_val_test_split"),
        f"{tabs}/table_2_parameters.csv")
    add("Attack parameters (T1-T6)", "onset/duration/intensity/targets/profile per class",
        "configs/attacks/T1.yaml ... T6.yaml")

    # -- Per-class window counts -------------------------------------------- #
    for split in ("train", "val", "test"):
        counts = {k.split(f"n_windows_{split}_")[1]: v
                  for k, v in params.items() if k.startswith(f"n_windows_{split}_")}
        add(f"Sample (window) counts - {split}", counts, f"{tabs}/table_2_parameters.csv")

    # -- Detection (Table 3, B1/B3) ----------------------------------------- #
    det = _read(md, "detection_per_seed.csv")
    if det is not None:
        for method in ("fused_framework", "telemetry_only", "traffic_only",
                       "behaviour_only", "rf_flow_baseline"):
            sub = det[det["method"] == method]
            if not sub.empty:
                add(f"Detection F1 - {method}", _ci(sub["f1"].values),
                    f"{tabs}/table_3_detection.csv")
        add("Fig. 4 confusion matrix", "leaf-level attribution",
            f"{figs}/fig_4_confusion_matrix.pdf")

    # -- Attribution (Section 6.2) ------------------------------------------ #
    attr = _read(md, "attribution_per_seed.csv")
    if attr is not None:
        for variant in ("hierarchical", "flat"):
            sub = attr[attr["variant"] == variant]
            if not sub.empty:
                add(f"Attribution macro-F1 - {variant}", _ci(sub["macro_f1"].values),
                    f"{mets}/attribution_per_seed.csv")
                add(f"Attribution leaf accuracy - {variant}",
                    _ci(sub["leaf_accuracy"].values), f"{mets}/attribution_per_seed.csv")
        add("Calibration (ECE / Brier)",
            f"ECE={_ci(attr[attr.variant=='hierarchical']['ece'].values)}, "
            f"Brier={_ci(attr[attr.variant=='hierarchical']['brier'].values)}",
            f"{mets}/attribution_per_seed.csv")

    # -- Response / containment (Table 5) ----------------------------------- #
    resp = _read(md, "response_per_seed.csv")
    if resp is not None:
        for policy in ("utility_rsa", "static_policy"):
            sub = resp[resp["policy"] == policy]
            if not sub.empty:
                add(f"Contained-before-impact - {policy}",
                    _ci(sub["contained_before_impact_rate"].values),
                    f"{tabs}/table_5_containment.csv")
        add("Table 4 ablation", "component removal deltas", f"{tabs}/table_4_ablation.csv")

    # -- Overhead / scalability (Table 6) ----------------------------------- #
    over = _read(md, "overhead_per_seed.csv")
    if over is not None:
        add("Processing latency (ms/window)", _ci(over["processing_latency_ms"].values),
            f"{tabs}/table_6_overhead.csv")
        add("RAM (MB)", _ci(over["ram_mb"].values), f"{tabs}/table_6_overhead.csv")
        add("Probe bandwidth (kbps/UAV)", _ci(over["probe_bandwidth_kbps"].values),
            f"{tabs}/table_6_overhead.csv")
    if (md / "scalability.csv").exists():
        add("Scalability plot (N=5..80)", "per-window latency / RAM / bandwidth",
            f"{figs}/scalability.pdf")
    if (md / "sensitivity.csv").exists():
        add("Sensitivity plots", "kappa, alpha, Delta, w_m, tau_e, lambda1, lambda2, pi_min",
            f"{figs}/sensitivity.pdf")

    # -- Statistics / error analysis / data availability -------------------- #
    if (tables_dir / "statistical_test_report.csv").exists():
        add("Statistical tests (Wilcoxon + Holm, effect sizes)",
            "paired comparisons across seeds", f"{tabs}/statistical_test_report.csv")
    if (tables_dir / "error_analysis.csv").exists():
        add("Error analysis", "per-class recall + most-confused class",
            f"{tabs}/error_analysis.csv")
    add("Fig. 5 detection/containment latency", "per attack class with 95% CI",
        f"{figs}/fig_5_latency.pdf")
    add("Data availability",
        f"aegis campaign --config configs/experiments/{run_group}.yaml; manifests in "
        "artifacts/manifests/", "README.md")

    df = pd.DataFrame(rows)
    write_table(df, tables_dir / "manuscript_data_map",
                caption="Mapping of manuscript [DATA REQUIRED] items to computed values.")
    with open(tables_dir / "manuscript_data_map.json", "w") as fh:
        json.dump(rows, fh, indent=2, default=str)
    log.info("manuscript data map written (%d items) for %s", len(rows), run_group)
    return tables_dir / "manuscript_data_map.md"


def _params(md: Path) -> dict:
    p = md / "parameters.csv"
    if not p.exists():
        return {}
    df = pd.read_csv(p)
    return dict(zip(df["parameter"], df["value"], strict=True))


def _read(md: Path, name: str) -> pd.DataFrame | None:
    p = md / name
    return pd.read_csv(p) if p.exists() else None


def _ci(values: np.ndarray) -> str:
    vals = np.asarray(values, dtype=float)
    vals = vals[~np.isnan(vals)]
    if len(vals) == 0:
        return "n/a"
    point, lo, hi = bootstrap_ci(vals, seed=0)
    return f"{point:.3f} [{lo:.3f}, {hi:.3f}]"
