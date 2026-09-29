#!/usr/bin/env python3
"""Run the full emulated campaign E00–E11 and write the result package
(section 15.1): manifest, configs, raw per-run logs, metrics, protocols,
figures, checksums.

Usage:  python scripts/run_campaign.py [--blocks 10] [--workers 4]
"""
from __future__ import annotations

import argparse
import csv
import json
import platform
import shutil
import sys
import time
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from dtpower import EVIDENCE_CLASS, __version__, bench, calibration, config, replay, scenarios, sizing, stats  # noqa: E402
from dtpower.edge_guard import EdgeGuard  # noqa: E402

OUT = ROOT / "results"
BENCH_SEED = 1
BASE_SEED = 20260929


def _jsonable(o):
    if isinstance(o, (np.floating,)):
        return float(o)
    if isinstance(o, (np.integer,)):
        return int(o)
    if isinstance(o, (np.bool_,)):
        return bool(o)
    if isinstance(o, np.ndarray):
        return o.tolist()
    raise TypeError(type(o))


def dump(path: Path, obj):
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=1, default=_jsonable)


_BENCH = None


def _init_worker():
    global _BENCH
    hw = config.load("hardware_bench_12v.json")
    _BENCH, _, _ = bench.build_bench(hw, BENCH_SEED)


def _job(args):
    sid, policy, repeat, seed = args
    pcfg = config.load("policies.json")
    sc = scenarios.ALL[sid]()
    t0 = time.time()
    m = bench.run(_BENCH, sc, policy, pcfg, repeat=repeat, seed=seed)
    m["wall_s"] = time.time() - t0
    return m


def write_run_raw(m: dict):
    d = OUT / "raw" / m["run_id"]
    d.mkdir(parents=True, exist_ok=True)
    s = m.get("series", {})
    if s:
        keys = list(s.keys())
        with open(d / "telemetry_10s.csv", "w", newline="") as f:
            w = csv.writer(f)
            w.writerow(keys)
            for row in zip(*[s[k] for k in keys]):
                w.writerow(["" if v is None else (round(v, 6) if isinstance(v, float) else v) for v in row])
    with open(d / "events.csv", "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["run_id", "event_id", "t_model_s", "event_type", "value"])
        for i, e in enumerate(m["events"]):
            w.writerow([m["run_id"], i, round(e["t"], 3), e["event_type"], e["value"]])
    with open(d / "commands.csv", "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["run_id", "command_id", "action", "reason", "sent_s", "ack_s", "effect_s", "effect_kind", "accepted", "reject_reason", "retry_of"])
        for c in m["commands_log"]:
            w.writerow([m["run_id"], c["command_id"], c["action"], c["reason"], round(c["sent"], 4),
                        "" if c["ack"] is None else round(c["ack"], 4), "" if c["effect"] is None else round(c["effect"], 4), c.get("effect_kind") or "",
                        c["accepted"], c["reject_reason"], c["retry_of"] or ""])
    with open(d / "edge_log.csv", "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["t_s", "kind", "detail"])
        for r in m["edge_log"]:
            w.writerow([round(r[0], 4), r[1], r[2]])


def run_protocol_text(m: dict, cfg_hash: str, prof_note: str) -> str:
    return "\n".join([
        f"RUN_ID: {m['run_id']}", f"SCENARIO_ID: {m['scenario_id']}", f"MODE: {m['mode']}  [{EVIDENCE_CLASS}]",
        f"POLICY: {m['policy']}", f"REPEAT_ID: {m['repeat']}", f"PAIR_BLOCK_ID: {m['scenario_id']}_B{m['repeat']:02d}",
        "OPERATOR: automated (scripts/run_campaign.py)", "START_UTC: model t=0 (emulated)",
        f"END_UTC: model t={m['duration_h'] * 3600:.0f} s", f"START_SOC_REFERENCE: {m['soc_ref_start']:.4f}",
        "START_SOC_UNCERTAINTY_PP: 0.4 (1 sigma, preparation procedure)", "START_BATTERY_TEMPERATURE_C: 22.0",
        f"CONFIG_SHA256: {cfg_hash}", "FIRMWARE_SHA256: n/a (edge_guard emulated by dtpower/edge_guard.py)",
        f"MODEL_VERSION: dtpower {__version__}", f"PROFILE: {prof_note}", "CALIBRATION_ID: CAL-B1-E00",
        f"REAL_DURATION_S: {m.get('wall_s', 0):.1f} (wall clock of the emulation)", f"MODEL_DURATION_S: {m['duration_h'] * 3600:.0f}",
        f"STOP_REASON: {m['stop_reason']}", f"VALID_COVERAGE_PERCENT: {m['coverage_pct']:.3f}",
        f"UNKNOWN_DURATION_S: {m['unknown_duration_s']:.1f}", "MANUAL_INTERVENTIONS: none",
        f"CRITICAL_SERVICE_EVENTS: {m['service_failures']} failed checks of {m['service_checks']} (longest streak {m['service_longest_fail_s']} s)",
        f"RAW_FILES_AND_CHECKSUMS: raw/{m['run_id']}/ (see checksums.sha256)", "DEVIATIONS_FROM_PLAN: none",
        f"STATUS: {'completed' if m['stop_reason'] == 'completed' else 'stopped_limit' if m['stop_reason'] == 'stopped_limit' else m['stop_reason']}",
        "OPERATOR_REVIEW: n/a (emulated)", "ANALYST_REVIEW: automated metrics; see report",
    ]) + "\n"


def e10_vectors():
    """E10 — protection/contract logic by signal injection on the edge model."""
    rows = []

    def eg():
        g = EdgeGuard("R", "B", "sil_hw_emulated", 0.0, 0.015, stale_s=5)
        g.self_test(True)
        g.start(0.0)
        return g

    base = {"schema_version": "1.0", "mode": "sil_hw_emulated", "source": "ems", "run_id": "R", "boot_id_target": "B"}
    cases = [
        ("ON accepted in RUNNING with permissions", lambda g: g.handle_command(1, {**base, "command_id": "a", "action": "SET_AUX_ON", "expires_at_utc": 3}), True),
        ("Low pack voltage (12.2 V < 12.4 V) forces OFF", lambda g: (g.handle_command(1, {**base, "command_id": "a", "action": "SET_AUX_ON", "expires_at_utc": 3}), g.tick(2, 12.2, 20, False))[1] or {"accepted": not g.aux_out}, True),
        ("ON rejected while local protection active", lambda g: (g.tick(1, 12.2, 20, False), g.handle_command(1.1, {**base, "command_id": "b", "action": "SET_AUX_ON", "expires_at_utc": 3}))[1], False),
        ("BMS open forces OFF", lambda g: (g.handle_command(1, {**base, "command_id": "a", "action": "SET_AUX_ON", "expires_at_utc": 3}), g.tick(2, 13.2, 20, True))[1] or {"accepted": not g.aux_out}, True),
        ("Expired command rejected (TTL, clock bound)", lambda g: g.handle_command(10, {**base, "command_id": "c", "action": "SET_AUX_ON", "expires_at_utc": 10.01}), False),
        ("Wrong run_id rejected", lambda g: g.handle_command(1, {**base, "run_id": "X", "command_id": "d", "action": "SET_AUX_ON", "expires_at_utc": 3}), False),
        ("Wrong boot_id rejected", lambda g: g.handle_command(1, {**base, "boot_id_target": "X", "command_id": "e", "action": "SET_AUX_ON", "expires_at_utc": 3}), False),
        ("TOGGLE not accepted (non-idempotent)", lambda g: g.handle_command(1, {**base, "command_id": "f", "action": "TOGGLE", "expires_at_utc": 3}), False),
        ("Duplicate QoS-1 delivery does not re-switch", lambda g: (g.handle_command(1, {**base, "command_id": "g", "action": "SET_AUX_ON", "expires_at_utc": 3}), g.handle_command(1.5, {**base, "command_id": "g", "action": "SET_AUX_ON", "expires_at_utc": 3}))[1], True),
        ("Heartbeat loss > 5 s -> DEGRADED, aux OFF", lambda g: (g.handle_command(1, {**base, "command_id": "h", "action": "SET_AUX_ON", "expires_at_utc": 3}), g.tick(7, 13.2, 20, False))[1] or {"accepted": g.state == "DEGRADED" and not g.aux_out}, True),
        ("ON rejected in DEGRADED", lambda g: (g.tick(7, 13.2, 20, False), g.handle_command(7.1, {**base, "command_id": "i", "action": "SET_AUX_ON", "expires_at_utc": 9}))[1], False),
        ("Synthetic-mode command rejected in physical mode", lambda g: g.handle_command(1, {**base, "mode": "physical", "command_id": "j", "action": "SET_AUX_ON", "expires_at_utc": 3}), False),
    ]
    for name, fn, expect in cases:
        g = eg()
        r = fn(g)
        got = bool(r["accepted"])
        rows.append({"test": name, "expected_accepted_or_condition": expect, "observed": got, "pass": got == expect,
                     "aux_out_after": g.aux_out, "state_after": g.state, "reject_reason": r.get("reject_reason", "")})
    return rows


def e07_detection(m: dict):
    sc = scenarios.e07()
    out = []
    inv = [(e["t"], e["value"]) for e in m["events"] if e["event_type"] == "INVALID_SAMPLE"]
    for f0, f1, kind, param in sc.sensor_faults:
        hits = [(t, r) for t, r in inv if f0 <= t <= f1 + 2]
        det = hits[0] if hits else None
        out.append({"fault": kind, "param": param, "t_start_s": f0, "duration_s": f1 - f0,
                    "detected": det is not None, "latency_s": (det[0] - f0) if det else None,
                    "flag": det[1] if det else "", "flagged_samples": len(hits),
                    "flagged_fraction": len(hits) / (f1 - f0)})
    false_pos = [t for t, _ in inv if not any(f0 <= t <= f1 + 2 for f0, f1, _, _ in sc.sensor_faults)]
    return out, len(false_pos)


def common_interval_aux(runs_by_policy):
    """Aux energy served up to the earliest termination among paired policies (12.6)."""
    t_common = min(r["duration_h"] for r in runs_by_policy.values()) * 3600
    res = {}
    for p, r in runs_by_policy.items():
        s = r["series"]
        t = np.asarray(s["t"])
        paux = np.asarray(s["p_aux_term"])
        mask = t <= t_common
        # series is 10-s decimated plus switch instants; integrate as step function
        tt = np.r_[0.0, t[mask]]
        res[p] = float(np.sum(paux[mask] * np.diff(tt)) / 3600)
    return t_common / 3600, res


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--blocks", type=int, default=10)
    ap.add_argument("--workers", type=int, default=4)
    a = ap.parse_args()
    t_start = time.time()
    if OUT.exists():
        shutil.rmtree(OUT)
    OUT.mkdir(parents=True)
    hw = config.load("hardware_bench_12v.json")
    pcfg = config.load("policies.json")
    art = config.load("article_scenarios.json")
    cfg_hash = config.config_hash({"hw": hw, "policies": pcfg, "article": art})

    # ---- E00 / E09 -------------------------------------------------------
    inst, cal, cap = bench.build_bench(hw, BENCH_SEED)
    dump(OUT / "calibration" / "E00_calibration.json", cal)
    dump(OUT / "calibration" / "E09_capacity.json", cap)
    chan_rows = [calibration.channel_protocol_row(n, hw) for n in hw["channels"]]
    budgets = {}
    for n, ops in {"M1": [-10.0, -2.0, 2.0, 4.0], "REF": [-10.0, 2.0, 4.0], "M0": [1.0, 4.0], "M2": [1.5], "M4": [2.5]}.items():
        chc = hw["channels"][n]
        ic, sh = hw["sensors"][chc["meter"]], hw["shunts"][chc["shunt"]]
        resid = max(abs(r["residual_rel"]) for r in cal[n]["levels"] if r["residual_rel"] == r["residual_rel"])
        budgets[n] = [calibration.uncertainty_budget(chc, ic, sh, hw["calibration_standard"], i, residual_rel=resid) for i in ops]
    dump(OUT / "calibration" / "channel_characteristics.json", chan_rows)
    dump(OUT / "calibration" / "uncertainty_budget.json", budgets)

    # ---- job list ----------------------------------------------------------
    jobs = []
    for sid in ("E01", "E02", "E04", "E06", "E07"):
        jobs.append((sid, "C1" if sid in ("E06", "E07") else "C0", 0, BASE_SEED))
    for sid in ("E03", "E08"):
        for p in ("C0", "C1", "C2"):
            jobs.append((sid, p, 0, BASE_SEED + 11 + ord(sid[-1])))
    for b in range(a.blocks):
        for p in ("C0", "C1", "C2", "C_oracle"):
            jobs.append(("E05", p, b, BASE_SEED + 1000 * (b + 1)))  # same seed within a block: paired
    # deterministic seeds for single runs
    jobs = [(s, p, r, int(sd) if s in ("E03", "E05", "E08") else BASE_SEED + 7 * i) for i, (s, p, r, sd) in enumerate(jobs)]
    print(f"{len(jobs)} runs on {a.workers} workers ...", flush=True)
    with ProcessPoolExecutor(a.workers, initializer=_init_worker) as ex:
        runs = list(ex.map(_job, jobs))
    print(f"runs done in {time.time() - t_start:.0f} s", flush=True)

    # ---- per-run outputs ----------------------------------------------------
    prot_dir = OUT / "protocols"
    prot_dir.mkdir()
    metric_cols = ["run_id", "scenario_id", "policy", "repeat", "mode", "duration_h", "stop_reason", "right_censored", "coverage_pct",
                   "unknown_duration_s", "soc_ref_start", "min_soc_ref", "mae_soc_pp", "rmse_soc_pp", "max_soc_err_pp",
                   "ref_vs_true_mae_pp", "energy_error_pct", "critical_unserved_wh", "aux_served_wh", "aux_unserved_wh",
                   "lolh_critical_h", "lpsp_critical", "lpsp_total", "service_checks", "service_failures", "availability_pct",
                   "commands", "commands_accepted", "commands_effect_confirmed", "switch_count", "residual_w_mean", "residual_w_sd",
                   "e_gen_wh", "e_curtailed_wh", "e_ref_dis_wh"]
    with open(OUT / "metrics_runs.csv", "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(metric_cols + ["rtt_median_ms", "rtt_p95_ms", "rtt_max_ms", "effect_median_ms", "effect_max_ms"])
        for m in runs:
            write_run_raw(m)
            sc = scenarios.ALL[m["scenario_id"]]()
            (prot_dir / f"{m['run_id']}.txt").write_text(run_protocol_text(m, cfg_hash, sc.note), encoding="utf-8")
            w.writerow([m[c] if not isinstance(m[c], float) else round(m[c], 6) for c in metric_cols] +
                       [round(m["rtt"].get(k, float("nan")), 3) if m["rtt"]["n"] else "" for k in ("median_ms", "p95_ms", "max_ms")] +
                       [round(m["decision_to_effect"].get(k, float("nan")), 1) if m["decision_to_effect"]["n"] else "" for k in ("median_ms", "max_ms")])

    # ---- E05 paired statistics ----------------------------------------------
    e05 = [m for m in runs if m["scenario_id"] == "E05"]
    blocks = {}
    for m in e05:
        blocks.setdefault(m["repeat"], {})[m["policy"]] = m
    B = sorted(blocks)
    get = lambda p, k: [blocks[b][p][k] for b in B]  # noqa: E731
    ci_common = {b: common_interval_aux({p: blocks[b][p] for p in ("C0", "C1", "C2")}) for b in B}
    prim = {
        "C1_minus_C0": stats.paired_summary(get("C0", "time_to_limit_h"), get("C1", "time_to_limit_h"), "time_to_limit_h C1-C0"),
        "C2_minus_C1": stats.paired_summary(get("C1", "time_to_limit_h"), get("C2", "time_to_limit_h"), "time_to_limit_h C2-C1"),
    }
    adj = stats.holm({k: v["p_signflip"] for k, v in prim.items()})
    for k in prim:
        prim[k]["p_holm"] = adj[k]
    sec = {}
    for metric, better in (("aux_served_wh", 1), ("min_soc_ref", 1), ("switch_count", -1), ("mae_soc_pp", -1), ("critical_unserved_wh", -1)):
        for a_, b_ in (("C0", "C1"), ("C1", "C2"), ("C2", "C_oracle")):
            x, y = np.array(get(a_, metric), float), np.array(get(b_, metric), float)
            s = stats.paired_summary(x, y, f"{metric} {b_}-{a_}")
            s["orientation"] = "higher is better" if better > 0 else "lower is better"
            sec[f"{metric}:{b_}-{a_}"] = s
    aux_common = {p: [ci_common[b][1][p] for b in B] for p in ("C0", "C1", "C2")}
    sec["aux_served_common_interval_wh:C1-C0"] = stats.paired_summary(aux_common["C0"], aux_common["C1"], "aux served to common end C1-C0")
    sec["aux_served_common_interval_wh:C2-C1"] = stats.paired_summary(aux_common["C1"], aux_common["C2"], "aux served to common end C2-C1")
    fried = {k: stats.friedman(*[get(p, k) for p in ("C0", "C1", "C2")]) for k in ("aux_served_wh", "min_soc_ref", "time_to_limit_h")}
    e05_summary = {"blocks": len(B), "primary": prim, "secondary": sec, "friedman": fried,
                   "common_interval_h": {b: ci_common[b][0] for b in B}, "aux_common": aux_common,
                   "per_policy": {p: {k: {"mean": float(np.mean(get(p, k))), "sd": float(np.std(get(p, k), ddof=1)), "min": float(np.min(get(p, k))), "max": float(np.max(get(p, k)))}
                                      for k in ("time_to_limit_h", "aux_served_wh", "min_soc_ref", "critical_unserved_wh", "mae_soc_pp", "max_soc_err_pp",
                                                "energy_error_pct", "switch_count", "coverage_pct", "availability_pct")}
                                  | {"censored": int(sum(get(p, "right_censored")))} for p in ("C0", "C1", "C2", "C_oracle")}}

    # ---- other analyses -----------------------------------------------------
    e07_run = next(m for m in runs if m["scenario_id"] == "E07")
    e07_tab, e07_fp = e07_detection(e07_run)
    e10 = e10_vectors()
    e11 = replay.run_e11(art, pcfg)
    sizing_tab = {s: sizing.size_scenario(art["scenarios"][s], art["common"]) for s in ("S1", "S2", "S3")}
    sens = sizing.sensitivity(art["common"])
    psh_g, eta_g, grid = sizing.sensitivity_grid(art["common"])

    all_rtt = [c["ack"] - c["sent"] for m in runs for c in m["commands_log"] if c["ack"] is not None and c["reason"] not in ("E06_stale_test", "E06_wrong_run")]
    all_eff = [c["effect"] - c["decision_t"] for m in runs for c in m["commands_log"] if c["accepted"] and c["effect"] is not None and c.get("effect_kind") == "edge"]
    n_state_conf = sum(1 for m in runs for c in m["commands_log"] if c["accepted"] and c.get("effect_kind") == "state_confirmed")
    n_acc = sum(m["commands_accepted"] for m in runs)
    n_conf = sum(m["commands_effect_confirmed"] for m in runs)
    normal = [m for m in runs if m["scenario_id"] not in ("E06", "E07")]
    cov_min = min(m["coverage_pct"] for m in normal)
    mae_all = [m["mae_soc_pp"] for m in normal]
    max_all = [m["max_soc_err_pp"] for m in normal]
    en_all = [m["energy_error_pct"] for m in normal if m["energy_error_pct"] == m["energy_error_pct"]]
    e06 = next(m for m in runs if m["scenario_id"] == "E06")
    e06_ev = [e for e in e06["events"] if e["event_type"] in ("TELEMETRY_STALE", "TELEMETRY_RESTORED")]
    e06_edge = [r for r in e06["edge_log"] if r[1] in ("STATE", "AUX_OFF", "AUX_ON", "REJECT")]
    acceptance = [
        {"object": "Telemetry (normal runs)", "criterion": ">= 99 % valid expected packets", "observed": f"min {cov_min:.2f} %", "pass": cov_min >= 99},
        {"object": "Gaps > 5 s", "criterion": "each has an event and a defined control state", "observed": f"E06: {len(e06_ev)} stale/restore events; edge log {len(e06_edge)} entries", "pass": len(e06_ev) >= 2},
        {"object": "Energy model", "criterion": "<= 5 % on non-zero integral", "observed": f"max {max(en_all):.2f} %", "pass": max(en_all) <= 5},
        {"object": "SOC", "criterion": "MAE <= 3 pp, max <= 5 pp vs independent REF", "observed": f"MAE max {max(mae_all):.2f} pp; |err| max {max(max_all):.2f} pp", "pass": max(mae_all) <= 3 and max(max_all) <= 5},
        {"object": "Command transfer", "criterion": "p95 RTT <= 2 s", "observed": f"p95 {np.percentile(np.array(all_rtt) * 1000, 95):.1f} ms (n={len(all_rtt)}), max {max(all_rtt) * 1000:.1f} ms", "pass": np.percentile(all_rtt, 95) <= 2},
        {"object": "Physical execution", "criterion": "every accepted command has a confirmed effect", "observed": f"{n_conf}/{n_acc}", "pass": n_conf == n_acc},
        {"object": "E06", "criterion": "stale detected, fallback applied", "observed": "; ".join(f"{e['event_type']}@{e['t']:.0f}s" for e in e06_ev), "pass": any(e["event_type"] == "TELEMETRY_STALE" for e in e06_ev)},
        {"object": "E07", "criterion": "each injected fault flagged", "observed": f"{sum(r['detected'] for r in e07_tab)}/{len(e07_tab)} detected, {e07_fp} false flags", "pass": all(r["detected"] for r in e07_tab)},
        {"object": "E10", "criterion": "all protection/contract vectors pass", "observed": f"{sum(r['pass'] for r in e10)}/{len(e10)}", "pass": all(r["pass"] for r in e10)},
        {"object": "Critical service", "criterion": "no detected outage in nominal runs", "observed": f"critical unserved max {max(m['critical_unserved_wh'] for m in normal):.3f} Wh; service failures total {sum(m['service_failures'] for m in normal)} of {sum(m['service_checks'] for m in normal)} checks", "pass": max(m['critical_unserved_wh'] for m in normal) == 0},
        {"object": "Forecast advantage (C2 vs C1)", "criterion": "pre-specified effect with uncertainty", "observed": "see E05 primary/secondary contrasts", "pass": None},
    ]

    summary = {
        "evidence_class": EVIDENCE_CLASS, "dtpower_version": __version__, "config_sha256": cfg_hash,
        "bench": {"seed": BENCH_SEED, "hidden_truth": {"capacity_ah": inst.truth.capacity_ah, "r0": inst.truth.r0, "ocv_shift_v": inst.truth.ocv_shift_v},
                  "eta_crit": inst.eta_crit, "eta_aux": inst.eta_aux},
        "calibration": {n: {k: v for k, v in c.items() if k != "levels"} for n, c in cal.items()}, "capacity": cap,
        "channels": chan_rows, "uncertainty": budgets,
        "runs": [{k: v for k, v in m.items() if k not in ("series", "edge_log", "events", "commands_log")} for m in runs],
        "e05": e05_summary, "e07": {"table": e07_tab, "false_flags": e07_fp}, "e10": e10,
        "e06": {"events": e06_ev, "edge": e06_edge, "commands": [c for c in e06["commands_log"]]},
        "e11": e11, "sizing": sizing_tab, "sensitivity": sens,
        "sensitivity_grid": {"psh": psh_g.tolist(), "eta": eta_g.tolist(), "wp": grid.tolist()},
        "timing": {"rtt_ms": {"n": len(all_rtt), "median": float(np.median(all_rtt) * 1000), "p95": float(np.percentile(all_rtt, 95) * 1000),
                              "p99": float(np.percentile(all_rtt, 99) * 1000), "max": float(np.max(all_rtt) * 1000)},
                   "effect_ms": {"n": len(all_eff), "median": float(np.median(all_eff) * 1000), "p95": float(np.percentile(all_eff, 95) * 1000),
                                 "max": float(np.max(all_eff) * 1000)}, "state_confirmations": n_state_conf},
        "acceptance": acceptance,
    }
    dump(OUT / "summary.json", summary)
    # compact series for figures/web
    series = {}
    for m in runs:
        if m["scenario_id"] in ("E02", "E03", "E04", "E06", "E08") or (m["scenario_id"] == "E05" and m["repeat"] == 0):
            series[m["run_id"]] = m["series"]
    dump(OUT / "series_selected.json", series)
    shutil.copytree(ROOT / "configs", OUT / "configs")

    manifest = {"created_by": "scripts/run_campaign.py", "evidence_class": EVIDENCE_CLASS, "dtpower_version": __version__,
                "python": platform.python_version(), "numpy": np.__version__, "platform": platform.platform(),
                "bench_seed": BENCH_SEED, "base_seed": BASE_SEED, "blocks_e05": a.blocks, "n_runs": len(runs),
                "config_sha256": cfg_hash, "run_ids": [m["run_id"] for m in runs], "wall_time_s": time.time() - t_start}
    dump(OUT / "manifest.json", manifest)
    lines = []
    for p in sorted(OUT.rglob("*")):
        if p.is_file() and p.name != "checksums.sha256":
            lines.append(f"{config.sha256_file(p)}  {p.relative_to(OUT)}")
    (OUT / "checksums.sha256").write_text("\n".join(lines) + "\n")
    print(f"done in {time.time() - t_start:.0f} s; {len(lines)} files")


if __name__ == "__main__":
    main()
