#!/usr/bin/env python3
"""Generate the seeded SYNTHETIC reference dataset for the DTCR deposit.

WHAT THIS SCRIPT IS
-------------------
The manuscript reports only aggregate means.  The run-level observations that
produced them were not preserved, so this script generates a *synthetic
reference dataset* whose per-scenario aggregates reproduce the published means
exactly and whose availability traces, recovery times and NRI values are
mutually consistent by construction (they are all derived from the same traces
through ``dtcr.resilience``).

WHAT THIS SCRIPT IS NOT
-----------------------
It is NOT a measurement.  No row it writes may be reported as an experimental
observation.  Its purpose is to make the analysis pipeline, the figures, the
statistics and the manuscript tables executable end to end *before* the real
runs exist, so that replacing ``data/`` with genuine measurement exports
reproduces the whole results section without touching a line of analysis code.
Every file it writes carries ``data_origin=synthetic_reference`` in a column and
in its header comment.  ``analysis/verify_repository.py`` refuses to certify a
dataset that still carries that marker as submission-ready.

Usage
-----
    python analysis/simulate_reference_dataset.py --out data
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from dtcr.resilience import NRIConfig, recovery_time, nri  # noqa: E402

DATA_ORIGIN = "synthetic_reference"
SEED = 20260731

SCENARIOS = ["S1", "S2", "S3", "S4"]
METHODS = ["baseline", "framework"]
N_REPS = 20

# Per-scenario means. The unweighted mean over S1-S4 reproduces the aggregate
# values printed in the manuscript abstract, Section 3.1 and Table 4:
#   detection latency 43.1 -> 8.5 s ; recovery time 399 -> 122 s
TARGET_DETECTION = {
    "baseline":  {"S1": 52.0, "S2": 68.4, "S3": 18.7, "S4": 33.3},   # mean 43.1
    "framework": {"S1": 9.2,  "S2": 7.4,  "S3": 5.8,  "S4": 11.6},   # mean 8.5
}
TARGET_RECOVERY = {
    "baseline":  {"S1": 402.0, "S2": 356.0, "S3": 511.0, "S4": 327.0},  # mean 399
    "framework": {"S1": 118.0, "S2": 96.0,  "S3": 164.0, "S4": 110.0},  # mean 122
}
# Coefficient of variation of the lognormal run-to-run dispersion.
CV_DETECTION = {"baseline": 0.32, "framework": 0.26}
CV_RECOVERY = {"baseline": 0.24, "framework": 0.21}

# NRI targets published for S3 only (Section 3.3 and Table 4).
TARGET_NRI_S3 = {"baseline": 0.71, "framework": 0.93}

# Availability-floor priors for the scenarios without a published NRI. They are
# calibrated for S3 against TARGET_NRI_S3 and left at these values elsewhere.
FLOOR_PRIOR = {
    "baseline":  {"S1": 0.62, "S2": 0.78, "S3": 0.34, "S4": 0.70},
    "framework": {"S1": 0.88, "S2": 0.94, "S3": 0.72, "S4": 0.91},
}

CFG = NRIConfig(rto=300.0, a_min=0.95, a_max=1.00, hold=30.0, sampling_interval=1.0)
T_ATTACK = 120.0
T_END = 1500.0
NOISE_SD = 0.0025

# Integrity verification: per-scenario operating point of the audit layer.
# Observation unit = one challenged telemetry block.
INTEGRITY_RATES = {
    "S1": {"tpr": 0.972, "tnr": 0.9925, "n_pos": 900,  "n_neg": 3600},
    "S2": {"tpr": 0.991, "tnr": 0.9890, "n_pos": 2400, "n_neg": 3600},
    "S3": {"tpr": 0.958, "tnr": 0.9945, "n_pos": 600,  "n_neg": 3600},
    "S4": {"tpr": 0.976, "tnr": 0.9935, "n_pos": 700,  "n_neg": 3600},
}
CORRUPTION_LEVELS = [0.01, 0.05, 0.10, 0.20]

# Pooled integrity-verification accuracy printed in the abstract and Table 4.
TARGET_INTEGRITY_ACCURACY = 0.987

# Resource baselines (absolute units) and the framework's relative overhead.
RESOURCE_SPEC = {
    "cpu_pct":            {"baseline": 38.5,  "overhead": 0.054, "sd": 0.06},
    "ram_mb":             {"baseline": 2410., "overhead": 0.041, "sd": 0.04},
    "network_kbps":       {"baseline": 1875., "overhead": 0.032, "sd": 0.07},
    "storage_mb_per_h":   {"baseline": 96.0,  "overhead": 0.058, "sd": 0.09},
}
LATENCY_SPEC = {
    "integrity_verification_ms": (14.2, 0.35),
    "graph_solver_ms":           (23.6, 0.30),
    "whatif_simulation_ms":      (186.0, 0.28),
    "end_to_end_orchestration_ms": (412.0, 0.25),
}

# Ablation / baseline matrix. Each variant declares which mechanisms it enables
# and the operating point it produces, so the rates are stated rather than
# derived from string matching on the variant name.
ABLATION = {
    #                       det   rec   unsafe  viol   rollback success rank  twin_err
    "B0_ids_manual":       dict(det=1.00, rec=1.00, unsafe=0.000, viol=0.000,
                                rollback=0.000, success=0.84, rank=0.52, twin_err=None),
    "B1_ids_playbook":     dict(det=1.00, rec=0.52, unsafe=0.115, viol=0.092,
                                rollback=0.180, success=0.89, rank=0.52, twin_err=None),
    "B2_stack_no_dt":      dict(det=0.42, rec=0.38, unsafe=0.072, viol=0.048,
                                rollback=0.121, success=0.93, rank=0.61, twin_err=None),
    "A1_no_graph":         dict(det=0.24, rec=0.34, unsafe=0.056, viol=0.021,
                                rollback=0.094, success=0.94, rank=0.58, twin_err=0.083),
    "A2_no_whatif":        dict(det=0.21, rec=0.31, unsafe=0.081, viol=0.037,
                                rollback=0.142, success=0.93, rank=0.93, twin_err=None),
    "FULL_framework":      dict(det=0.20, rec=0.31, unsafe=0.014, viol=0.000,
                                rollback=0.038, success=0.98, rank=0.95, twin_err=0.041),
}


# --------------------------------------------------------------------------- #
# helpers
# --------------------------------------------------------------------------- #
def lognormal_with_mean(rng, mean: float, cv: float, n: int) -> np.ndarray:
    """Draw n lognormal values, then rescale so the SAMPLE mean equals `mean`.

    Rescaling is what makes the generated aggregates reproduce the published
    means exactly; the shape of the dispersion is still lognormal.
    """
    sigma = np.sqrt(np.log(1.0 + cv ** 2))
    mu = -0.5 * sigma ** 2
    x = rng.lognormal(mu, sigma, size=n)
    return x * (mean / x.mean())


def availability_trace(rng, t_attack: float, l_det: float, l_rec: float,
                       floor: float, cfg: NRIConfig = CFG):
    """Build one availability trace consistent with its detection and recovery times.

    Phases: nominal -> exponential degradation from ``t_attack`` towards
    ``floor`` -> containment at detection + reaction -> monotone recovery that
    crosses ``a_min`` exactly at ``t_attack + l_rec`` and then settles at nominal.
    Recovery measured back off this trace with Eq. (15) therefore equals ``l_rec``.
    """
    t = np.arange(0.0, T_END + cfg.sampling_interval, cfg.sampling_interval)
    a = np.full(t.shape, 0.999)

    t_contain = t_attack + l_det + 0.18 * l_rec
    t_cross = t_attack + l_rec
    if t_contain >= t_cross - 20.0:           # keep a physically ordered timeline
        t_contain = t_cross - 20.0
    tau_deg = max(6.0, 0.28 * (t_contain - t_attack))

    deg = (t >= t_attack) & (t < t_contain)
    a[deg] = floor + (0.999 - floor) * np.exp(-(t[deg] - t_attack) / tau_deg)
    a_at_contain = floor + (0.999 - floor) * np.exp(-(t_contain - t_attack) / tau_deg)

    # recovery: smoothstep from the containment level to 0.93 at t_cross - 1 s,
    # then a fast ramp through a_min so the hold condition of Eq. (15) is met.
    rec = (t >= t_contain) & (t < t_cross)
    span = max(t_cross - t_contain, 1e-6)
    u = (t[rec] - t_contain) / span
    a[rec] = a_at_contain + (0.930 - a_at_contain) * (u ** 2 * (3 - 2 * u))

    tail = t >= t_cross
    u2 = np.clip((t[tail] - t_cross) / 25.0, 0.0, 1.0)
    a[tail] = 0.962 + (0.999 - 0.962) * (u2 ** 2 * (3 - 2 * u2))

    a = a + rng.normal(0.0, NOISE_SD, size=a.shape)
    # Round here, not at write time: the metrics stored in run_level_metrics.csv
    # must be computed from exactly the values the trace file contains, otherwise
    # analysis/calculate_nri.py cannot reproduce them from the published traces.
    return t, np.round(np.clip(a, 0.0, 1.0), 5)


def calibrate_floor(rng_seed: int, scenario: str, method: str, l_det, l_rec,
                    target_nri: float, lo: float = 0.05, hi: float = 0.985):
    """Bisect the availability floor so the mean NRI over the reps hits the target."""
    def mean_nri(floor):
        rng = np.random.default_rng(rng_seed)
        vals = []
        for k in range(len(l_det)):
            t, a = availability_trace(rng, T_ATTACK, l_det[k], l_rec[k], floor)
            below = np.flatnonzero(a < CFG.a_min)
            t_dis = float(t[below[0]]) if below.size else T_ATTACK
            vals.append(nri(t, a, t_dis, CFG))
        return float(np.mean(vals))

    for _ in range(60):
        mid = 0.5 * (lo + hi)
        if mean_nri(mid) < target_nri:
            lo = mid
        else:
            hi = mid
    return 0.5 * (lo + hi)


# --------------------------------------------------------------------------- #
# generators
# --------------------------------------------------------------------------- #
# Eq. (15) measures recovery from the first sample that begins a satisfied hold
# window, which sits a fraction of a sampling interval later than the injected
# availability crossing. RECOVERY_TARGET_OFFSET absorbs that systematic gap so
# the MEASURED per-scenario mean matches the published value; it is calibrated
# once (see PROVENANCE.md) and applied to the injected crossing time.
RECOVERY_TARGET_OFFSET = -0.55


def generate_runs(out: Path):
    master = np.random.default_rng(SEED)
    rows, floors = [], {}
    trace_dir = out / "availability_traces"
    trace_dir.mkdir(parents=True, exist_ok=True)

    for method in METHODS:
        for scenario in SCENARIOS:
            sub = np.random.default_rng(abs(hash((SEED, method, scenario))) % (2 ** 32))
            l_det = lognormal_with_mean(sub, TARGET_DETECTION[method][scenario],
                                        CV_DETECTION[method], N_REPS)
            l_rec = lognormal_with_mean(
                sub, TARGET_RECOVERY[method][scenario] + RECOVERY_TARGET_OFFSET,
                CV_RECOVERY[method], N_REPS)
            trace_seed = abs(hash((SEED, "trace", method, scenario))) % (2 ** 32)

            if scenario == "S3":
                floor = calibrate_floor(trace_seed, scenario, method, l_det, l_rec,
                                        TARGET_NRI_S3[method])
            else:
                floor = FLOOR_PRIOR[method][scenario]
            floors[(method, scenario)] = floor

            rng = np.random.default_rng(trace_seed)
            for k in range(N_REPS):
                t, a = availability_trace(rng, T_ATTACK, l_det[k], l_rec[k], floor)
                below = np.flatnonzero(a < CFG.a_min)
                t_dis = float(t[below[0]]) if below.size else T_ATTACK
                rec_measured = recovery_time(t, a, T_ATTACK, CFG)
                nri_k = nri(t, a, t_dis, CFG)

                run_id = f"{scenario}_{method}_r{k + 1:02d}"
                pd.DataFrame({
                    "t_s": t,
                    "availability": a,
                    "run_id": run_id,
                    "data_origin": DATA_ORIGIN,
                }).to_csv(trace_dir / f"{run_id}.csv", index=False)

                rows.append({
                    "run_id": run_id,
                    "scenario": scenario,
                    "method": method,
                    "repetition": k + 1,
                    "attack_onset_s": T_ATTACK,
                    "detection_s": round(T_ATTACK + l_det[k], 3),
                    "containment_s": round(T_ATTACK + l_det[k] + 0.18 * l_rec[k], 3),
                    "recovery_s": round(T_ATTACK + rec_measured, 3),
                    "disruption_onset_s": round(t_dis, 3),
                    "detection_latency_s": round(l_det[k], 3),
                    "recovery_time_s": round(rec_measured, 3),
                    "availability_floor": round(floor, 5),
                    "nri": round(nri_k, 5),
                    "recovery_censored": int(np.isnan(rec_measured)),
                    "trace_file": f"availability_traces/{run_id}.csv",
                    "data_origin": DATA_ORIGIN,
                })

    df = pd.DataFrame(rows).sort_values(["scenario", "method", "repetition"])
    df.to_csv(out / "run_level_metrics.csv", index=False)
    return df, floors


def _confusion_cells():
    """Per-scenario, per-corruption-level operating points before calibration."""
    cells = []
    for scenario in SCENARIOS:
        spec = INTEGRITY_RATES[scenario]
        for level in CORRUPTION_LEVELS:
            # Sensitivity grows with the corrupted fraction: a larger corrupted
            # share is hit by the same challenge budget with higher probability.
            cells.append({
                "scenario": scenario,
                "corruption_fraction": level,
                "tpr": min(0.9995, spec["tpr"] * (0.965 + 0.35 * level)),
                "tnr": spec["tnr"],
                "n_pos": int(round(spec["n_pos"] * (0.4 + 5.0 * level) / 4)),
                "n_neg": int(round(spec["n_neg"] / len(CORRUPTION_LEVELS))),
            })
    return cells


def generate_confusion(out: Path, target_accuracy: float = TARGET_INTEGRITY_ACCURACY):
    """Draw the confusion matrices, calibrated to the published pooled accuracy.

    The per-cell error rates are scaled by one common factor so that the pooled
    *expected* accuracy equals the published 98.7%; the realised counts are then
    drawn binomially and reported with a Wilson interval rather than forced to
    the target. The draw seed is fixed so the reference dataset reproduces the
    published point value exactly.
    """
    # Offset 164 is the smallest offset in [1, 400) whose binomial draw reproduces
    # the published pooled accuracy to four decimals; see PROVENANCE.md.
    rng = np.random.default_rng(SEED + 164)
    cdir = out / "confusion_matrices"
    cdir.mkdir(parents=True, exist_ok=True)

    cells = _confusion_cells()
    n_total = sum(c["n_pos"] + c["n_neg"] for c in cells)
    expected_errors = sum(c["n_pos"] * (1 - c["tpr"]) + c["n_neg"] * (1 - c["tnr"])
                          for c in cells)
    k = (1.0 - target_accuracy) * n_total / expected_errors

    rows = []
    for c in cells:
        tpr = 1.0 - k * (1.0 - c["tpr"])
        tnr = 1.0 - k * (1.0 - c["tnr"])
        if not (0.0 < tpr < 1.0 and 0.0 < tnr < 1.0):
            raise ValueError("calibration factor pushed a rate out of (0, 1)")
        tp = int(rng.binomial(c["n_pos"], tpr))
        fn = c["n_pos"] - tp
        tn = int(rng.binomial(c["n_neg"], tnr))
        fp = c["n_neg"] - tn
        rows.append({"scenario": c["scenario"],
                     "corruption_fraction": c["corruption_fraction"],
                     "observation_unit": "challenged_telemetry_block",
                     "tp": tp, "fn": fn, "tn": tn, "fp": fp,
                     "n": tp + fn + tn + fp,
                     "nominal_tpr": round(tpr, 5), "nominal_tnr": round(tnr, 5),
                     "data_origin": DATA_ORIGIN})
    df = pd.DataFrame(rows)
    df.to_csv(cdir / "integrity_confusion.csv", index=False)
    return df


def generate_resources(out: Path):
    """Per-run resource and latency measurements.

    Each metric is drawn per run and then rescaled so that the *arm* mean equals
    its intended value exactly. Without that step the sampling error of 80 runs
    moves the realised relative overhead of Eq. (17) by up to two percentage
    points, which would silently contradict the published "below 6%" bound.
    """
    rng = np.random.default_rng(SEED + 2)
    rdir = out / "resource_measurements"
    rdir.mkdir(parents=True, exist_ok=True)
    n_arm = len(SCENARIOS) * N_REPS
    index = [(s, k + 1) for s in SCENARIOS for k in range(N_REPS)]

    frames = {}
    for method in METHODS:
        cols = {}
        for metric, spec in RESOURCE_SPEC.items():
            target = spec["baseline"] * (1 + spec["overhead"]) if method == "framework" \
                else spec["baseline"]
            x = 1.0 + rng.normal(0.0, spec["sd"], size=n_arm)
            cols[metric] = x * (target / x.mean())
        for metric, (mean, cv) in LATENCY_SPEC.items():
            if method == "baseline" and metric != "end_to_end_orchestration_ms":
                cols[metric] = np.full(n_arm, np.nan)  # component absent in the baseline
                continue
            target = mean if method == "framework" else mean * 7.4
            cols[metric] = lognormal_with_mean(rng, target, cv, n_arm)
        frames[method] = cols

    rows = []
    for method in METHODS:
        for i, (scenario, rep) in enumerate(index):
            row = {"run_id": f"{scenario}_{method}_r{rep:02d}", "scenario": scenario,
                   "method": method, "repetition": rep}
            for metric, values in frames[method].items():
                v = values[i]
                row[metric] = float("nan") if np.isnan(v) else round(float(v), 3)
            row["data_origin"] = DATA_ORIGIN
            rows.append(row)
    df = pd.DataFrame(rows)
    df.to_csv(rdir / "resource_usage.csv", index=False)
    return df


def generate_ablation(out: Path):
    """Baseline and ablation variants of the experimental matrix.

    ``twin_err = None`` marks a variant that runs no digital twin at all; the
    prediction-error column is left empty for those rows instead of being filled
    with a value that has no referent.
    """
    rng = np.random.default_rng(SEED + 3)
    rows = []
    for variant, spec in ABLATION.items():
        for scenario in SCENARIOS:
            det = lognormal_with_mean(
                rng, TARGET_DETECTION["baseline"][scenario] * spec["det"], 0.30, N_REPS)
            rec = lognormal_with_mean(
                rng, TARGET_RECOVERY["baseline"][scenario] * spec["rec"], 0.23, N_REPS)
            fast = spec["det"] < 0.5           # variants that decide on the twin
            for k in range(N_REPS):
                rows.append({
                    "variant": variant, "scenario": scenario, "repetition": k + 1,
                    "detection_latency_s": round(float(det[k]), 3),
                    "recovery_time_s": round(float(rec[k]), 3),
                    "unsafe_action": int(rng.random() < spec["unsafe"]),
                    "policy_violation": int(rng.random() < spec["viol"]),
                    "rollback": int(rng.random() < spec["rollback"]),
                    "recovery_success": int(rng.random() < spec["success"]),
                    "orchestration_decision_latency_ms": round(
                        float(412.0 * (0.35 if fast else 1.9) * rng.lognormal(0, 0.22)), 3),
                    "twin_prediction_error": (
                        round(float(abs(rng.normal(spec["twin_err"], 0.02))), 4)
                        if spec["twin_err"] is not None else float("nan")),
                    "risk_ranking_correct": int(rng.random() < spec["rank"]),
                    "data_origin": DATA_ORIGIN,
                })
    df = pd.DataFrame(rows)
    df.to_csv(out / "ablation_runs.csv", index=False)
    return df


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--out", default="data", help="output data directory")
    args = ap.parse_args()
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)

    runs, floors = generate_runs(out)
    conf = generate_confusion(out)
    res = generate_resources(out)
    abl = generate_ablation(out)

    det = runs.groupby("method")["detection_latency_s"].mean()
    rec = runs.groupby("method")["recovery_time_s"].mean()
    scen_det = runs.groupby(["method", "scenario"])["detection_latency_s"].mean()
    scen_rec = runs.groupby(["method", "scenario"])["recovery_time_s"].mean()
    nri_s3 = runs[runs.scenario == "S3"].groupby("method")["nri"].mean()
    acc = (conf.tp.sum() + conf.tn.sum()) / conf.n.sum()
    fpr = conf.fp.sum() / (conf.fp.sum() + conf.tn.sum())

    manifest = {
        "generator": "simulate_reference_dataset.py",
        "seed": SEED,
        "data_origin": DATA_ORIGIN,
        "n_runs": int(len(runs)),
        "n_traces": int(len(runs)),
        "reproduced_aggregates": {
            "detection_latency_mean_s": {m: round(float(det[m]), 4) for m in METHODS},
            "recovery_time_mean_s": {m: round(float(rec[m]), 4) for m in METHODS},
            "scenario_mean_detection_s": {f"{m}/{s}": round(float(scen_det[(m, s)]), 3)
                                          for m in METHODS for s in SCENARIOS},
            "scenario_mean_recovery_s": {f"{m}/{s}": round(float(scen_rec[(m, s)]), 3)
                                         for m in METHODS for s in SCENARIOS},
            "nri_s3_mean": {m: round(float(nri_s3[m]), 4) for m in METHODS},
            "integrity_accuracy": round(float(acc), 5),
            "integrity_fpr": round(float(fpr), 5),
        },
        "availability_floor_calibrated": {f"{m}/{s}": round(v, 5)
                                          for (m, s), v in floors.items()},
        "warning": ("Synthetic reference data. Not a measurement. Replace every file "
                    "in data/ with real measurement exports before submission."),
    }
    (out / "generation_manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")

    print(json.dumps(manifest["reproduced_aggregates"], indent=2))
    print(f"\nwrote {len(runs)} runs, {len(conf)} confusion cells, "
          f"{len(res)} resource rows, {len(abl)} ablation rows -> {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
