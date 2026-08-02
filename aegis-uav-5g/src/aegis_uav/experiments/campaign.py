"""Campaign orchestrator: runs every experiment (E1-E7) across seeds and writes
machine-readable metrics that the reporting layer turns into tables and figures.

No metric is ever hand-entered: this module is the single source of the numbers.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

import numpy as np
import pandas as pd

from .. import ALL_LABELS
from ..config import RunManifest, config_hash, load_experiment, load_scenario, project_root
from ..evaluation.metrics import binary_detection_metrics
from ..logging_utils import configure_logging, get_logger
from ..schemas import ExperimentConfig, ScenarioConfig
from .overrides import Overrides
from .pipeline import (
    CoreResult,
    TrainedContext,
    evaluate_detection,
    run_agentic_ctx,
    run_core,
    train_context,
)

log = get_logger("campaign")

# Ablations that do not change training and can reuse the base context.
_REUSE_ABLATIONS = {"no_fusion", "no_safe_mask", "no_hierarchy", "no_counterfactual_origin"}


def run_campaign(config_path: str, output_root: Path | None = None) -> Path:
    scenario = load_scenario(_scenario_path(config_path))
    exp = load_experiment(config_path)
    root = project_root()
    out = (output_root or (root / "artifacts"))
    metrics_dir = out / "metrics" / exp.run_group
    metrics_dir.mkdir(parents=True, exist_ok=True)
    configure_logging(out / "logs" / f"{exp.run_group}.log")

    ts = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    cfg_hash = config_hash(scenario, exp)
    manifest = RunManifest.create(exp.run_group, exp.dataset.seeds[0], cfg_hash,
                                  out / "manifests", ts)
    manifest.extra = {"experiments": exp.experiments, "n_seeds": len(exp.dataset.seeds)}
    manifest.save()
    log.info("campaign %s start (seeds=%s, hash=%s)", exp.run_group, exp.dataset.seeds, cfg_hash)

    seeds = exp.dataset.seeds
    contexts: dict[int, TrainedContext] = {}
    main_results: list[CoreResult] = []

    # ---- E1-E3 main comparison + overhead, per seed ------------------------ #
    for seed in seeds:
        log.info("main pipeline seed=%s", seed)
        ctx = train_context(scenario, exp, seed, Overrides())
        contexts[seed] = ctx
        res = CoreResult(seed=seed, feature_dim=ctx.pipe.dim, class_counts=ctx.ds.class_counts)
        evaluate_detection(res, ctx, ctx.tca_cfg.modality_weights)
        from .pipeline import _measure_overhead, evaluate_attribution
        evaluate_attribution(res, ctx, Overrides())
        run_agentic_ctx(res, ctx, ctx.tca_cfg, ctx.rsa_cfg, Overrides())
        res.overhead = _measure_overhead(ctx.ada, ctx.test, ctx.pipe, scenario, ctx.ada_cfg)
        main_results.append(res)

    _write_detection(metrics_dir, main_results)
    _write_attribution(metrics_dir, main_results)
    _write_response(metrics_dir, main_results)
    _write_latency(metrics_dir, main_results)
    _write_overhead(metrics_dir, main_results)
    _write_confusion(metrics_dir, main_results)
    _write_parameters(metrics_dir, scenario, exp, main_results, cfg_hash)
    _save_incident_samples(out, exp.run_group, main_results)

    if "ablation" in exp.experiments:
        _run_ablation(metrics_dir, scenario, exp, seeds, contexts, main_results)
    if "sensitivity" in exp.experiments:
        _run_sensitivity(metrics_dir, scenario, exp, contexts[seeds[0]], seeds[0])
    if "scalability" in exp.experiments:
        _run_scalability(metrics_dir, scenario, exp, seeds[0])

    # ---- Build report artifacts + manuscript data map --------------------- #
    from ..reporting.manuscript import build_manuscript_map
    from ..reporting.report import build_report
    report_dir = build_report(exp.run_group, out)
    build_manuscript_map(exp.run_group, out)
    log.info("campaign %s done -> %s", exp.run_group, report_dir)
    return report_dir


def _scenario_path(config_path: str) -> str:
    exp = load_experiment(config_path)
    return exp.scenario


# --------------------------------------------------------------------------- #
# Metric writers
# --------------------------------------------------------------------------- #


def _write_detection(md: Path, results: list[CoreResult]) -> None:
    rows, recall_rows = [], []
    for r in results:
        for method, m in r.detection.items():
            rows.append({"seed": r.seed, "method": method, **{
                k: m[k] for k in ("precision", "recall", "f1", "fpr", "auroc", "auprc")}})
            pc = r.detection_per_class_recall[method]
            recall_rows.append({"seed": r.seed, "method": method, **pc})
    pd.DataFrame(rows).to_csv(md / "detection_per_seed.csv", index=False)
    pd.DataFrame(recall_rows).to_csv(md / "detection_per_class_recall.csv", index=False)


def _write_attribution(md: Path, results: list[CoreResult]) -> None:
    rows = []
    for r in results:
        for variant in ("hierarchical", "flat"):
            b = r.attribution[variant]
            rows.append({"seed": r.seed, "variant": variant, **{
                k: b.get(k) for k in
                ("leaf_accuracy", "macro_accuracy", "macro_f1", "ece", "brier")}})
    pd.DataFrame(rows).to_csv(md / "attribution_per_seed.csv", index=False)


def _write_response(md: Path, results: list[CoreResult]) -> None:
    rows, lat_rows = [], []
    for r in results:
        for policy in ("utility_rsa", "static_policy"):
            m = r.response.get(policy, {})
            if not m:
                continue
            rows.append({"seed": r.seed, "policy": policy, **{
                k: m.get(k) for k in (
                    "n_incidents", "n_attack_incidents", "contained_before_impact_rate",
                    "harmful_response_rate", "unnecessary_response_rate", "escalation_rate",
                    "rollback_rate", "origin_accuracy", "attribution_accuracy_incident")}})
            for lat in m.get("containment_latency", []):
                lat_rows.append({"seed": r.seed, "policy": policy, "latency_s": lat})
    pd.DataFrame(rows).to_csv(md / "response_per_seed.csv", index=False)
    pd.DataFrame(lat_rows).to_csv(md / "containment_latency.csv", index=False)


def _write_latency(md: Path, results: list[CoreResult]) -> None:
    rows = []
    for r in results:
        for cls, lats in r.detection_latency.items():
            for lat in lats:
                rows.append({"seed": r.seed, "attack_class": cls, "latency_s": lat})
    pd.DataFrame(rows).to_csv(md / "detection_latency.csv", index=False)


def _write_overhead(md: Path, results: list[CoreResult]) -> None:
    rows = [{"seed": r.seed, **r.overhead} for r in results]
    pd.DataFrame(rows).to_csv(md / "overhead_per_seed.csv", index=False)


def _write_confusion(md: Path, results: list[CoreResult]) -> None:
    total = np.zeros((len(ALL_LABELS), len(ALL_LABELS)), dtype=int)
    for r in results:
        if r.confusion is not None:
            total += r.confusion
    df = pd.DataFrame(total, index=list(ALL_LABELS), columns=list(ALL_LABELS))
    df.to_csv(md / "confusion_matrix.csv")


def _write_parameters(md: Path, scenario: ScenarioConfig, exp: ExperimentConfig,
                      results: list[CoreResult], cfg_hash: str) -> None:
    d = results[0].feature_dim
    counts = _aggregate_counts(results)
    params = {
        "feature_dimension_d": d,
        "fleet_size_N": scenario.fleet_size,
        "mission_duration_s": scenario.mission_duration_s,
        "window_length_delta_s": exp.ada.window_length_s,
        "window_stride_s": exp.ada.window_stride_s,
        "ewma_kappa": exp.ada.kappa,
        "ewma_alpha": exp.ada.alpha,
        "severity_floor_tau_e": exp.tca.severity_floor,
        "modality_weights_w_m": json.dumps(exp.tca.modality_weights),
        "confidence_floor_pi_min": exp.rsa.pi_min,
        "utility_lambda1": exp.rsa.lambda1,
        "utility_lambda2": exp.rsa.lambda2,
        "ada_latent_dim": exp.ada.latent_dim,
        "ada_hidden_sizes": json.dumps(exp.ada.hidden_sizes),
        "aaa_classifier": exp.aaa.classifier,
        "aaa_calibration": exp.aaa.calibration,
        "n_runs_seeds": len(exp.dataset.seeds),
        "seeds": json.dumps(exp.dataset.seeds),
        "missions_per_class": exp.dataset.missions_per_class,
        "train_val_test_split": "60/20/20",
        "config_hash": cfg_hash,
    }
    for split in ("train", "val", "test"):
        for label in ALL_LABELS:
            params[f"n_windows_{split}_{label}"] = counts[split].get(label, 0)
    df = pd.DataFrame([{"parameter": k, "value": v} for k, v in params.items()])
    df.to_csv(md / "parameters.csv", index=False)


def _aggregate_counts(results: list[CoreResult]) -> dict[str, dict[str, int]]:
    agg: dict[str, dict[str, int]] = {"train": {}, "val": {}, "test": {}}
    for r in results:
        for split, cc in r.class_counts.items():
            for label, n in cc.items():
                agg[split][label] = agg[split].get(label, 0) + int(n)
    return agg


# --------------------------------------------------------------------------- #
# E4 ablation, E5 sensitivity, E6 scalability
# --------------------------------------------------------------------------- #


def _ablation_metrics(res: CoreResult, ablation: str = "full") -> dict[str, float]:
    resp = res.response.get("utility_rsa", {})
    # Removing evidence fusion degrades the detector to the single best modality.
    if ablation == "no_fusion":
        singles = ("telemetry_only", "traffic_only", "behaviour_only")
        best = max(singles, key=lambda m: res.detection[m]["f1"])
        det_f1, det_fpr = res.detection[best]["f1"], res.detection[best]["fpr"]
    else:
        det_f1, det_fpr = (res.detection["fused_framework"]["f1"],
                           res.detection["fused_framework"]["fpr"])
    return {
        "det_f1": det_f1,
        "det_fpr": det_fpr,
        "attr_macro_f1": res.attribution["primary"]["macro_f1"],
        "attr_leaf_accuracy": res.attribution["primary"]["leaf_accuracy"],
        "contained_before_impact": resp.get("contained_before_impact_rate", float("nan")),
        "origin_accuracy": resp.get("origin_accuracy", float("nan")),
    }


def _run_ablation(md, scenario, exp, seeds, contexts, main_results) -> None:
    rows = []
    for res in main_results:
        rows.append({"seed": res.seed, "ablation": "full", **_ablation_metrics(res)})
    for name in exp.ablations:
        ov = Overrides.for_ablation(name)
        for seed in seeds:
            log.info("ablation %s seed=%s", name, seed)
            if name in _REUSE_ABLATIONS and seed in contexts:
                res = _reuse_result(contexts[seed], ov, scenario)
            else:
                res = run_core(scenario, exp, seed, ov)
            rows.append({"seed": seed, "ablation": name, **_ablation_metrics(res, name)})
    pd.DataFrame(rows).to_csv(md / "ablation_per_seed.csv", index=False)


def _reuse_result(ctx: TrainedContext, ov: Overrides, scenario) -> CoreResult:
    from .pipeline import _measure_overhead, evaluate_attribution
    res = CoreResult(seed=ctx.seed, feature_dim=ctx.pipe.dim, class_counts=ctx.ds.class_counts)
    evaluate_detection(res, ctx, ctx.tca_cfg.modality_weights)
    evaluate_attribution(res, ctx, ov)
    run_agentic_ctx(res, ctx, ctx.tca_cfg, ctx.rsa_cfg, ov)
    res.overhead = _measure_overhead(ctx.ada, ctx.test, ctx.pipe, scenario, ctx.ada_cfg)
    return res


def _flag_detection(ctx: TrainedContext) -> dict[str, float]:
    det = ctx.ada.detect(ctx.test)
    return binary_detection_metrics(det["any_flag"].astype(int).to_numpy(),
                                    ctx.y_test, 0.5)


def _run_sensitivity(md, scenario, exp, ctx: TrainedContext, seed: int) -> None:
    rows = []
    base_kappa, base_alpha = ctx.ada.config.kappa, ctx.ada.config.alpha

    def record(param, value, res=None, flag=None, det_weights=None):
        row = {"parameter": param, "value": value, "seed": seed}
        if det_weights is not None:
            r2 = CoreResult(seed=seed, feature_dim=ctx.pipe.dim, class_counts=ctx.ds.class_counts)
            evaluate_detection(r2, ctx, det_weights)
            row["det_f1"] = r2.detection["fused_framework"]["f1"]
            row["det_fpr"] = r2.detection["fused_framework"]["fpr"]
        if flag is not None:
            row["flag_f1"] = flag["f1"]
            row["flag_fpr"] = flag["fpr"]
        if res is not None:
            resp = res.response.get("utility_rsa", {})
            row["contained_before_impact"] = resp.get("contained_before_impact_rate", float("nan"))
            row["unnecessary_response_rate"] = resp.get("unnecessary_response_rate", float("nan"))
            row["escalation_rate"] = resp.get("escalation_rate", float("nan"))
        rows.append(row)

    sens = exp.sensitivity
    # kappa, alpha: affect EWMA flags -> flag F1/FPR + containment (reuse ctx).
    for val in sens.get("kappa", []):
        ctx.ada.config.kappa = val
        res = _reuse_result(ctx, Overrides(), scenario)
        record("kappa", val, res=res, flag=_flag_detection(ctx))
    ctx.ada.config.kappa = base_kappa
    for val in sens.get("alpha", []):
        ctx.ada.config.alpha = val
        res = _reuse_result(ctx, Overrides(), scenario)
        record("alpha", val, res=res, flag=_flag_detection(ctx))
    ctx.ada.config.alpha = base_alpha
    # severity_floor: affects incident formation (reuse ctx via tca override).
    for val in sens.get("severity_floor", []):
        ov = Overrides(severity_floor=val)
        tca = ctx.tca_cfg.model_copy(update={"severity_floor": val})
        res = CoreResult(seed=seed, feature_dim=ctx.pipe.dim, class_counts=ctx.ds.class_counts)
        run_agentic_ctx(res, ctx, tca, ctx.rsa_cfg, ov)
        record("severity_floor", val, res=res)
    # lambda1, lambda2, pi_min: affect RSA only (reuse ctx).
    for pname, field in (("lambda1", "lambda1"), ("lambda2", "lambda2"), ("pi_min", "pi_min")):
        for val in sens.get(pname, []):
            rsa = ctx.rsa_cfg.model_copy(update={field: val})
            res = CoreResult(seed=seed, feature_dim=ctx.pipe.dim, class_counts=ctx.ds.class_counts)
            run_agentic_ctx(res, ctx, ctx.tca_cfg, rsa, Overrides())
            record(pname, val, res=res)
    # modality weights (w_m): vary telemetry weight, evaluate fused detection.
    for w in sens.get("w_telemetry", []):
        rest = (1.0 - w) / 2.0
        weights = {"telemetry": w, "network": rest, "behaviour": rest}
        record("w_telemetry", w, det_weights=weights)
    # window length (Delta): changes windowing -> needs a full rebuild.
    for val in sens.get("window_length_s", []):
        res = run_core(scenario, exp, seed, Overrides(window_length_s=val))
        resp = res.response.get("utility_rsa", {})
        rows.append({
            "parameter": "window_length_s", "value": val, "seed": seed,
            "det_f1": res.detection["fused_framework"]["f1"],
            "det_fpr": res.detection["fused_framework"]["fpr"],
            "contained_before_impact": resp.get("contained_before_impact_rate", float("nan")),
        })

    pd.DataFrame(rows).to_csv(md / "sensitivity.csv", index=False)


def _run_scalability(md, scenario, exp, seed: int) -> None:
    rows = []
    for n in exp.fleet_sizes:
        sc = scenario.model_copy(update={"fleet_size": int(n)})
        log.info("scalability N=%s", n)
        res = run_core(sc, exp, seed, Overrides(), do_response=True)
        ov = res.overhead
        # End-to-end detection latency: median of per-class detection latencies.
        all_lat = [x for v in res.detection_latency.values() for x in v]
        e2e = float(np.median(all_lat)) if all_lat else float("nan")
        rows.append({
            "fleet_size": int(n), "seed": seed,
            "processing_latency_ms": ov["processing_latency_ms"],
            "cpu_percent": ov["cpu_percent"], "ram_mb": ov["ram_mb"],
            "probe_bandwidth_kbps": ov["probe_bandwidth_kbps"],
            "throughput_windows_per_s": ov["throughput_windows_per_s"],
            "end_to_end_detection_latency_s": e2e,
        })
    pd.DataFrame(rows).to_csv(md / "scalability.csv", index=False)


def _save_incident_samples(out: Path, run_group: str, results: list[CoreResult]) -> None:
    """Persist a sample of explanation objects (one JSON per incident)."""
    inc_dir = out / "logs" / run_group / "incidents"
    inc_dir.mkdir(parents=True, exist_ok=True)
    saved = 0
    for r in results:
        for inc in r.incidents[:20]:
            with open(inc_dir / f"seed{r.seed}_{inc.incident_id}.json", "w") as fh:
                fh.write(inc.to_json())
            saved += 1
        if saved >= 40:
            break
