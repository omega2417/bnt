#!/usr/bin/env python3
"""Build results/run_index.csv: one row per independent software run.

The unit of analysis of this deposit is a run/replicate, never an individual
telemetry row. This index makes that unit explicit and machine-readable, so a
reader can see exactly how many independent software runs the campaign
contains and which artifact directory backs each of them.
"""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path

FIELDS = [
    "run_id", "experiment_id", "scenario_id", "component", "replicate_id",
    "mode", "evidence_class", "seed", "duration_s", "rows", "gates_passed",
    "config_hash", "engine_source_hash", "run_dir", "status",
]


def component_of(run_dir: Path, results: Path) -> str:
    rel = run_dir.relative_to(results).parts
    if rel[0] == "scenarios":
        return "scenario"
    if rel[0] == "doe":
        return "doe"
    if rel[0] == "demo":
        return "demo"
    return rel[0]


def rows_for(run_dir: Path, results: Path) -> list[dict[str, object]]:
    summary = json.loads((run_dir / "summary.json").read_text(encoding="utf-8"))
    manifest = json.loads((run_dir / "manifest.json").read_text(encoding="utf-8"))
    scenario = json.loads((run_dir / "scenario.resolved.json").read_text(encoding="utf-8"))
    seed = scenario.get("seed", scenario.get("base_seed", ""))
    out: list[dict[str, object]] = []
    for replicate in summary.get("per_replicate", []):
        out.append({
            "run_id": summary["run_id"],
            "experiment_id": summary["experiment_id"],
            "scenario_id": scenario.get("experiment_id", summary["experiment_id"]),
            "component": component_of(run_dir, results),
            "replicate_id": replicate["replicate_id"],
            "mode": summary["mode"],
            "evidence_class": summary["evidence_class"],
            "seed": seed,
            "duration_s": summary["duration_s"],
            "rows": replicate["rows"],
            "gates_passed": summary["gates"]["passed"],
            "config_hash": summary["config_hash"],
            "engine_source_hash": manifest["hashes"].get("engine_source", ""),
            "run_dir": run_dir.relative_to(results.parent).as_posix(),
            "status": "completed",
        })
    return out


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--results", default="results")
    parser.add_argument("--output", default="results/run_index.csv")
    args = parser.parse_args()

    results = Path(args.results)
    runs = sorted(p.parent for p in results.rglob("summary.json"))
    rows: list[dict[str, object]] = []
    for run_dir in runs:
        rows.extend(rows_for(run_dir, results))

    with Path(args.output).open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=FIELDS, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)

    total_rows = sum(int(r["rows"]) for r in rows)
    print(json.dumps({
        "run_directories": len(runs),
        "independent_runs_replicates": len(rows),
        "telemetry_rows_total": total_rows,
        "note": "telemetry rows within one run are dependent; do not treat the "
                "total as an independent sample size",
        "output": args.output,
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
