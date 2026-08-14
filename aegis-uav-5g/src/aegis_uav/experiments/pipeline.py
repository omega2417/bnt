"""Core per-seed pipeline: build data, train agents, run the agentic loop, and
compute detection/attribution/response/overhead metrics.

This module never fabricates a number: every reported value is computed from the
model outputs on the held-out test split.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any

import numpy as np
import pandas as pd
import psutil

from .. import ATTACK_CLASSES, BENIGN_LABEL, MACRO_CLASSES
from ..agents.aaa import AttackAttributionAgent
from ..agents.ada import AnomalyDetectionAgent
from ..agents.pea import PolicyEnforcementAgent
from ..agents.rsa import ResponseSelectionAgent
from ..agents.tca import ThreatCorrelationAgent
from ..baselines.detectors import RandomForestFlowDetector
from ..blackboard.blackboard import Blackboard
from ..evaluation.metrics import binary_detection_metrics, tune_threshold
from ..evaluation.statistics import brier_score, expected_calibration_error
from ..features.pipeline import CROSS_VEHICLE_FEATURES, FeaturePipeline
from ..schemas import ExperimentConfig, ScenarioConfig
from .dataset import build_seed_dataset
from .overrides import Overrides

__all__ = [
    "run_core", "CoreResult", "TrainedContext", "train_context",
    "evaluate_detection", "evaluate_attribution", "run_agentic_ctx",
]

MODALITY_KEY = {"telemetry": "tel", "network": "net", "behaviour": "beh"}
INSIDER_CLASSES = {"T4", "T5", "T6"}


@dataclass
class CoreResult:
    seed: int
    feature_dim: int
    class_counts: dict[str, dict[str, int]]
    detection: dict[str, dict[str, float]] = field(default_factory=dict)
    detection_per_class_recall: dict[str, dict[str, float]] = field(default_factory=dict)
    detection_latency: dict[str, list[float]] = field(default_factory=dict)
    attribution: dict[str, Any] = field(default_factory=dict)
    confusion: np.ndarray | None = None
    response: dict[str, dict[str, Any]] = field(default_factory=dict)
    overhead: dict[str, float] = field(default_factory=dict)
    incidents: list = field(default_factory=list)
    thresholds: dict[str, float] = field(default_factory=dict)


def _cfg_with_overrides(exp: ExperimentConfig, ov: Overrides):
    ada = exp.ada.model_copy(deep=True)
    tca = exp.tca.model_copy(deep=True)
    aaa = exp.aaa.model_copy(deep=True)
    rsa = exp.rsa.model_copy(deep=True)
    if ov.kappa is not None:
        ada.kappa = ov.kappa
    if ov.alpha is not None:
        ada.alpha = ov.alpha
    if ov.window_length_s is not None:
        ada.window_length_s = ov.window_length_s
    if ov.severity_floor is not None:
        tca.severity_floor = ov.severity_floor
    if ov.lambda1 is not None:
        rsa.lambda1 = ov.lambda1
    if ov.lambda2 is not None:
        rsa.lambda2 = ov.lambda2
    if ov.pi_min is not None:
        rsa.pi_min = ov.pi_min
    if ov.no_calibration:
        aaa.calibration = "none"
    if ov.no_hierarchy:
        aaa.hierarchical = False
    return ada, tca, aaa, rsa


def _zero_cross_vehicle(*dfs: pd.DataFrame) -> None:
    for df in dfs:
        for c in CROSS_VEHICLE_FEATURES:
            df[c] = 0.0


def _fused(scores: dict[str, np.ndarray], weights: dict[str, float]) -> np.ndarray:
    return sum(weights[m] * scores[m] for m in weights)


def run_core(
    scenario: ScenarioConfig,
    exp: ExperimentConfig,
    seed: int,
    ov: Overrides | None = None,
    do_response: bool = True,
) -> CoreResult:
    ov = ov or Overrides()
    ctx = train_context(scenario, exp, seed, ov)
    res = CoreResult(seed=seed, feature_dim=ctx.pipe.dim, class_counts=ctx.ds.class_counts)

    evaluate_detection(res, ctx, ctx.tca_cfg.modality_weights)
    evaluate_attribution(res, ctx, ov)
    if do_response:
        run_agentic_ctx(res, ctx, ctx.tca_cfg, ctx.rsa_cfg, ov)
    res.overhead = _measure_overhead(ctx.ada, ctx.test, ctx.pipe, scenario, ctx.ada_cfg)
    return res


@dataclass
class TrainedContext:
    """Everything trained once for a (seed, override) so downstream stages can be
    re-evaluated cheaply (used by the sensitivity sweep)."""

    seed: int
    scenario: ScenarioConfig
    exp: ExperimentConfig
    ov: Overrides
    ds: Any
    pipe: FeaturePipeline
    ada: AnomalyDetectionAgent
    aaa: AttackAttributionAgent
    rf: RandomForestFlowDetector
    ada_cfg: Any
    tca_cfg: Any
    aaa_cfg: Any
    rsa_cfg: Any
    val_scores: dict[str, np.ndarray]
    test_scores: dict[str, np.ndarray]
    rf_val: np.ndarray
    rf_test: np.ndarray
    y_val: np.ndarray
    y_test: np.ndarray

    @property
    def train(self):
        return self.ds.train

    @property
    def val(self):
        return self.ds.val

    @property
    def test(self):
        return self.ds.test


def train_context(scenario, exp, seed, ov: Overrides) -> TrainedContext:
    ada_cfg, tca_cfg, aaa_cfg, rsa_cfg = _cfg_with_overrides(exp, ov)
    ds = build_seed_dataset(scenario, ada_cfg, exp.dataset, seed)
    if ov.no_cross_vehicle:
        _zero_cross_vehicle(ds.train, ds.val, ds.test)

    pipe = FeaturePipeline().fit(ds.train, benign_only=True)
    ada = AnomalyDetectionAgent(ada_cfg, seed=seed).fit(ds.train, pipe)
    val_scores = {m: ada.normalised_score(m, ada.raw_scores(ds.val)[m]) for m in MODALITY_KEY}
    test_scores = {m: ada.normalised_score(m, ada.raw_scores(ds.test)[m]) for m in MODALITY_KEY}
    aaa = AttackAttributionAgent(aaa_cfg, seed=seed).fit(ds.train, pipe)
    rf = RandomForestFlowDetector(seed=seed).fit(ds.train)
    return TrainedContext(
        seed=seed, scenario=scenario, exp=exp, ov=ov, ds=ds, pipe=pipe, ada=ada, aaa=aaa,
        rf=rf, ada_cfg=ada_cfg, tca_cfg=tca_cfg, aaa_cfg=aaa_cfg, rsa_cfg=rsa_cfg,
        val_scores=val_scores, test_scores=test_scores,
        rf_val=rf.predict_proba(ds.val), rf_test=rf.predict_proba(ds.test),
        y_val=(ds.val["attack_label"] != BENIGN_LABEL).astype(int).to_numpy(),
        y_test=(ds.test["attack_label"] != BENIGN_LABEL).astype(int).to_numpy(),
    )


def evaluate_detection(res: CoreResult, ctx: TrainedContext, weights: dict[str, float]) -> None:
    val_fused = _fused(ctx.val_scores, weights)
    test_fused = _fused(ctx.test_scores, weights)
    methods = {
        "fused_framework": (val_fused, test_fused),
        "telemetry_only": (ctx.val_scores["telemetry"], ctx.test_scores["telemetry"]),
        "traffic_only": (ctx.val_scores["network"], ctx.test_scores["network"]),
        "behaviour_only": (ctx.val_scores["behaviour"], ctx.test_scores["behaviour"]),
        "rf_flow_baseline": (ctx.rf_val, ctx.rf_test),
    }
    for name, (vs, ts) in methods.items():
        thr = tune_threshold(vs, ctx.y_val)
        res.thresholds[name] = thr
        res.detection[name] = binary_detection_metrics(ts, ctx.y_test, thr)
        res.detection_per_class_recall[name] = _per_class_recall(ts, thr, ctx.test)


def evaluate_attribution(res: CoreResult, ctx: TrainedContext, ov: Overrides) -> None:
    X_test = ctx.pipe.transform(ctx.test)
    y_leaf = ctx.test["attack_label"].to_numpy()
    y_macro = np.array([{**{BENIGN_LABEL: "benign"}, **MACRO_CLASSES}.get(v) for v in y_leaf])
    res.attribution["hierarchical"] = _attribution_block(ctx.aaa, X_test, y_leaf, y_macro, True)
    res.attribution["flat"] = _attribution_block(ctx.aaa, X_test, y_leaf, y_macro, False)
    res.attribution["primary"] = _attribution_block(
        ctx.aaa, X_test, y_leaf, y_macro, not ov.no_hierarchy
    )
    res.confusion = res.attribution["primary"].pop("_confusion")
    res.attribution["hierarchical"].pop("_confusion", None)
    res.attribution["flat"].pop("_confusion", None)


def _per_class_recall(scores: np.ndarray, thr: float, test: pd.DataFrame) -> dict[str, float]:
    pred = scores >= thr
    out: dict[str, float] = {}
    labels = test["attack_label"].to_numpy()
    for cls in ATTACK_CLASSES:
        mask = labels == cls
        out[cls] = float(pred[mask].mean()) if mask.sum() else float("nan")
    return out


def _attribution_block(aaa, X, y_leaf, y_macro, hierarchical: bool) -> dict[str, Any]:
    from ..evaluation.metrics import attribution_metrics, confusion

    leaf_pred, macro_pred, post = aaa.predict_batch(X, hierarchical=hierarchical)
    metrics = attribution_metrics(y_leaf, leaf_pred, y_macro, macro_pred)
    labels = list((BENIGN_LABEL, *ATTACK_CLASSES))
    conf = post.max(axis=1)
    correct = (leaf_pred == y_leaf).astype(float)
    onehot = np.zeros_like(post)
    for i, lab in enumerate(y_leaf):
        onehot[i, labels.index(lab)] = 1.0
    metrics["ece"] = expected_calibration_error(conf, correct)
    metrics["brier"] = brier_score(post, onehot)
    metrics["_confusion"] = confusion(y_leaf, leaf_pred)
    return metrics


def run_agentic_ctx(res, ctx, tca_cfg, rsa_cfg, ov) -> None:
    test, pipe, ada, aaa, exp = (ctx.test, ctx.pipe, ctx.ada, ctx.aaa, ctx.exp)
    det = ada.detect(test)
    tca = ThreatCorrelationAgent(tca_cfg, seed=res.seed)
    incidents = tca.correlate(det, use_fusion=not ov.no_fusion)
    rsa = ResponseSelectionAgent(rsa_cfg, seed=res.seed)
    pea = PolicyEnforcementAgent(exp.pea, seed=res.seed)
    board = Blackboard()

    impact_by_run = _impact_times(test)
    variants = {"utility_rsa": False, "static_policy": True}
    metric_rows: dict[str, list[dict]] = {v: [] for v in variants}
    latencies: dict[str, list[float]] = {}

    for inc in incidents:
        rows = test.loc[inc.row_indices]
        # Representative = the highest-severity windows of the incident, so that
        # attribution is driven by the attack peak, not by merged-in benign FPs.
        sev = det.loc[rows.index, ["tel_score", "net_score", "beh_score"]].max(axis=1)
        top_idx = sev.sort_values(ascending=False).index[: min(3, len(rows))]
        fv = pipe.transform(test.loc[top_idx]).mean(axis=0)
        attr = aaa.attribute(fv, hierarchical=not ov.no_hierarchy)
        if ov.no_counterfactual_origin:
            origin = _severity_origin(rows, det)
            origin_conf = float("nan")
        else:
            origin, origin_conf = aaa.attribute_origin(rows, det)

        # Per-incident ground truth: derived from the incident's own windows so
        # that benign false-positive incidents are labelled benign (not missed
        # attacks) and true incidents carry the attacked class/origin/onset.
        g = _incident_ground_truth(rows, impact_by_run)
        det_latency = max(inc.window_start_min - g["onset"], 0.0) if not np.isnan(
            g["onset"]) else float("nan")
        if g["true_label"] != BENIGN_LABEL and not np.isnan(det_latency):
            latencies.setdefault(g["true_label"], []).append(det_latency)

        record = board.new_incident()
        record.window_ids = [int(i) for i in rows["window_id"].tolist()]
        record.affected_entities = inc.affected_entities
        record.modality_scores = inc.modality_scores
        record.fused_score = inc.fused_score
        record.predicted_attack = attr["predicted_attack"]
        record.macro_class = attr["macro_class"]
        record.attack_posterior = {k: round(v, 4) for k, v in attr["attack_posterior"].items()}
        record.suspected_origin = origin
        record.origin_confidence = origin_conf
        record.top_features = {
            m: ada.top_features(rows, m) for m in ("telemetry", "network", "behaviour")
        }
        record.ground_truth = g

        for variant, is_static in variants.items():
            sel = (rsa.static_select(attr["predicted_attack"]) if is_static
                   else rsa.select(attr["predicted_attack"], attr["confidence"],
                                   use_mask=not ov.no_safe_mask))
            enf = pea.enforce(sel["selected"], record.incident_id)
            contain_latency = (det_latency + enf["latency_ms"] / 1000.0
                               if not np.isnan(det_latency) else float("nan"))
            metric_rows[variant].append(
                _response_row(g, attr, sel, enf, det_latency, contain_latency, origin)
            )
            if not is_static:  # persist the utility-RSA decision on the blackboard
                record.selected_response = sel["selected"]
                record.runner_up_response = sel["runner_up"]
                record.utility_terms = sel["utility_terms"]
                record.safety_mask = sel["safe_actions"]
                record.enforcement_result = enf
        record.explanation = {
            "modality_scores": inc.modality_scores,
            "fused_severity": inc.fused_score,
            "top_features": record.top_features,
            "attack_posterior": record.attack_posterior,
            "selected_response": record.selected_response,
            "runner_up_response": record.runner_up_response,
            "utility_terms": record.utility_terms,
            "safety_constraints": record.safety_mask,
            "enforcement_result": record.enforcement_result,
        }
        record.timestamps = {
            "incident_start": inc.window_start_min,
            "incident_end": inc.window_start_max,
            "detection_latency_s": det_latency,
        }

    res.incidents = board.incidents
    res.detection_latency = latencies
    for variant in variants:
        res.response[variant] = _aggregate_response(metric_rows[variant])


def _response_row(g, attr, sel, enf, det_latency, contain_latency, origin) -> dict:
    true_label = g["true_label"]
    is_attack = true_label != BENIGN_LABEL
    action = sel["selected"]
    enforced = action != "escalate" and enf["post_condition_ok"]
    correct_attr = attr["predicted_attack"] == true_label
    contained_before_impact = (
        is_attack and enforced and not np.isnan(contain_latency)
        and not np.isnan(g["impact_time"]) and not np.isnan(g["onset"])
        and (g["onset"] + contain_latency) <= g["impact_time"]
    )
    return {
        "is_attack": is_attack,
        "true_label": true_label,
        "action": action,
        "enforced": enforced,
        "escalated": action == "escalate",
        "rolled_back": bool(enf["rolled_back"]),
        "correct_attr": correct_attr,
        "origin_correct": (origin == g["origin"]) if is_attack and g["origin"] else False,
        "insider": true_label in INSIDER_CLASSES,
        "harmful": bool(is_attack and enforced and not correct_attr),
        "unnecessary": bool((not is_attack) and enforced),
        "contained_before_impact": bool(contained_before_impact),
        "containment_latency": contain_latency if (is_attack and enforced) else float("nan"),
    }


def _aggregate_response(rows: list[dict]) -> dict[str, Any]:
    if not rows:
        return {}
    df = pd.DataFrame(rows)
    attacks = df[df["is_attack"]]
    insiders = attacks[attacks["insider"]]
    lat = df["containment_latency"].dropna().tolist()
    return {
        "n_incidents": int(len(df)),
        "n_attack_incidents": int(len(attacks)),
        "containment_latency": lat,
        "contained_before_impact_rate": float(attacks["contained_before_impact"].mean())
        if len(attacks) else float("nan"),
        "harmful_response_rate": float(df["harmful"].mean()),
        "unnecessary_response_rate": float(df["unnecessary"].mean()),
        "escalation_rate": float(df["escalated"].mean()),
        "rollback_rate": float(df["rolled_back"].mean()),
        "origin_accuracy": float(insiders["origin_correct"].mean())
        if len(insiders) else float("nan"),
        "attribution_accuracy_incident": float(attacks["correct_attr"].mean())
        if len(attacks) else float("nan"),
    }


def _impact_times(test: pd.DataFrame) -> dict[str, float]:
    """Earliest mission-impact window time per run (for contained-before-impact)."""
    out: dict[str, float] = {}
    imp = test[test["mission_impact_window"]]
    for run_id, rows in imp.groupby("run_id"):
        out[str(run_id)] = float(rows["window_start"].min())
    return out


def _incident_ground_truth(rows: pd.DataFrame, impact_by_run: dict[str, float]) -> dict:
    """Ground-truth label for an incident, from its own windows."""
    attack_rows = rows[rows["is_attack"]]
    if len(attack_rows) < 0.5 * len(rows) or len(attack_rows) == 0:
        return {"true_label": BENIGN_LABEL, "onset": float("nan"),
                "impact_time": float("nan"), "origin": ""}
    labels = attack_rows["attack_label"]
    true_label = labels.mode().iloc[0]
    origin_vals = attack_rows["attack_origin"][attack_rows["attack_origin"] != ""]
    origin = origin_vals.mode().iloc[0] if len(origin_vals) else ""
    run_id = str(rows["run_id"].iloc[0])
    return {
        "true_label": true_label,
        "onset": float(attack_rows["attack_onset"].min()),
        "impact_time": impact_by_run.get(run_id, float("nan")),
        "origin": origin,
    }


def _severity_origin(rows: pd.DataFrame, det: pd.DataFrame) -> str:
    sub = det.loc[rows.index]
    per_uav = sub.assign(sev=sub[["tel_score", "net_score", "beh_score"]].mean(axis=1))
    grp = per_uav.groupby("uav_index")["sev"].mean()
    u = int(grp.idxmax())
    return f"uav_{u:02d}"


def _measure_overhead(ada, test, pipe, scenario, ada_cfg) -> dict[str, float]:
    proc = psutil.Process()
    proc.cpu_percent(interval=None)
    t0 = time.perf_counter()
    _ = {m: ada.raw_scores(test)[m] for m in MODALITY_KEY}
    elapsed = time.perf_counter() - t0
    cpu = proc.cpu_percent(interval=None)
    ram_mb = proc.memory_info().rss / (1024 * 1024)
    n_windows = max(len(test), 1)
    per_window_ms = elapsed / n_windows * 1000.0
    throughput = n_windows / elapsed if elapsed > 0 else float("nan")
    # Probe bandwidth per UAV: d features * 4 bytes, once per stride seconds.
    bytes_per_report = pipe.dim * 4
    reports_per_s = 1.0 / max(ada_cfg.window_stride_s, 1e-6)
    probe_kbps = bytes_per_report * 8 * reports_per_s / 1000.0
    return {
        "processing_latency_ms": per_window_ms,
        "cpu_percent": float(cpu),
        "ram_mb": float(ram_mb),
        "probe_bandwidth_kbps": float(probe_kbps),
        "throughput_windows_per_s": float(throughput),
        "fleet_size": float(scenario.fleet_size),
    }
