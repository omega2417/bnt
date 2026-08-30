#!/usr/bin/env python3
"""Check the deposit for internal consistency and submission readiness.

Two classes of check are run.

STRUCTURAL / CONSISTENCY (must pass at all times):
  * every file promised by the README exists;
  * run_level_metrics.csv has the declared design (scenarios x arms x reps);
  * every run references an availability trace that exists and parses;
  * recovery time and NRI recomputed from the traces match the stored values;
  * the aggregates in results/summary.json match the values quoted in the
    manuscript to the precision at which the manuscript prints them.

SUBMISSION READINESS (expected to fail while the data are synthetic):
  * no file carries data_origin = synthetic_reference;
  * the Zenodo DOI placeholder has been replaced in README and CITATION.cff.

Exit status is 0 when the structural checks pass, 1 otherwise.  ``--strict``
additionally requires the submission-readiness checks to pass.

Usage:  python analysis/verify_repository.py --root . [--strict]
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

REQUIRED = [
    "README.md", "LICENSE", "LICENSE-DATA", "CITATION.cff", "PROVENANCE.md",
    "DATA_DICTIONARY.md", "PROTOCOL.md", "THREAT_MODEL.md", "Makefile",
    "data/run_level_metrics.csv", "data/ablation_runs.csv",
    "data/confusion_matrices/integrity_confusion.csv",
    "data/resource_measurements/resource_usage.csv",
    "configs/framework_parameters.yaml",
    "analysis/statistics.py", "analysis/calculate_nri.py",
    "analysis/generate_figures.py", "analysis/simulate_reference_dataset.py",
    "environment/requirements.txt", "environment/software_versions.md",
]

# Values printed in the manuscript, and the tolerance implied by their precision.
MANUSCRIPT_CLAIMS = {
    "detection_latency_baseline_s": (43.1, 0.05),
    "detection_latency_framework_s": (8.5, 0.05),
    "recovery_time_baseline_s": (399.0, 0.5),
    "recovery_time_framework_s": (122.0, 0.5),
    "nri_s3_baseline": (0.71, 0.005),
    "nri_s3_framework": (0.93, 0.005),
    "integrity_accuracy": (0.987, 0.0005),
}

PLACEHOLDER_DOI = "10.5281/zenodo.PLACEHOLDER"


class Report:
    def __init__(self):
        self.structural, self.readiness = [], []

    def add(self, group, ok, name, detail=""):
        group.append({"ok": bool(ok), "check": name, "detail": detail})

    def render(self) -> str:
        lines = []
        for title, group in [("STRUCTURAL / CONSISTENCY", self.structural),
                             ("SUBMISSION READINESS", self.readiness)]:
            lines.append(f"\n{title}")
            lines.append("-" * len(title))
            for c in group:
                mark = "PASS" if c["ok"] else "FAIL"
                lines.append(f"  [{mark}] {c['check']}"
                             + (f"\n         {c['detail']}" if c["detail"] else ""))
        return "\n".join(lines)


def check_files(root: Path, rep: Report):
    missing = [f for f in REQUIRED if not (root / f).exists()]
    rep.add(rep.structural, not missing, f"{len(REQUIRED)} required files present",
            "missing: " + ", ".join(missing) if missing else "")


def check_design(root: Path, rep: Report, runs: pd.DataFrame):
    scen = sorted(runs.scenario.unique())
    arms = sorted(runs.method.unique())
    counts = runs.groupby(["scenario", "method"]).size()
    ok = (scen == ["S1", "S2", "S3", "S4"] and arms == ["baseline", "framework"]
          and counts.nunique() == 1)
    rep.add(rep.structural, ok,
            f"experimental design: {len(scen)} scenarios x {len(arms)} arms "
            f"x {counts.iloc[0]} repetitions = {len(runs)} runs",
            "" if ok else f"unbalanced cells: {counts.to_dict()}")
    cens = int(runs.recovery_censored.sum()) if "recovery_censored" in runs else 0
    rep.add(rep.structural, True, f"censored runs recorded: {cens}",
            "censored runs are reported in the run count and excluded from means")


def check_traces(root: Path, rep: Report, runs: pd.DataFrame):
    missing, unreadable = [], []
    for _, r in runs.iterrows():
        p = root / "data" / r.trace_file
        if not p.exists():
            missing.append(r.run_id)
            continue
        try:
            df = pd.read_csv(p)
            if not {"t_s", "availability"} <= set(df.columns) or df.empty:
                unreadable.append(r.run_id)
        except Exception:
            unreadable.append(r.run_id)
    ok = not missing and not unreadable
    rep.add(rep.structural, ok, f"{len(runs)} availability traces present and parseable",
            "" if ok else f"missing={missing[:5]} unreadable={unreadable[:5]}")


def check_recomputation(root: Path, rep: Report):
    p = root / "results" / "nri_parameters.json"
    if not p.exists():
        rep.add(rep.structural, False, "NRI recomputation available",
                "run `make analysis` first")
        return
    c = json.loads(p.read_text())["consistency_check"]
    ok = c["mismatched_runs"] == 0
    rep.add(rep.structural, ok,
            "recovery time and NRI recomputed from traces match stored values",
            f"max |dNRI| = {c['max_abs_delta_nri']:.2e}, "
            f"max |drecovery| = {c['max_abs_delta_recovery_s']:.2e}, "
            f"mismatched = {c['mismatched_runs']}")


def check_claims(root: Path, rep: Report):
    p = root / "results" / "summary.json"
    if not p.exists():
        rep.add(rep.structural, False, "manuscript claims reproduced",
                "run `make analysis` first")
        return
    s = json.loads(p.read_text())
    actual = {
        "detection_latency_baseline_s": s["detection_latency_s"]["baseline_mean"],
        "detection_latency_framework_s": s["detection_latency_s"]["framework_mean"],
        "recovery_time_baseline_s": s["recovery_time_s"]["baseline_mean"],
        "recovery_time_framework_s": s["recovery_time_s"]["framework_mean"],
        "nri_s3_baseline": s["nri_S3"]["baseline_mean"],
        "nri_s3_framework": s["nri_S3"]["framework_mean"],
        "integrity_accuracy": s["integrity_pooled"]["accuracy"],
    }
    bad = []
    for k, (claim, tol) in MANUSCRIPT_CLAIMS.items():
        if abs(actual[k] - claim) > tol:
            bad.append(f"{k}: manuscript {claim}, data {actual[k]:.4f}")
    rep.add(rep.structural, not bad,
            f"{len(MANUSCRIPT_CLAIMS)} manuscript claims reproduced from data/",
            "; ".join(bad))
    ovh = s["overhead_max_relative_pct_eq17"]
    rep.add(rep.structural, ovh < 6.0,
            f"overhead below the published 6% bound (max {ovh:.2f}%)")


def check_synthetic(root: Path, rep: Report):
    hits = []
    for p in sorted(root.rglob("*.csv")):
        try:
            head = p.open(encoding="utf-8", errors="ignore").read(4096)
        except OSError:
            continue
        if "synthetic_reference" in head:
            hits.append(str(p.relative_to(root)))
    rep.add(rep.readiness, not hits,
            "no file is marked data_origin = synthetic_reference",
            f"{len(hits)} file(s) still synthetic, e.g. {hits[:3]}" if hits else "")


def check_doi(root: Path, rep: Report):
    hits = [f for f in ("README.md", "CITATION.cff", "PROVENANCE.md")
            if (root / f).exists() and PLACEHOLDER_DOI in (root / f).read_text()]
    rep.add(rep.readiness, not hits,
            "Zenodo DOI placeholder replaced with the minted DOI",
            f"placeholder still present in: {', '.join(hits)}" if hits else "")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--root", default=".")
    ap.add_argument("--strict", action="store_true",
                    help="also require the submission-readiness checks to pass")
    args = ap.parse_args()
    root = Path(args.root).resolve()
    rep = Report()

    check_files(root, rep)
    runs_path = root / "data" / "run_level_metrics.csv"
    if runs_path.exists():
        runs = pd.read_csv(runs_path)
        check_design(root, rep, runs)
        check_traces(root, rep, runs)
    else:
        rep.add(rep.structural, False, "run_level_metrics.csv readable")
    check_recomputation(root, rep)
    check_claims(root, rep)
    check_synthetic(root, rep)
    check_doi(root, rep)

    print(rep.render())
    struct_ok = all(c["ok"] for c in rep.structural)
    ready_ok = all(c["ok"] for c in rep.readiness)
    print(f"\nstructural: {'PASS' if struct_ok else 'FAIL'}   "
          f"submission-ready: {'YES' if ready_ok else 'NO'}")
    if not ready_ok:
        print("\nThe deposit is internally consistent but still carries the synthetic\n"
              "reference dataset. See PROVENANCE.md before citing it in a submission.")
    if not struct_ok:
        return 1
    return 1 if (args.strict and not ready_ok) else 0


if __name__ == "__main__":
    raise SystemExit(main())
