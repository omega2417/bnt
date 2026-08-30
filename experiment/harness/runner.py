"""Software-in-the-loop run executor.

One call to `execute_run` produces one row of runs.csv plus a raw evidence bundle.
The (scenario, repetition) pair fixes the random seed, so all six arms observe the
*identical* environment realisation: the design is fully blocked and every
comparison is paired.

Metric provenance classes (recorded per metric in processed/data_dictionary.md):

  endogenous_algorithmic  - produced by executing the dtcr implementation on the
      generated stream. Depends only on detector/decision quality; this is the
      only class used as evidence about the method.
  parameterized_model     - produced by a declared actuation/availability model
      (operator delay, actuation latency, degradation depth, recovery ramp).
      These are ASSUMPTIONS, not measurements, and carry the sensitivity analysis.
  measured_implementation - real CPU cost of executing the framework code here.
"""
from __future__ import annotations

import hashlib
import time
from dataclasses import dataclass
from pathlib import Path

import numpy as np

import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from dtcr import anomaly, audit, graph_risk, orchestrator as orch, resilience, trust
from harness import environment as env
from harness.arms import ARMS, ArmSpec
from harness.scenarios import ACTION_MODELS, SCENARIOS, apply_injection

# ---------------------------------------------------------------------------
# Declared parameters, frozen in protocol/preregistration.yaml.
# Values marked [P] belong to the parameterized_model class.
# ---------------------------------------------------------------------------
DT = 0.5
T_BASELINE = 240.0        # window used to estimate mu, Sigma and the IDS threshold
T_HOLDOUT = 60.0          # clean window held out for out-of-sample FPR measurement
T_ATTACK = 300.0          # = T_BASELINE + T_HOLDOUT
T_END = 1200.0
PERSISTENCE_K = 3
ANOMALY_WINDOW = 20        # samples averaged before the score enters Eq. (8)
NOMINAL_FPR = 0.01
SHRINKAGE = 0.10
LAMBDA = 0.45
THETA = 0.05
MU_OVERHEAD = (0.35, 0.35, 0.30)
TRUST_HEALTHY = 0.97
MSGS_PER_CYCLE = 20
AUDIT_R_PER_CYCLE = 2            # operational audit budget = 10% sampling
AUDIT_BLOCKS_REF = 10_000        # replica size used for the Eq. (5) reporting rule
AUDIT_ETA = 0.95
A_MIN = 0.95
HOLD = 30.0
RTO = 300.0

ALERT_LATENCY = 1.0              # [P]
ACTUATION_LATENCY = 8.0          # [P]
VALIDATION_LATENCY = 15.0        # [P]
ROLLBACK_LATENCY = 20.0          # [P]
OPERATOR_LOG_MEDIAN = 180.0      # [P]
OPERATOR_LOG_SIGMA = 0.50        # [P]
PLAYBOOK_LATENCY = 8.0           # [P]
DECISION_COMPUTE_S = 0.001       # [P] declared decision-compute budget used in the
                                 # timeline. The MEASURED orchestrator cost is reported
                                 # separately as orchestrator_cpu_s and is deliberately
                                 # NOT fed back into the timeline: a wall-clock reading
                                 # is machine-dependent, and letting a sub-millisecond
                                 # measurement enter second-scale timestamps would make
                                 # every downstream column, and every raw-bundle hash,
                                 # irreproducible for no analytical gain.
MANUAL_REVIEW_S4 = 420.0         # [P]

DEGRADATION = {"S1": 0.25, "S2": 0.10, "S3": 0.70, "S4": 0.15}   # [P]
DEG_RAMP = 20.0                  # [P]
REC_TAU = 25.0                   # [P]
RESIDUAL_FLOOR = 0.03            # [P] impact left even by the optimal action

ACTION_SET = list(ACTION_MODELS)


@dataclass
class RunResult:
    row: dict
    raw: dict


def _seed(scenario: str, rep: int) -> int:
    h = hashlib.sha256(f"UMSF-DTCR|{scenario}|{rep}".encode()).digest()
    return int.from_bytes(h[:4], "big")


def _arm_seed(scenario: str, rep: int, arm: str) -> int:
    h = hashlib.sha256(f"UMSF-DTCR|{scenario}|{rep}|{arm}".encode()).digest()
    return int.from_bytes(h[:4], "big")


def _first_persistent(flags: np.ndarray, k: int, start: int, stop: int | None = None) -> int | None:
    stop = flags.size if stop is None else stop
    run = 0
    for i in range(max(0, start - k + 1), stop):
        run = run + 1 if flags[i] else 0
        if run >= k and i >= start:
            return i
    return None


def _descendants(W: np.ndarray, src: int) -> set[int]:
    """Assets that transitively depend on `src` (W[i, j] > 0 means j depends on i)."""
    seen, stack = set(), [src]
    while stack:
        u = stack.pop()
        for v in np.where(W[u] > 0)[0].tolist():
            if v not in seen:
                seen.add(v)
                stack.append(v)
    return seen


def build_world(scenario: str, rep: int) -> dict:
    spec = SCENARIOS[scenario]
    rng = np.random.default_rng(_seed(scenario, rep))
    assets = env.build_assets()
    W = env.build_dependency_matrix(assets)
    t = np.arange(0.0, T_END + DT, DT)
    n_base = int(T_BASELINE / DT)

    streams, sds = [], []
    for a in assets:
        mu, cov = env.node_moments(a.kind, rng)
        streams.append(env.sample_stream(mu, cov, t.size, rng))
        sds.append(np.sqrt(np.diag(cov)))

    cand = [i for i, a in enumerate(assets) if a.kind == spec.target_kind]
    target = int(rng.choice(cand))
    inj = apply_injection(streams[target], sds[target], spec, t, T_ATTACK, rng)
    streams[target] = inj.stream

    violation_type = str(rng.choice(["capacity", "security_label", "host_trust"])) \
        if spec.placement_event else ""
    return dict(spec=spec, assets=assets, W=W, t=t, n_base=n_base, streams=streams,
                sds=sds, anomaly_mask=inj.anomaly_mask, tamper_mask=inj.tamper_mask,
                target=target, violation_type=violation_type,
                impacted=_descendants(W, target) | {target})


def fit_detectors(world: dict) -> dict:
    """Baseline estimation - performed once per world, identical for every arm."""
    models, ids_thr = [], []
    for z in world["streams"]:
        base = z[: world["n_base"]]
        models.append(anomaly.fit_baseline(base, threshold_fpr=NOMINAL_FPR, shrinkage=SHRINKAGE))
        b = base[:, list(env.IDS_FEATURES)]
        zz = (z[:, list(env.IDS_FEATURES)] - b.mean(axis=0)) / b.std(axis=0, ddof=1)
        stat = np.abs(zz).max(axis=1)
        ids_thr.append(float(np.quantile(stat[: world["n_base"]], 1.0 - NOMINAL_FPR)))
        world.setdefault("ids_stat", []).append(stat)
    return {"models": models, "ids_thr": ids_thr}


def _apply_action(name: str, scenario: str, R: np.ndarray, W: np.ndarray, target: int):
    """Environment-side effect of one action; identical for every arm."""
    m = ACTION_MODELS[name]
    R2 = R.copy()
    R2[target] *= m.local_factor[scenario]
    W2 = W.copy()
    deps = np.where(W[target] > 0)[0]
    if m.collateral:
        R2[deps] += m.collateral
    W2[target] = W[target] * m.edge_factor
    return R2, W2


def _availability_trace(t, t_contain, scenario, residual, rng):
    """[P] Declared availability model.

    Both of its endogenous inputs come from the run itself: `t_contain` (when the
    decision loop actually acted) and `residual` (how good the chosen action was,
    as a normalised regret in [0,1]). The shape constants are assumptions.
    """
    depth = DEGRADATION[scenario]
    g = np.zeros_like(t)
    act = t >= T_ATTACK
    g[act] = np.clip((t[act] - T_ATTACK) / DEG_RAMP, 0.0, 1.0)
    if np.isfinite(t_contain):
        post = t >= t_contain
        residual = float(np.clip(residual, 0.0, 1.0))
        g[post] = residual + (g[post] - residual) * np.exp(-(t[post] - t_contain) / REC_TAU)
        g[post] = np.maximum(g[post], residual)
    A = 1.0 - depth * g
    return np.clip(A + rng.normal(0.0, 0.004, size=A.size), 0.0, 1.0)


def execute_run(scenario: str, arm_code: str, rep: int, phase: str,
                world: dict | None = None, fitted: dict | None = None) -> RunResult:
    arm: ArmSpec = ARMS[arm_code]
    world = world if world is not None else build_world(scenario, rep)
    fitted = fitted if fitted is not None else fit_detectors(world)
    models, ids_thr = fitted["models"], fitted["ids_thr"]
    spec = world["spec"]
    t, n_base = world["t"], world["n_base"]
    assets, W, target = world["assets"], world["W"], world["target"]
    n_assets = len(assets)
    i_attack = int(T_ATTACK / DT)
    i_hold = int(T_BASELINE / DT)
    n_hold = i_attack - i_hold
    rng = np.random.default_rng(_arm_seed(scenario, rep, arm_code))
    cpu0 = time.process_time()

    # ------------------------------------------------------------------ detection
    hits: list[int] = []
    fp_samples = 0            # per-sample exceedances inside the baseline window
    fp_persistent = 0         # nodes that produced a persistent baseline firing
    detector_used = ""
    integrity_tp = integrity_fp = integrity_cycles = 0

    if not spec.placement_event:
        for node in range(n_assets):
            z = world["streams"][node]
            flags = np.zeros(z.shape[0], dtype=bool)
            if arm.ids:
                flags |= world["ids_stat"][node] > ids_thr[node]
            if arm.twin_anomaly:
                flags |= models[node].d2(z) > models[node].d2_threshold
            # out-of-sample: never on the window used to calibrate the thresholds
            fp_samples += int(flags[i_hold:i_attack].sum())
            if _first_persistent(flags[i_hold:i_attack], PERSISTENCE_K, PERSISTENCE_K - 1) is not None:
                fp_persistent += 1
            if node == target:
                h = _first_persistent(flags, PERSISTENCE_K, i_attack)
                if h is not None:
                    hits.append(h)
                    detector_used = "anomaly" if arm.twin_anomaly else "ids"

        # integrity / provenance layer: the only mechanism that can expose a replay
        if arm.integrity and spec.tamper_fraction > 0:
            tam = world["tamper_mask"]
            for i in range(i_attack, t.size):
                integrity_cycles += 1
                d = int(round(spec.tamper_fraction * MSGS_PER_CYCLE)) if tam[i] else 0
                corrupted = set(rng.choice(MSGS_PER_CYCLE, size=d, replace=False).tolist()) if d else set()
                found, n_hits = audit.challenge(rng, MSGS_PER_CYCLE, corrupted, AUDIT_R_PER_CYCLE)
                if found:
                    integrity_tp += n_hits
                    hits.append(i)
                    detector_used = detector_used or "integrity"
                    break
                if not corrupted and rng.random() < NOMINAL_FPR:
                    integrity_fp += 1
        i_detect = min(hits) if hits else None
    else:
        i_detect = i_attack if world["violation_type"] in arm.constraints else None

    detected = i_detect is not None
    t_detect = float(t[i_detect]) if detected else float("nan")

    # -------------------------------------------------------- trust and risk state
    tp = trust.TrustParams()
    T_vec = np.full(n_assets, TRUST_HEALTHY)
    c, q, b = spec.trust_evidence
    if arm.trust:
        tr = trust.TrustTracker(tp, initial=TRUST_HEALTHY)
        for _ in range(6):
            tr.update(c, q, b)
        T_vec[target] = tr.value
    else:
        # without provenance/integrity evidence only the behavioural component moves
        tr = trust.TrustTracker(tp, initial=TRUST_HEALTHY)
        for _ in range(6):
            tr.update(0.95, 0.95, b)
        T_vec[target] = tr.value

    def _a_vector(idx: int) -> np.ndarray:
        """Trailing-window mean of the anomaly score.

        A single-sample score is a draw from U(0,1) under the null and therefore too
        noisy to drive an irreversible orchestration decision; averaging over
        ANOMALY_WINDOW samples is the smallest change that makes Eq. (8) stable.
        """
        lo = max(0, idx - ANOMALY_WINDOW + 1)
        out = np.empty(n_assets)
        for node in range(n_assets):
            d2 = models[node].d2(world["streams"][node][lo:idx + 1])
            out[node] = float(anomaly.anomaly_likelihood_chi2(d2, models[node].p).mean())
        return out

    idx_eval = i_detect if detected else t.size - 1
    a_vec = _a_vector(idx_eval)
    s_vec = np.array([a.criticality for a in assets])
    R_local = graph_risk.local_risk(a_vec, T_vec, s_vec)

    # Arm-independent ground-truth risk state, evaluated at a fixed reference instant
    # with the FULL evidence set. Ground truth must not depend on which mechanisms an
    # arm happens to run, otherwise each arm would be scored against its own target.
    i_ref = min(i_attack + int(60.0 / DT), t.size - 1)
    tr_true = trust.TrustTracker(tp, initial=TRUST_HEALTHY)
    for _ in range(6):
        tr_true.update(c, q, b)
    T_true = np.full(n_assets, TRUST_HEALTHY)
    T_true[target] = tr_true.value
    R_true = graph_risk.local_risk(_a_vector(i_ref), T_true, s_vec)

    if arm.graph:
        gr = graph_risk.propagate(R_local, W, LAMBDA)
        R_used, kappa, margin = gr.R_prop, gr.kappa, gr.margin
    else:
        R_used, kappa, margin = R_local, float("nan"), float("nan")

    flagged = set(np.where(R_used > THETA)[0].tolist())
    impacted = world["impacted"]
    blast_recall = len(flagged & impacted) / len(impacted) if impacted else float("nan")
    blast_precision = len(flagged & impacted) / len(flagged) if flagged else float("nan")
    localized = int(int(np.argmax(R_used)) == target)

    # ------------------------------------------------------------ action selection
    nodes = {}
    for i, a in enumerate(assets):
        nodes[a.node_id] = orch.Node(
            a.node_id, np.array([100.0, 100.0, 100.0]),
            np.array([rng.uniform(20, 60), rng.uniform(25, 65), rng.uniform(15, 55)]),
            security_label=2 if a.kind == "cloud" else 1, trust=float(T_vec[i]))
    demand = np.array([95.0, 95.0, 95.0]) if world["violation_type"] == "capacity" \
        else np.array([25.0, 30.0, 20.0])
    wl = orch.Workload("w0", demand,
                       security_label=3 if world["violation_type"] == "security_label" else 1,
                       min_host_trust=0.999 if world["violation_type"] == "host_trust" else 0.10)

    candidates = [orch.Action(n, "migrate" if ACTION_MODELS[n].is_placement else n,
                              target_node="c0" if ACTION_MODELS[n].is_placement else None,
                              overhead=np.asarray(ACTION_MODELS[n].overhead),
                              disruption=ACTION_MODELS[n].disruption) for n in ACTION_SET]

    engine = orch.Orchestrator(mu=MU_OVERHEAD, theta=THETA, constraints=arm.constraints)

    # Reference level used to make the risk term of Eq. (12) dimensionless. Comparing
    # an ABSOLUTE risk sum against a normalised overhead in [0,1], as Eq. (12) is
    # printed, makes the balance between the two terms depend on the number of assets
    # and on the incidental magnitude of the risk vector - see finding F-04.
    ref_pred = float(graph_risk.propagate(R_local, W, LAMBDA).R_prop.sum()) if arm.graph \
        else float(R_local.sum())
    ref_pred = ref_pred if ref_pred > 0 else 1.0

    def twin_risk(act: orch.Action) -> float:
        """What-if prediction. Graph+what-if arms evaluate the full propagated cascade
        including collateral and rerouted dependencies; arms without the graph can see
        neither the rerouting benefit nor the cascade amplification."""
        R2, W2 = _apply_action(act.name, scenario, R_local, W, target)
        val = float(graph_risk.propagate(R2, W2, LAMBDA).R_prop.sum()) \
            if (arm.whatif and arm.graph) else float(R2.sum())
        return val / ref_pred

    t0 = time.process_time()
    decision = engine.evaluate(candidates, twin_risk, workload=wl, nodes=nodes)
    decide_cpu = time.process_time() - t0

    chosen = decision.action.name if decision.action else ""

    # Ground truth, identical for every arm: realised propagated risk from R_true, and
    # the true objective value (relative residual risk + true cost) of each action.
    R_true_before = float(graph_risk.propagate(R_true, W, LAMBDA).R_prop.sum())
    R_true_before = R_true_before if R_true_before > 0 else 1.0
    realised, J_true = {}, {}
    for n in ACTION_SET:
        R2, W2 = _apply_action(n, scenario, R_true, W, target)
        realised[n] = float(graph_risk.propagate(R2, W2, LAMBDA).R_prop.sum())
        m = ACTION_MODELS[n]
        J_true[n] = realised[n] / R_true_before \
            + float(np.asarray(MU_OVERHEAD) @ np.asarray(m.overhead)) + m.disruption
    best_action = min(J_true, key=J_true.get)
    action_optimal = int(chosen == best_action)
    J_chosen = J_true.get(chosen, max(J_true.values()))
    J_best, J_worst = J_true[best_action], max(J_true.values())
    # normalised decision regret in [0,1]: 0 = truly optimal action, 1 = worst candidate
    regret = float(np.clip((J_chosen - J_best) / (J_worst - J_best), 0.0, 1.0)) \
        if J_worst > J_best else 0.0
    R_after = realised.get(chosen, R_true_before)
    effect = float(np.clip(1.0 - R_after / R_true_before, 0.0, 1.0))
    residual = RESIDUAL_FLOOR + (1.0 - RESIDUAL_FLOOR) * regret

    unsafe_action = int(bool(spec.placement_event and world["violation_type"] not in arm.constraints))
    policy_violation = unsafe_action
    rollback = int(bool(unsafe_action and arm.response != "manual"))

    # ------------------------------------------------------------ response timing
    if spec.placement_event and not detected:
        t_alert = T_ATTACK + float(rng.lognormal(np.log(MANUAL_REVIEW_S4), 0.4))
        t_action_start = t_alert + ALERT_LATENCY
        t_contain = t_action_start + ROLLBACK_LATENCY + ACTUATION_LATENCY
    elif not detected:
        t_alert = t_action_start = t_contain = float("nan")
        effect, residual = 0.0, 1.0
    else:
        t_alert = t_detect + ALERT_LATENCY
        if arm.response == "manual":
            decide = float(rng.lognormal(np.log(OPERATOR_LOG_MEDIAN), OPERATOR_LOG_SIGMA))
        elif arm.response == "playbook":
            decide = PLAYBOOK_LATENCY
        else:
            decide = ACTUATION_LATENCY + DECISION_COMPUTE_S
        t_action_start = t_alert + decide
        t_contain = t_action_start + ACTUATION_LATENCY + (ROLLBACK_LATENCY if rollback else 0.0)

    A = _availability_trace(t, t_contain, scenario, residual, rng)
    t_service_restore = resilience.recovery_time(t, A, T_ATTACK, A_MIN, HOLD)
    nri_val = resilience.nri(t, A, t_detect if detected else T_ATTACK, RTO)
    below = resilience.availability_below(t, A, A_MIN)
    t_recover = (t_contain - T_ATTACK) + VALIDATION_LATENCY if np.isfinite(t_contain) else float("nan")
    # H6 calibration: the twin predicted a RELATIVE residual risk; compare it with the
    # relative residual risk that the environment actually realised.
    whatif_abs_err = abs(decision.predicted_risk - R_after / R_true_before) \
        if arm.whatif else float("nan")

    row = {
        "run_id": f"{'CONF' if phase == 'confirmatory' else 'PILOT'}-{scenario}-{arm_code}-r{rep:03d}",
        "scenario": scenario, "arm": arm_code, "repetition": rep, "phase": phase,
        "data_origin": "simulation" if phase == "confirmatory" else "simulation_pilot",
        "site": "SIL-container", "operator_id_pseudonym": "AUTO" if arm.response != "manual" else "OP-SIM",
        "target_node": assets[target].node_id, "violation_type": world["violation_type"],
        "t_attack": T_ATTACK, "t_detect": t_detect, "t_alert": t_alert,
        "t_action_start": t_action_start, "t_contain": t_contain,
        "t_service_restore": t_service_restore, "t_recover": t_recover,
        "detection_latency": t_detect - T_ATTACK if detected else float("nan"),
        "containment_latency": t_contain - T_ATTACK if np.isfinite(t_contain) else float("nan"),
        "detected": int(detected), "contained": int(np.isfinite(t_contain)),
        "recovered": int(np.isfinite(t_service_restore)),
        "detector_used": detector_used,
        "action_selected": chosen, "action_optimal": action_optimal,
        "action_regret": regret, "containment_effect": effect,
        "residual_impact": residual,
        "policy_violation": policy_violation, "unsafe_action": unsafe_action, "rollback": rollback,
        "fp_samples_holdout": fp_samples,
        "fp_rate_holdout": fp_samples / (n_assets * n_hold),
        "fp_nodes_persistent": fp_persistent,
        "fp_per_hour": fp_persistent / (T_HOLDOUT / 3600.0),
        "integrity_tp": integrity_tp, "integrity_fp": integrity_fp,
        "integrity_cycles": integrity_cycles,
        "kappa": kappa, "convergence_margin": margin,
        "source_localized": localized, "blast_recall": blast_recall,
        "blast_precision": blast_precision,
        "whatif_abs_err": whatif_abs_err,
        "nri": nri_val, "availability_below_amin": below, "min_availability": float(A.min()),
        "orchestrator_cpu_s": decide_cpu, "run_cpu_s": time.process_time() - cpu0,
        "censored_restore": int(not np.isfinite(t_service_restore)),
        "exclusion_flag": 0, "exclusion_reason": "", "protocol_deviation": "",
    }
    raw = {"true_objective_by_action": J_true, "R_true": R_true.tolist(),
           "availability_t": t[::4].tolist(), "availability_A": A[::4].tolist(),
           "R_local": R_local.tolist(), "R_used": np.asarray(R_used).tolist(),
           "realised_risk_by_action": realised, "best_action": best_action,
           "rejected_candidates": decision.rejected,
           "admissible_candidates": decision.admissible,
           "target_index": int(target), "impacted": sorted(impacted),
           "assets": [a.node_id for a in assets]}
    return RunResult(row=row, raw=raw)
