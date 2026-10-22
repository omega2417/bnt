"""Deterministic synthetic benchmark (Section 3.9) and executed analyses.

python -m metatwin_guard.benchmark --seed 20260823 --out results
"""
from __future__ import annotations

import argparse
import csv
import json
import platform
import statistics
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

import cryptography

from . import __version__, config
from .detector import RobustDetector, StaticRules
from .generator import GeneratedRun, generate_run
from .metrics import average_precision, confusion, mean_sd, prf
from .pipeline import MetaTwinGuard

MODES = ("rules", "robust", "hybrid", "integrity_only", "rules_integrity")
MODE_LABELS = {
    "rules": "Rules",
    "robust": "Robust score",
    "hybrid": "Hybrid",
    "integrity_only": "Integrity-only",
    "rules_integrity": "Rules + integrity",
}


@dataclass
class RunResult:
    run: GeneratedRun
    guard: MetaTwinGuard
    records: list[dict[str, Any]]

    @property
    def eval_idx(self) -> list[int]:
        return list(range(self.run.n_baseline, len(self.run.events)))


def execute_run(scenario: str, rep: int, master_seed: int = config.MASTER_SEED) -> RunResult:
    run = generate_run(scenario, rep, master_seed)
    guard = MetaTwinGuard(run.registry, seed=master_seed)
    records = []
    for i, ev in enumerate(run.events):
        if i == run.n_baseline:
            guard.fit_baseline()
        records.append(guard.process(ev))
    return RunResult(run, guard, records)


def mode_predictions(rec: dict[str, Any]) -> dict[str, bool]:
    g = rec["admitted"]
    return {
        "rules": rec["rule_alert"],
        "robust": rec["robust_alert"],
        "hybrid": rec["hybrid_alert"],
        "integrity_only": not g,
        "rules_integrity": rec["rule_alert"] or not g,
    }


def run_metrics(res: RunResult) -> dict[str, Any]:
    idx = res.eval_idx
    labels = [res.run.labels[i] for i in idx]
    recs = [res.records[i] for i in idx]
    preds = [mode_predictions(r) for r in recs]
    row: dict[str, Any] = {
        "scenario": res.run.scenario,
        "rep": res.run.rep,
        "run_seed": res.run.seed,
        "n_events": len(res.run.events),
        "n_eval": len(idx),
        "n_injected": sum(labels),
        "n_rejected": sum(1 for r in recs if not r["admitted"]),
    }
    for m in MODES:
        c = confusion(labels, [p[m] for p in preds])
        for k, v in {**c, **prf(c)}.items():
            row[f"{m}_{k}"] = v
    row["robust_auprc"] = average_precision(labels, [r["robust_score"] for r in recs])

    sync = [r["sync_latency_ms"] for r in res.records if r["sync_latency_ms"] is not None]
    row["sync_latency_mean_ms"] = statistics.fmean(sync)
    row["append_median_ms"] = statistics.median(res.guard.ledger.append_times_ms)

    hits = []
    for i in idx:
        changed = res.run.changed[i]
        top = res.records[i]["top_contributions"]
        if res.run.labels[i] and changed and top:
            hits.append(any(f in changed for f, _ in top))
    row["explanation_top3_hit_rate"] = statistics.fmean(hits) if hits else float("nan")

    rep = res.guard.ledger.verify()
    row["ledger_valid"] = rep.valid
    row["ledger_blocks"] = rep.n_blocks
    row["state_unchanged_on_reject"] = all(not r["state_changed"] for r in res.records if not r["admitted"])
    return row


def summarize(rows: list[dict[str, Any]], modes: Iterable[str] = ("rules", "robust", "hybrid")) -> list[dict[str, Any]]:
    out = []
    for sc in config.SCENARIOS:
        rr = [r for r in rows if r["scenario"] == sc]
        if not rr:
            continue
        for m in modes:
            s = {"scenario": sc, "mode": m, "n_runs": len(rr)}
            for k in ("precision", "recall", "f1", "fp_per_1000_normal"):
                mu, sd = mean_sd([r[f"{m}_{k}"] for r in rr])
                s[f"{k}_mean"], s[f"{k}_sd"] = mu, sd
            out.append(s)
    return out


def scenario_extras(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    out = []
    for sc in config.SCENARIOS:
        rr = [r for r in rows if r["scenario"] == sc]
        if not rr:
            continue
        e = {"scenario": sc}
        for k in ("sync_latency_mean_ms", "append_median_ms", "explanation_top3_hit_rate", "robust_auprc"):
            e[f"{k}_mean"], e[f"{k}_sd"] = mean_sd([r[k] for r in rr])
        e["all_ledgers_valid"] = all(r["ledger_valid"] for r in rr)
        out.append(e)
    return out


def sensitivity(results: list[RunResult], floors=(0.10, 0.25, 0.50), thresholds=(2.5, 3.2, 4.0)) -> list[dict[str, Any]]:
    """Executed sensitivity: rescore the same events with alternative floor/threshold."""
    out = []
    for res in results:
        base = [e["features"] for e in res.run.events[: res.run.n_baseline]]
        idx = res.eval_idx
        labels = [res.run.labels[i] for i in idx]
        for fl in floors:
            det = RobustDetector(floor=fl).fit(base)
            scores = [det.evaluate(res.run.events[i]["features"]).score for i in idx]
            for th in thresholds:
                c = confusion(labels, [s >= th for s in scores])
                out.append({"scenario": res.run.scenario, "rep": res.run.rep, "floor": fl, "threshold": th, **c, **prf(c)})
    return out


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    if not rows:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)


def run_benchmark(master_seed: int = config.MASTER_SEED, repetitions: int = config.REPETITIONS,
                  scenarios: Iterable[str] = config.SCENARIOS, verbose: bool = False) -> tuple[list[RunResult], list[dict[str, Any]]]:
    results, rows = [], []
    for sc in scenarios:
        for rep in range(1, repetitions + 1):
            res = execute_run(sc, rep, master_seed)
            results.append(res)
            rows.append(run_metrics(res))
            if verbose:
                print(f"  {sc:24s} run {rep}: hybrid F1={rows[-1]['hybrid_f1']:.3f} ledger_valid={rows[-1]['ledger_valid']}", flush=True)
    return results, rows


def environment() -> dict[str, Any]:
    return {
        "python": sys.version.split()[0],
        "implementation": platform.python_implementation(),
        "platform": platform.platform(),
        "machine": platform.machine(),
        "processor": platform.processor(),
        "cryptography": cryptography.__version__,
        "metatwin_guard": __version__,
    }


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="MetaTwin-Guard deterministic synthetic benchmark")
    ap.add_argument("--seed", type=int, default=config.MASTER_SEED)
    ap.add_argument("--reps", type=int, default=config.REPETITIONS)
    ap.add_argument("--out", type=Path, default=Path("results"))
    ap.add_argument("--extra-seeds", type=int, nargs="*", default=[], help="additional master seeds (multi-seed gate)")
    ap.add_argument("--quiet", action="store_true")
    a = ap.parse_args(argv)

    t0 = time.time()
    results, rows = run_benchmark(a.seed, a.reps, verbose=not a.quiet)
    write_csv(a.out / "run_level.csv", rows)
    write_csv(a.out / "summary.csv", summarize(rows))
    write_csv(a.out / "ablation_executed.csv", summarize(rows, MODES))
    write_csv(a.out / "scenario_extras.csv", scenario_extras(rows))
    write_csv(a.out / "sensitivity_executed.csv", sensitivity(results))

    ms_rows = []
    for s in a.extra_seeds:
        _, r = run_benchmark(s, a.reps, verbose=False)
        for x in summarize(r, MODES):
            ms_rows.append({"master_seed": s, **x})
    if a.extra_seeds:
        write_csv(a.out / "multiseed_summary.csv", ms_rows)

    meta = {
        "artifact": "MetaTwin-Guard reference implementation",
        "evidence_level": "B (deterministic synthetic verification; not field data)",
        "master_seed": a.seed,
        "extra_seeds": a.extra_seeds,
        "scenarios": list(config.SCENARIOS),
        "repetitions": a.reps,
        "n_baseline": config.N_BASELINE,
        "n_eval": config.N_EVAL,
        "n_injected": config.N_INJECTED,
        "n_runs": len(rows),
        "n_events": sum(r["n_events"] for r in rows),
        "n_injected_total": sum(r["n_injected"] for r in rows),
        "all_ledgers_valid": all(r["ledger_valid"] for r in rows),
        "detector": {
            "mad_consistency": config.MAD_CONSISTENCY,
            "dispersion_floor": config.DISPERSION_FLOOR,
            "z_clip": config.Z_CLIP,
            "threshold": config.SCORE_THRESHOLD,
        },
        "static_rules": [list(r) for r in config.STATIC_RULES],
        "quorum": f"{config.QUORUM}-of-{config.N_VALIDATORS}",
        "environment": environment(),
        "wall_time_s": round(time.time() - t0, 2),
    }
    (a.out / "metadata.json").write_text(json.dumps(meta, indent=2))
    if not a.quiet:
        print(json.dumps({k: meta[k] for k in ("n_runs", "n_events", "n_injected_total", "all_ledgers_valid", "wall_time_s")}, indent=2))
        for s in summarize(rows):
            print(f"{s['scenario']:24s} {s['mode']:7s} P={s['precision_mean']:.3f} R={s['recall_mean']:.3f} "
                  f"F1={s['f1_mean']:.3f}±{s['f1_sd']:.3f} FP/1000={s['fp_per_1000_normal_mean']:.2f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
