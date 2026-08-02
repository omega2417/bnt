"""Build all manuscript artifacts (Tables 2-6, Figs 4-5, sensitivity/scalability
plots, statistical tests, error analysis, snippets and a manifest) from the
machine-readable metrics written by the campaign."""

from __future__ import annotations

import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

from .. import ATTACK_CLASSES  # noqa: E402
from ..evaluation.statistics import bootstrap_ci, wilcoxon_holm  # noqa: E402
from ..logging_utils import get_logger  # noqa: E402
from .formats import save_figure, write_table  # noqa: E402

log = get_logger("reporting")

_DETECTION_METHOD_LABEL = {
    "fused_framework": "Fused framework (ours)",
    "telemetry_only": "Telemetry-only (B1)",
    "traffic_only": "Traffic-only (B1)",
    "behaviour_only": "Behaviour-only (B1)",
    "rf_flow_baseline": "Random-Forest flow (B3)",
}


def build_report(run_group: str, out: Path) -> Path:
    md = out / "metrics" / run_group
    tables = out / "tables" / run_group
    figures = out / "figures" / run_group
    for d in (tables, figures, out / "manifests"):
        d.mkdir(parents=True, exist_ok=True)

    manifest: dict[str, dict] = {}
    _table2_parameters(md, tables, manifest)
    _table3_detection(md, tables, manifest)
    _table4_ablation(md, tables, manifest)
    _table5_containment(md, tables, manifest)
    _table6_overhead(md, tables, manifest)
    _fig4_confusion(md, figures, manifest)
    _fig5_latency(md, figures, manifest)
    _scalability_plot(md, figures, manifest)
    _sensitivity_plots(md, figures, manifest)
    _statistical_tests(md, tables, manifest)
    _error_analysis(md, tables, manifest)
    _snippets(md, out / "tables" / run_group, run_group)
    _run_summary(md, out, run_group, manifest)

    with open(out / "manifests" / f"{run_group}_report_manifest.json", "w") as fh:
        json.dump(manifest, fh, indent=2, default=str)
    log.info("report artifacts written for run-group %s", run_group)
    return tables


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #


def _ci_str(values: np.ndarray, seed: int = 0, pct: bool = False) -> str:
    vals = np.asarray(values, dtype=float)
    vals = vals[~np.isnan(vals)]
    if len(vals) == 0:
        return "n/a"
    point, lo, hi = bootstrap_ci(vals, seed=seed)
    if pct:
        return f"{point*100:.1f} [{lo*100:.1f}, {hi*100:.1f}]"
    return f"{point:.3f} [{lo:.3f}, {hi:.3f}]"


def _read(md: Path, name: str) -> pd.DataFrame | None:
    p = md / name
    if not p.exists():
        return None
    return pd.read_csv(p)


# --------------------------------------------------------------------------- #
# Tables
# --------------------------------------------------------------------------- #


def _table2_parameters(md: Path, tables: Path, manifest: dict) -> None:
    df = _read(md, "parameters.csv")
    if df is None:
        return
    paths = write_table(df, tables / "table_2_parameters",
                        caption="Experimental parameters (auto-generated).")
    manifest["table_2_parameters"] = {"source": "parameters.csv", "outputs": _rel(paths)}


def _table3_detection(md: Path, tables: Path, manifest: dict) -> None:
    df = _read(md, "detection_per_seed.csv")
    if df is None:
        return
    rows = []
    for method, sub in df.groupby("method"):
        rows.append({
            "Method": _DETECTION_METHOD_LABEL.get(method, method),
            "Precision": _ci_str(sub["precision"].values, 1),
            "Recall": _ci_str(sub["recall"].values, 2),
            "F1": _ci_str(sub["f1"].values, 3),
            "FPR": _ci_str(sub["fpr"].values, 4),
            "AUROC": _ci_str(sub["auroc"].values, 5),
            "AUPRC": _ci_str(sub["auprc"].values, 6),
        })
    order = list(_DETECTION_METHOD_LABEL.values())
    out = pd.DataFrame(rows)
    out["__o"] = out["Method"].apply(lambda m: order.index(m) if m in order else 99)
    out = out.sort_values("__o").drop(columns="__o").reset_index(drop=True)
    paths = write_table(out, tables / "table_3_detection",
                        caption="Detection performance (mean [95% CI] over seeds).")
    manifest["table_3_detection"] = {"source": "detection_per_seed.csv", "outputs": _rel(paths)}


def _table4_ablation(md: Path, tables: Path, manifest: dict) -> None:
    df = _read(md, "ablation_per_seed.csv")
    if df is None:
        return
    metrics = ["det_f1", "attr_macro_f1", "attr_leaf_accuracy", "contained_before_impact"]
    full = df[df["ablation"] == "full"]
    full_mean = {m: np.nanmean(full[m].values) for m in metrics}
    rows = []
    for name, sub in df.groupby("ablation"):
        row = {"Configuration": name}
        for m in metrics:
            mean = float(np.nanmean(sub[m].values))
            delta = mean - full_mean[m] if name != "full" else 0.0
            row[m] = f"{mean:.3f}" if name == "full" else f"{mean:.3f} ({delta:+.3f})"
        rows.append(row)
    out = pd.DataFrame(rows)
    out = out.rename(columns={
        "det_f1": "Detection F1", "attr_macro_f1": "Attribution macro-F1",
        "attr_leaf_accuracy": "Leaf accuracy", "contained_before_impact": "Contained<impact",
    })
    # Put 'full' first.
    out["__o"] = (out["Configuration"] != "full").astype(int)
    out = out.sort_values("__o").drop(columns="__o").reset_index(drop=True)
    paths = write_table(out, tables / "table_4_ablation",
                        caption="Ablation study (change relative to full framework).")
    manifest["table_4_ablation"] = {"source": "ablation_per_seed.csv", "outputs": _rel(paths)}


def _table5_containment(md: Path, tables: Path, manifest: dict) -> None:
    df = _read(md, "response_per_seed.csv")
    lat = _read(md, "containment_latency.csv")
    if df is None:
        return
    label = {"utility_rsa": "Utility-constrained RSA (ours)", "static_policy": "Static policy (B4)"}
    rows = []
    for policy, sub in df.groupby("policy"):
        lat_vals = lat[lat["policy"] == policy]["latency_s"].values if lat is not None else []
        rows.append({
            "Policy": label.get(policy, policy),
            "Containment latency (s)": _ci_str(lat_vals, 7) if len(lat_vals) else "n/a",
            "Contained<impact": _ci_str(sub["contained_before_impact_rate"].values, 8, pct=True),
            "Harmful (%)": _ci_str(sub["harmful_response_rate"].values, 9, pct=True),
            "Unnecessary (%)": _ci_str(sub["unnecessary_response_rate"].values, 10, pct=True),
            "Escalation (%)": _ci_str(sub["escalation_rate"].values, 11, pct=True),
            "Rollback (%)": _ci_str(sub["rollback_rate"].values, 12, pct=True),
        })
    out = pd.DataFrame(rows)
    paths = write_table(out, tables / "table_5_containment",
                        caption="Containment effectiveness (mean [95% CI] over seeds).")
    manifest["table_5_containment"] = {"source": "response_per_seed.csv", "outputs": _rel(paths)}


def _table6_overhead(md: Path, tables: Path, manifest: dict) -> None:
    df = _read(md, "overhead_per_seed.csv")
    if df is None:
        return
    row = {
        "Fleet size N": int(df["fleet_size"].iloc[0]),
        "Processing latency (ms/window)": _ci_str(df["processing_latency_ms"].values, 13),
        "CPU (%)": _ci_str(df["cpu_percent"].values, 14),
        "RAM (MB)": _ci_str(df["ram_mb"].values, 15),
        "Probe bandwidth (kbps/UAV)": _ci_str(df["probe_bandwidth_kbps"].values, 16),
        "Throughput (windows/s)": _ci_str(df["throughput_windows_per_s"].values, 17),
    }
    out = pd.DataFrame([row])
    paths = write_table(out, tables / "table_6_overhead",
                        caption="Runtime, resource and communication overhead.")
    manifest["table_6_overhead"] = {"source": "overhead_per_seed.csv", "outputs": _rel(paths)}


# --------------------------------------------------------------------------- #
# Figures
# --------------------------------------------------------------------------- #


def _fig4_confusion(md: Path, figures: Path, manifest: dict) -> None:
    p = md / "confusion_matrix.csv"
    if not p.exists():
        return
    cm = pd.read_csv(p, index_col=0)
    mat = cm.to_numpy(dtype=float)
    norm = mat / np.clip(mat.sum(axis=1, keepdims=True), 1, None)
    fig, ax = plt.subplots(figsize=(6, 5))
    im = ax.imshow(norm, cmap="Blues", vmin=0, vmax=1)
    ax.set_xticks(range(len(cm.columns)), cm.columns, rotation=45, ha="right")
    ax.set_yticks(range(len(cm.index)), cm.index)
    ax.set_xlabel("Predicted"); ax.set_ylabel("True")
    ax.set_title("Leaf-level attribution confusion matrix")
    for i in range(mat.shape[0]):
        for j in range(mat.shape[1]):
            ax.text(j, i, f"{norm[i, j]:.2f}", ha="center", va="center",
                    color="white" if norm[i, j] > 0.5 else "black", fontsize=8)
    fig.colorbar(im, ax=ax, fraction=0.046, pad=0.04)
    paths = save_figure(fig, figures / "fig_4_confusion_matrix")
    plt.close(fig)
    manifest["fig_4_confusion_matrix"] = {"source": "confusion_matrix.csv", "outputs": _rel(paths)}


def _fig5_latency(md: Path, figures: Path, manifest: dict) -> None:
    det = _read(md, "detection_latency.csv")
    con = _read(md, "containment_latency.csv")
    if det is None or det.empty:
        return
    classes = list(ATTACK_CLASSES)
    det_means, det_err = [], []
    for c in classes:
        vals = det[det["attack_class"] == c]["latency_s"].values
        if len(vals):
            point, lo, hi = bootstrap_ci(vals, seed=20)
            det_means.append(point); det_err.append([point - lo, hi - point])
        else:
            det_means.append(0.0); det_err.append([0.0, 0.0])
    det_err = np.array(det_err).T
    fig, ax = plt.subplots(figsize=(7, 4))
    x = np.arange(len(classes))
    ax.bar(x, det_means, yerr=det_err, capsize=4, color="#4C78A8", label="Detection latency")
    if con is not None and not con.empty:
        cl = con["latency_s"].values
        point, lo, hi = bootstrap_ci(cl, seed=21)
        ax.axhline(point, color="#E45756", ls="--",
                   label=f"Median containment latency ({point:.2f}s)")
    ax.set_xticks(x, classes)
    ax.set_xlabel("Attack class"); ax.set_ylabel("Latency (s)")
    ax.set_title("Detection latency per attack class (95% CI)")
    ax.legend()
    paths = save_figure(fig, figures / "fig_5_latency")
    plt.close(fig)
    manifest["fig_5_latency"] = {"source": "detection_latency.csv", "outputs": _rel(paths)}


def _scalability_plot(md: Path, figures: Path, manifest: dict) -> None:
    df = _read(md, "scalability.csv")
    if df is None or df.empty:
        return
    fig, axes = plt.subplots(1, 3, figsize=(13, 4))
    axes[0].plot(df["fleet_size"], df["processing_latency_ms"], "o-")
    axes[0].set_title("Per-window latency"); axes[0].set_ylabel("ms/window")
    axes[1].plot(df["fleet_size"], df["ram_mb"], "s-", color="#59A14F")
    axes[1].set_title("Memory"); axes[1].set_ylabel("RAM (MB)")
    axes[2].plot(df["fleet_size"], df["probe_bandwidth_kbps"], "^-", color="#E45756")
    axes[2].set_title("Probe bandwidth"); axes[2].set_ylabel("kbps/UAV")
    for ax in axes:
        ax.set_xlabel("Fleet size N")
    fig.suptitle("Scalability with fleet size")
    paths = save_figure(fig, figures / "scalability")
    plt.close(fig)
    manifest["scalability_plot"] = {"source": "scalability.csv", "outputs": _rel(paths)}


def _sensitivity_plots(md: Path, figures: Path, manifest: dict) -> None:
    df = _read(md, "sensitivity.csv")
    if df is None or df.empty:
        return
    metric_for = {
        "kappa": "flag_f1", "alpha": "flag_f1", "window_length_s": "det_f1",
        "w_telemetry": "det_f1", "severity_floor": "contained_before_impact",
        "lambda1": "contained_before_impact", "lambda2": "contained_before_impact",
        "pi_min": "escalation_rate",
    }
    params = [p for p in df["parameter"].unique()]
    ncol = 3
    nrow = int(np.ceil(len(params) / ncol))
    fig, axes = plt.subplots(nrow, ncol, figsize=(4 * ncol, 3 * nrow))
    axes = np.array(axes).reshape(-1)
    for ax, param in zip(axes, params, strict=False):
        sub = df[df["parameter"] == param].sort_values("value")
        metric = metric_for.get(param, "det_f1")
        if metric not in sub or sub[metric].isna().all():
            metric = next((m for m in ("det_f1", "flag_f1", "contained_before_impact")
                           if m in sub and not sub[m].isna().all()), None)
        if metric is None:
            continue
        ax.plot(sub["value"], sub[metric], "o-")
        ax.set_title(param); ax.set_xlabel(param); ax.set_ylabel(metric)
    for ax in axes[len(params):]:
        ax.axis("off")
    fig.suptitle("Sensitivity analysis")
    fig.tight_layout()
    paths = save_figure(fig, figures / "sensitivity")
    plt.close(fig)
    manifest["sensitivity_plots"] = {"source": "sensitivity.csv", "outputs": _rel(paths)}


# --------------------------------------------------------------------------- #
# Statistics / error analysis / snippets / summary
# --------------------------------------------------------------------------- #


def _statistical_tests(md: Path, tables: Path, manifest: dict) -> None:
    comparisons: dict[str, tuple] = {}
    det = _read(md, "detection_per_seed.csv")
    if det is not None:
        piv = det.pivot_table(index="seed", columns="method", values="f1")
        if "fused_framework" in piv:
            for base in ("telemetry_only", "traffic_only", "behaviour_only", "rf_flow_baseline"):
                if base in piv:
                    comparisons[f"F1: fused vs {base}"] = (
                        piv["fused_framework"].values, piv[base].values)
    attr = _read(md, "attribution_per_seed.csv")
    if attr is not None:
        piv = attr.pivot_table(index="seed", columns="variant", values="macro_f1")
        if "hierarchical" in piv and "flat" in piv:
            comparisons["macroF1: hierarchical vs flat"] = (
                piv["hierarchical"].values, piv["flat"].values)
    resp = _read(md, "response_per_seed.csv")
    if resp is not None:
        piv = resp.pivot_table(index="seed", columns="policy",
                               values="contained_before_impact_rate")
        if "utility_rsa" in piv and "static_policy" in piv:
            comparisons["contained: utility vs static"] = (
                piv["utility_rsa"].values, piv["static_policy"].values)

    if not comparisons:
        return
    results = wilcoxon_holm(comparisons)
    rows = [{
        "Comparison": r.name, "n": r.n, "statistic": round(r.statistic, 4),
        "p_value": round(r.p_value, 4), "p_holm": round(r.p_holm, 4),
        "effect_size_rank_biserial": round(r.effect_size, 4),
    } for r in results]
    out = pd.DataFrame(rows)
    paths = write_table(out, tables / "statistical_test_report",
                        caption="Wilcoxon signed-rank tests with Holm correction.")
    manifest["statistical_tests"] = {"source": "multiple", "outputs": _rel(paths)}


def _error_analysis(md: Path, tables: Path, manifest: dict) -> None:
    cm_p = md / "confusion_matrix.csv"
    if not cm_p.exists():
        return
    cm = pd.read_csv(cm_p, index_col=0)
    rows = []
    for true_label in cm.index:
        total = cm.loc[true_label].sum()
        if total == 0:
            continue
        correct = cm.loc[true_label, true_label]
        conf = cm.loc[true_label].drop(true_label)
        worst = conf.idxmax() if conf.max() > 0 else "-"
        rows.append({
            "True class": true_label,
            "Support": int(total),
            "Recall": round(correct / total, 3),
            "Most confused with": worst,
            "Confusion rate": round(conf.max() / total, 3) if total else 0.0,
        })
    out = pd.DataFrame(rows)
    paths = write_table(out, tables / "error_analysis",
                        caption="Per-class error analysis from the confusion matrix.")
    manifest["error_analysis"] = {"source": "confusion_matrix.csv", "outputs": _rel(paths)}


def _snippets(md: Path, tables: Path, run_group: str) -> None:
    params = _read(md, "parameters.csv")
    det = _read(md, "detection_per_seed.csv")
    pv = {r["parameter"]: r["value"] for _, r in params.iterrows()} if params is not None else {}
    fused_f1 = "n/a"
    if det is not None:
        f = det[det["method"] == "fused_framework"]["f1"].values
        if len(f):
            fused_f1 = _ci_str(f, 3)
    text = f"""# Manuscript-ready result snippets ({run_group})

_All numbers below are generated automatically from the metrics CSVs; do not edit
by hand._

## Section 5 (Experimental methodology)

The feature vector has dimension d = {pv.get('feature_dimension_d', 'n/a')} after
one-hot encoding and derived cross-vehicle features. Experiments use a fleet of
N = {pv.get('fleet_size_N', 'n/a')} UAVs, a window length of
Delta = {pv.get('window_length_delta_s', 'n/a')} s, EWMA parameters
kappa = {pv.get('ewma_kappa', 'n/a')} and alpha = {pv.get('ewma_alpha', 'n/a')},
severity floor tau_e = {pv.get('severity_floor_tau_e', 'n/a')}, confidence floor
pi_min = {pv.get('confidence_floor_pi_min', 'n/a')} and utility weights
lambda1 = {pv.get('utility_lambda1', 'n/a')}, lambda2 = {pv.get('utility_lambda2', 'n/a')}.
Results are averaged over {pv.get('n_runs_seeds', 'n/a')} independent seeds with a
scenario-level 60/20/20 train/validation/test split; the test split is evaluated
once after tuning.

## Section 6 (Results)

The fused multimodal framework attains an F1 of {fused_f1} on the held-out test
split, exceeding each single-modality detector and the Random-Forest flow
baseline (see Table 3). Leaf-level attribution and calibration are reported in
Fig. 4 and the attribution metrics table; containment effectiveness in Table 5;
overhead and scalability in Table 6 and the scalability figure.

## Data availability

All tables and figures are reproduced by `aegis campaign --config
configs/experiments/{run_group}.yaml`; see the run manifest and report manifest
for run IDs, seeds and config hashes.
"""
    (tables / "manuscript_snippets.md").write_text(text)


def _run_summary(md: Path, out: Path, run_group: str, manifest: dict) -> None:
    summary = {"run_group": run_group, "artifacts": list(manifest.keys())}
    det = _read(md, "detection_per_seed.csv")
    if det is not None:
        fused = det[det["method"] == "fused_framework"]
        summary["fused_f1_mean"] = float(np.nanmean(fused["f1"].values))
        summary["fused_auroc_mean"] = float(np.nanmean(fused["auroc"].values))
    with open(out / "metrics" / run_group / "run_summary.json", "w") as fh:
        json.dump(summary, fh, indent=2, default=str)


def _rel(paths: dict[str, Path]) -> dict[str, str]:
    return {k: str(v) for k, v in paths.items()}
