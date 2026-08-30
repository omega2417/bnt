"""Campaign driver: randomisation plan, pilot, calibration and confirmatory series."""
from __future__ import annotations

import argparse
import csv
import gzip
import hashlib
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from harness.arms import ARMS
from harness.runner import build_world, execute_run, fit_detectors
from harness.scenarios import SCENARIOS

RANDOMIZATION_SEED = 20260830      # frozen in protocol/preregistration.yaml


def randomization_plan(scenarios, arms, reps, phase):
    """Pre-generated order of execution: arm order is permuted inside every block."""
    rng = np.random.default_rng(RANDOMIZATION_SEED if phase == "confirmatory"
                                else RANDOMIZATION_SEED + 1)
    rows, order = [], 0
    blocks = [(s, r) for s in scenarios for r in range(1, reps + 1)]
    rng.shuffle(blocks)
    for scenario, rep in blocks:
        perm = list(arms)
        rng.shuffle(perm)
        for arm in perm:
            order += 1
            rows.append({"execution_order": order, "phase": phase, "scenario": scenario,
                         "repetition": rep, "arm": arm})
    return rows


def sha256_file(p: Path) -> str:
    h = hashlib.sha256()
    with p.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def run_campaign(phase: str, reps: int, outdir: Path) -> Path:
    outdir = Path(outdir).resolve()
    scenarios = list(SCENARIOS)
    arms = list(ARMS)
    plan = randomization_plan(scenarios, arms, reps, phase)
    (ROOT / "protocol").mkdir(exist_ok=True)
    plan_path = ROOT / "protocol" / f"randomization_{phase}.csv"
    with plan_path.open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(plan[0]))
        w.writeheader(); w.writerows(plan)

    raw_dir = outdir / "raw"
    raw_dir.mkdir(parents=True, exist_ok=True)
    cache: dict[tuple[str, int], tuple[dict, dict]] = {}
    rows = []
    t0 = time.time()
    for i, item in enumerate(plan, 1):
        key = (item["scenario"], item["repetition"])
        if key not in cache:
            world = build_world(*key)
            cache[key] = (world, fit_detectors(world))
        world, fitted = cache[key]
        res = execute_run(item["scenario"], item["arm"], item["repetition"],
                          phase, world, fitted)
        res.row["execution_order"] = item["execution_order"]
        res.row["start_utc"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
        blob = json.dumps(res.raw, separators=(",", ":"), sort_keys=True).encode()
        rp = raw_dir / f"{res.row['run_id']}.json.gz"
        with gzip.open(rp, "wb", compresslevel=9) as f:
            f.write(blob)
        res.row["raw_log_path"] = str(rp.relative_to(ROOT))
        res.row["raw_log_sha256"] = hashlib.sha256(blob).hexdigest()
        rows.append(res.row)
        if len(cache) > 8:
            cache.pop(next(iter(cache)))
        if i % 60 == 0:
            print(f"  {i}/{len(plan)} runs, {time.time()-t0:.0f}s", flush=True)

    fields = list(rows[0])
    out = outdir / "runs.csv"
    outdir.mkdir(parents=True, exist_ok=True)
    with out.open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        w.writerows(rows)
    print(f"wrote {out} ({len(rows)} runs, {time.time()-t0:.0f}s)")
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--phase", choices=["pilot", "confirmatory"], required=True)
    ap.add_argument("--reps", type=int, required=True)
    ap.add_argument("--outdir", type=Path, required=True)
    a = ap.parse_args()
    run_campaign(a.phase, a.reps, a.outdir)


if __name__ == "__main__":
    main()
