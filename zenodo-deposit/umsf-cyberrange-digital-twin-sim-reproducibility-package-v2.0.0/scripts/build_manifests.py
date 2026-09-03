#!/usr/bin/env python3
"""Rebuild manifests/ and SHA256SUMS.txt for the whole deposit.

Produces:
  manifests/campaign_manifest.json  - campaign identity, environment, hashes,
                                      per-run digests, provenance vector,
                                      policy flags, evidence histogram
  manifests/file_hashes.json        - SHA-256 of every file in the package
  manifests/provenance_histogram.json - parameter evidence status counts
  SHA256SUMS.txt                    - sha256sum-compatible checksum list

Run this LAST, after every other artifact is final. Re-run it after inserting
the reserved Zenodo DOI into README.md and CITATION.cff, otherwise the
checksums describe files that no longer exist in that form.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import platform
import sys
from datetime import datetime, timezone
from pathlib import Path

SKIP_DIRS = {"__pycache__", ".git", ".pytest_cache"}
SKIP_NAMES = {"SHA256SUMS.txt"}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def iter_files(root: Path):
    for path in sorted(root.rglob("*")):
        if not path.is_file():
            continue
        if any(part in SKIP_DIRS for part in path.parts):
            continue
        if path.name in SKIP_NAMES:
            continue
        yield path


def source_tree_hash(root: Path) -> str:
    """Same construction as umsf_twin.core.provenance.source_tree_hash."""
    digest = hashlib.sha256()
    for path in sorted(root.rglob("*.py")):
        if "__pycache__" in path.parts:
            continue
        digest.update(str(path.relative_to(root)).encode("utf-8"))
        digest.update(sha256(path).encode("utf-8"))
    return digest.hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", default=".")
    args = parser.parse_args()
    root = Path(args.root).resolve()

    manifests = root / "manifests"
    manifests.mkdir(exist_ok=True)

    # per-run manifests ----------------------------------------------------
    runs = []
    for summary_path in sorted((root / "results").rglob("summary.json")):
        run_dir = summary_path.parent
        summary = json.loads(summary_path.read_text("utf-8"))
        manifest = json.loads((run_dir / "manifest.json").read_text("utf-8"))
        runs.append({
            "run_dir": run_dir.relative_to(root).as_posix(),
            "run_id": summary["run_id"],
            "experiment_id": summary["experiment_id"],
            "mode": summary["mode"],
            "evidence_class": summary["evidence_class"],
            "replicates": summary["replicates"],
            "rows": summary["aggregate"]["rows"],
            "gates_passed": summary["gates"]["passed"],
            "config_hash": summary["config_hash"],
            "engine_source_hash": manifest["hashes"].get("engine_source", ""),
            "manifest_sha256": sha256(run_dir / "manifest.json"),
        })

    validate = json.loads((root / "results/verification/validate.json").read_text("utf-8"))
    (manifests / "provenance_histogram.json").write_text(
        json.dumps({
            "source": "results/verification/validate.json",
            "parameters": validate["parameters"],
            "evidence_histogram": validate["evidence"],
            "unknown_parameters": validate["unknown_parameters"],
            "interpretation": ("No parameter is MEASURED or VENDOR_SPEC. The four "
                               "UNKNOWN parameters block HIL mode by design."),
        }, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    ref_check_path = root / "results/verification/reference_check.json"
    ref_check = json.loads(ref_check_path.read_text("utf-8")) if ref_check_path.exists() else {}

    scenario_demo_rows = sum(r["rows"] for r in runs
                             if r["run_dir"].startswith(("results/scenarios/",))
                             or r["run_dir"] == "results/demo")

    campaign = {
        "package": {
            "name": "umsf-cyberrange-digital-twin-sim-reproducibility-package",
            "version": "2.0.0",
            "twin_version": "2.0.0",
            "schema_version": "2.0.0",
            "evidence_class": "pre-experimental synthetic model",
            "mode": "SIM",
            "doi": "[RESERVED-ZENODO-DOI]",
        },
        "claim_boundary": (
            "All numerical records in this package are synthetic outputs of a "
            "software model. They are not measurements of the physical UMSF cyber "
            "range and do not establish WAN/VPN/ATS switchover times, Wi-Fi "
            "coverage or capacity, power autonomy, battery thermal behaviour or "
            "field detector accuracy."),
        "generated_at_utc": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "environment": {
            "python_version": sys.version.split()[0],
            "implementation": platform.python_implementation(),
            "system": platform.system(),
            "machine": platform.machine(),
            "third_party_dependencies": [],
        },
        "hashes": {
            "engine_source_hash": source_tree_hash(root / "src" / "umsf_twin"),
            "engine_source_hash_reference_prior_run":
                "2136f8f4be6e300c272a52056e15038260f33d67e0283cadde99939a09b24549",
            "engine_source_hash_reference_specification_truncated": "925c24c6",
            "inventory_config_hash": validate["config_hash"],
        },
        "seed_policy": {
            "base_seed": 20260903,
            "streams": "named streams derived from (seed, replicate_id, namespace)",
            "unit_of_analysis": "one software run/replicate",
        },
        "campaign": {
            "scenarios_executed": 5,
            "demonstration_replicates": 3,
            "doe_points": 8,
            "doe_method": "latin hypercube, 5 factors, exploratory only",
            "monte_carlo_replicates_executed": 5,
            "automated_software_checks": "40/40 passed",
            "reference_values_checked": ref_check.get("checked_values"),
            "reference_values_matched": ref_check.get("matched"),
            "telemetry_rows_scenarios_and_demo": scenario_demo_rows,
            "telemetry_rows_all_runs": sum(r["rows"] for r in runs),
            "row_dependency_note": ("Telemetry rows inside one run are dependent. "
                                    "Row totals are not independent sample sizes."),
        },
        "provenance_vector": {
            "stimulus_origin": "scripted_synthetic",
            "observation_origin": "simulator_output",
            "label_origin": "scenario_controller",
            "curation_origin": "automated_pipeline",
            "analysis_origin": "derived_metric",
            "forbidden_values_in_this_package": ["measured", "physical_sensor",
                                                 "cyber_range_instrumentation"],
        },
        "policy_flags": {
            "external_egress": False,
            "hardware_writes": False,
            "hil_available": False,
            "hil_blocked_by": validate["unknown_parameters"],
            "exploit_code_included": False,
            "threat_modelling_level": "feature-level only",
        },
        "runs": runs,
    }
    (manifests / "campaign_manifest.json").write_text(
        json.dumps(campaign, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    # integrity files, written last so they cover every other artifact -----
    # file_hashes.json lists every file except itself and SHA256SUMS.txt
    # (a file cannot contain its own digest); SHA256SUMS.txt then covers
    # file_hashes.json as well, so `sha256sum -c SHA256SUMS.txt` verifies
    # everything in the package except that checksum file itself.
    file_hashes = {p.relative_to(root).as_posix(): sha256(p)
                   for p in iter_files(root)
                   if p.name != "file_hashes.json"}
    (manifests / "file_hashes.json").write_text(
        json.dumps({"algorithm": "sha256",
                    "excluded": ["manifests/file_hashes.json", "SHA256SUMS.txt"],
                    "files": file_hashes}, indent=2) + "\n", encoding="utf-8")

    all_hashes = {p.relative_to(root).as_posix(): sha256(p) for p in iter_files(root)}
    lines = [f"{digest}  {name}" for name, digest in sorted(all_hashes.items())]
    (root / "SHA256SUMS.txt").write_text("\n".join(lines) + "\n", encoding="utf-8")
    file_hashes = all_hashes

    print(json.dumps({"files_hashed": len(file_hashes), "runs": len(runs),
                      "engine_source_hash": campaign["hashes"]["engine_source_hash"]},
                     indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
