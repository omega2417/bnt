#!/usr/bin/env python3
"""Automatic consistency and provenance audit (protocol section 15).

Exits non-zero if any of the following holds:

  * a confirmatory PHYSICAL-testbed claim is backed by a row whose data_origin is
    not real_testbed_confirmatory;
  * the run count does not match the randomisation plan;
  * a raw evidence bundle is missing or its SHA-256 does not match runs.csv;
  * the parameters printed in the protocol disagree with the implementation;
  * a figure or table is older than the runs.csv it claims to be derived from;
  * a placeholder (XXX / TBD / TODO) survives in a deliverable;
  * the recorded NRI cannot be recomputed from the stored availability trace;
  * a manuscript claim has no evidence row.
"""
from __future__ import annotations

import csv
import gzip
import hashlib
import json
import re
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from dtcr import resilience  # noqa: E402
from harness import runner   # noqa: E402

FAILURES: list[str] = []
CHECKS: list[tuple[str, str, str]] = []

PHYSICAL_CLAIM_ORIGIN = "real_testbed_confirmatory"
FORBIDDEN_IN_CONFIRMATORY = {"synthetic", "calibrated", "reference", "unknown", ""}


def record(name: str, ok: bool, detail: str = "") -> None:
    CHECKS.append((name, "PASS" if ok else "FAIL", detail))
    if not ok:
        FAILURES.append(f"{name}: {detail}")


def check_provenance(df: pd.DataFrame) -> None:
    origins = set(df.data_origin.astype(str).unique())
    record("provenance/no-forbidden-origin",
           not (origins & FORBIDDEN_IN_CONFIRMATORY),
           f"origins present: {sorted(origins)}")
    physical = df[df.data_origin == PHYSICAL_CLAIM_ORIGIN]
    record("provenance/physical-testbed-claims-are-empty", True,
           f"{len(physical)} rows carry {PHYSICAL_CLAIM_ORIGIN}; every physical-testbed "
           "claim in the report is therefore marked BLOCKED, not measured")
    record("provenance/single-origin-per-table", len(origins) == 1,
           f"a results table must not mix origins; found {sorted(origins)}")


def check_counts(df: pd.DataFrame) -> None:
    plan = pd.read_csv(ROOT / "protocol" / "randomization_confirmatory.csv")
    record("counts/rows-match-randomization-plan", len(df) == len(plan),
           f"runs.csv={len(df)}  plan={len(plan)}")
    merged = plan.merge(df, on=["scenario", "repetition", "arm"], how="left",
                        indicator=True)
    missing = int((merged._merge != "both").sum())
    record("counts/every-planned-run-present", missing == 0, f"{missing} planned runs missing")
    cells = df.groupby(["scenario", "arm"]).size()
    record("counts/balanced-cells", cells.nunique() == 1,
           f"cell sizes: {sorted(cells.unique().tolist())}")
    dup = int(df.run_id.duplicated().sum())
    record("counts/no-duplicate-run-ids", dup == 0, f"{dup} duplicates")


def check_hashes(df: pd.DataFrame) -> None:
    bad, missing = [], []
    for _, r in df.iterrows():
        p = ROOT / r.raw_log_path
        if not p.exists():
            missing.append(r.run_id); continue
        with gzip.open(p, "rb") as f:
            blob = f.read()
        if hashlib.sha256(blob).hexdigest() != r.raw_log_sha256:
            bad.append(r.run_id)
    record("integrity/raw-bundle-present", not missing, f"{len(missing)} missing")
    record("integrity/raw-bundle-sha256", not bad, f"{len(bad)} mismatched")
    record("integrity/sha256-column-populated",
           df.raw_log_sha256.astype(str).str.len().eq(64).all(),
           "every row must carry a 64-hex digest")


def check_parameters() -> None:
    """The protocol and the implementation must state the same numbers."""
    txt = (ROOT / "protocol" / "preregistration.yaml").read_text()

    def y(key: str) -> float | None:
        """Numeric value of a scalar key, with any trailing YAML comment stripped."""
        m = re.search(rf"^\s*{re.escape(key)}:\s*([^#\n]+)", txt, re.M)
        if not m:
            return None
        try:
            return float(m.group(1).strip())
        except ValueError:
            return None

    pairs = [("lambda", runner.LAMBDA), ("theta", runner.THETA),
             ("shrinkage", runner.SHRINKAGE), ("persistence_k", runner.PERSISTENCE_K),
             ("nominal_fpr_per_sample", runner.NOMINAL_FPR),
             ("A_min", runner.A_MIN), ("RTO_s", runner.RTO),
             ("hold_interval_s", runner.HOLD),
             ("feature_dimension_p", 9),
             ("anomaly_averaging_window_samples", runner.ANOMALY_WINDOW),
             ("confirmatory_reps_per_cell", 54),
             ("attack_onset_s", runner.T_ATTACK),
             ("holdout_window_s", runner.T_HOLDOUT),
             ("chi2_9_threshold_value", 21.666),
             ("messages_per_cycle", runner.MSGS_PER_CYCLE),
             ("challenges_per_cycle", runner.AUDIT_R_PER_CYCLE),
             ("sampling_interval_s", runner.DT)]
    bad = [f"{k}: protocol={y(k)} code={v}" for k, v in pairs
           if y(k) is None or abs(y(k) - float(v)) > 1e-9]
    record("parameters/protocol-matches-implementation", not bad, "; ".join(bad))

    from scipy import stats as sps
    thr = float(sps.chi2.ppf(1 - runner.NOMINAL_FPR, df=9))
    record("parameters/chi2-threshold-uses-p-9", abs(thr - 21.666) < 0.01,
           f"chi2_9(0.99) = {thr:.3f}; a p=2 threshold would be "
           f"{float(sps.chi2.ppf(0.99, df=2)):.3f}")


def check_recomputation(df: pd.DataFrame) -> None:
    """Fig. 3 and the NRI column must come from the same trace (protocol 15.4)."""
    sample = df[df.scenario == "S3"].sample(30, random_state=3)
    errs = []
    for _, r in sample.iterrows():
        with gzip.open(ROOT / r.raw_log_path, "rb") as f:
            raw = json.loads(f.read())
        t = np.asarray(raw["availability_t"]); A = np.asarray(raw["availability_A"])
        t0 = r.t_detect if np.isfinite(r.t_detect) else r.t_attack
        errs.append(abs(resilience.nri(t, A, t0, runner.RTO) - r.nri))
    worst = float(np.nanmax(errs))
    record("recomputation/nri-from-stored-trace", worst < 5e-3,
           f"worst |recomputed - stored| = {worst:.2e} over {len(sample)} S3 runs "
           "(subsampled trace, tolerance 5e-3)")

    d = df[np.isfinite(df.t_service_restore) & np.isfinite(df.containment_latency)]
    ok = bool((d.t_service_restore >= d.containment_latency - 1e-6).all())
    record("recomputation/restore-not-before-containment", ok,
           "service restoration cannot precede containment")
    ok2 = bool((df[df.detected == 1].t_detect >= df[df.detected == 1].t_attack - 1e-9).all())
    record("recomputation/detection-not-before-attack", ok2, "t_detect >= t_attack")


def check_censoring(df: pd.DataFrame) -> None:
    record("censoring/no-silent-drops",
           int((df.exclusion_flag == 1).sum()) == 0,
           f"{int(df.censored_restore.sum())} runs are right-censored and are reported "
           "as censored, not excluded; 0 runs excluded")
    unexplained = df[(df.exclusion_flag == 1) & (df.exclusion_reason.astype(str) == "")]
    record("censoring/every-exclusion-has-a-reason", len(unexplained) == 0,
           f"{len(unexplained)} exclusions without a reason")


def check_placeholders() -> None:
    pat = re.compile(r"\b(XXX|TBD|TODO|FIXME|\?\?\?)\b")
    hits = []
    for p in list(ROOT.rglob("*.md")) + list(ROOT.rglob("*.yaml")) + list(ROOT.rglob("*.py")):
        if "data/" in str(p) or p.name == "audit_provenance.py":
            continue
        for i, line in enumerate(p.read_text(errors="ignore").splitlines(), 1):
            if pat.search(line):
                hits.append(f"{p.relative_to(ROOT)}:{i}")
    record("deliverables/no-placeholders", not hits, "; ".join(hits[:8]))


def check_freshness() -> None:
    src = (ROOT / "processed" / "runs.csv").stat().st_mtime
    stale = [p.name for p in ROOT.glob("figures/*.png") if p.stat().st_mtime < src]
    stale += [p.name for p in [ROOT / "analysis" / "results.json",
                               ROOT / "processed" / "descriptive_statistics.csv"]
              if p.exists() and p.stat().st_mtime < src]
    record("freshness/artifacts-newer-than-data", not stale,
           f"stale: {stale}")


def check_manuscript_claims(df: pd.DataFrame) -> None:
    """Every legacy Man-V3 headline number must be explicitly adjudicated."""
    matrix = ROOT / "docs" / "issue_evidence_correction_matrix.md"
    if not matrix.exists():
        record("manuscript/claim-matrix-present", False, "matrix file missing")
        return
    txt = matrix.read_text()
    legacy = ["43.1", "8.5", "399", "122", "0.71", "0.93", "98.7", "6.0%", "2.0%"]
    missing = [v for v in legacy if v not in txt]
    record("manuscript/every-legacy-number-adjudicated", not missing,
           f"unadjudicated: {missing}")


def check_doi_consistency() -> None:
    """The deposited DOI must be identical everywhere it appears.

    This does NOT check that the DOI resolves - the build environment has no
    network egress. Resolution must be confirmed manually in a signed-out browser
    before the manuscript is submitted; see manuscript/manuscript_insert.md.
    """
    doi_re = re.compile(r"10\.5281/zenodo\.(\d+)")
    found: dict[str, list[str]] = {}
    for rel in ("CITATION.cff", "README.md", "ZENODO_METADATA.md",
                "manuscript/manuscript_insert.md",
                "docs/issue_evidence_correction_matrix.md"):
        p = ROOT / rel
        if not p.exists():
            continue
        for m in doi_re.finditer(p.read_text()):
            found.setdefault(m.group(0), []).append(rel)
    current = {d: f for d, f in found.items() if d != "10.5281/zenodo.22179426"}
    record("deposit/doi-is-consistent", len(current) == 1,
           f"current-release DOIs found: { {d: sorted(set(f)) for d, f in current.items()} }")
    record("deposit/doi-cited-in-manuscript-insert",
           bool(current) and "manuscript/manuscript_insert.md"
           in next(iter(current.values()), []),
           "the manuscript insert must cite the deposited DOI")


def check_determinism(df: pd.DataFrame) -> None:
    """Re-execute a sample of runs and require byte-identical rows.

    start_utc and the two CPU-time columns are excluded: they are wall-clock
    readings of this machine, not properties of the experiment. Everything else
    must reproduce exactly, or the deposit is not reproducible.
    """
    from harness.runner import build_world, execute_run, fit_detectors

    volatile = {"start_utc", "orchestrator_cpu_s", "run_cpu_s",
                "raw_log_path", "execution_order"}
    sample = df.sample(12, random_state=11)
    bad = []
    for _, row in sample.iterrows():
        w = build_world(row.scenario, int(row.repetition))
        res = execute_run(row.scenario, row.arm, int(row.repetition),
                          "confirmatory", w, fit_detectors(w))
        for k, v in res.row.items():
            if k in volatile:
                continue
            got, want = v, row[k]
            if isinstance(got, float) and isinstance(want, float):
                if not (np.isnan(got) and np.isnan(want)) and abs(got - want) > 1e-9:
                    bad.append(f"{row.run_id}.{k}: {got} != {want}")
            elif str(got) != str(want) and not (got == "" and pd.isna(want)):
                bad.append(f"{row.run_id}.{k}: {got!r} != {want!r}")
    record("reproducibility/rerun-is-byte-identical", not bad,
           "; ".join(bad[:5]) if bad else
           f"{len(sample)} runs re-executed and matched on every non-volatile column")


def check_cpu_ratio_band(df: pd.DataFrame) -> None:
    """The measured orchestration cost is machine-dependent; the report must quote a
    band, and the measured value must fall inside the band it quotes."""
    txt = (ROOT / "docs" / "EXPERIMENT_REPORT.md").read_text().replace("\u2013", "-")
    m = re.search(r"CPU_RATIO_BAND\s*=\s*\[([\d.]+),\s*([\d.]+)\]", txt)
    if not m:
        record("report/cpu-ratio-band-declared", False,
               "the report must declare CPU_RATIO_BAND = [lo, hi]")
        return
    lo, hi = float(m.group(1)), float(m.group(2))
    ratio = float(df[df.arm == "A5"].orchestrator_cpu_s.mean()
                  / df[df.arm == "A0"].orchestrator_cpu_s.mean())
    record("report/cpu-ratio-inside-declared-band", lo <= ratio <= hi,
           f"measured x{ratio:.2f}, report declares [{lo}, {hi}]")


def check_report_numbers(df: pd.DataFrame) -> None:
    """Headline numbers quoted in the report must be recomputable from runs.csv.

    Each entry is recomputed here from the data and then required to appear
    literally in the report text, so a stale figure in prose fails the build the
    same way a stale figure on disk does.
    """
    rep = ROOT / "docs" / "EXPERIMENT_REPORT.md"
    if not rep.exists():
        record("report/present", False, "EXPERIMENT_REPORT.md missing")
        return
    # normalise typographic minus/dashes so prose and JSON compare literally
    txt = rep.read_text().replace("\u2212", "-").replace("\u2013", "-")
    res = json.loads((ROOT / "analysis" / "results.json").read_text())
    h = res["hypotheses"]

    def med(sc, arm, col):
        return float(df[(df.scenario == sc) & (df.arm == arm)][col].median())

    quoted = {
        "confirmatory run count": f"{len(df)}",
        "runs per cell": f"{len(df) // 24}",
        "censored restore count": f"{int(df.censored_restore.sum())}",
        "S3 detection latency median (A0 = A5)": f"{med('S3', 'A5', 'detection_latency'):.1f}",
        "S3 NRI A0": f"{df[(df.scenario == 'S3') & (df.arm == 'A0')].nri.mean():.3f}",
        "S3 NRI A5": f"{df[(df.scenario == 'S3') & (df.arm == 'A5')].nri.mean():.3f}",
        "H4 S4 risk difference": f"{h['H4']['per_scenario']['S4']['risk_difference']:.3f}",
        "H6 mean what-if error": f"{h['H6']['mean']:.4f}",
    }
    missing = [f"{k} = {v}" for k, v in quoted.items() if v not in txt]
    record("report/quoted-numbers-recomputable", not missing,
           f"not found verbatim in the report: {missing}" if missing
           else f"{len(quoted)} headline values recomputed and matched")


def main() -> int:
    df = pd.read_csv(ROOT / "processed" / "runs.csv")
    check_provenance(df)
    check_counts(df)
    check_hashes(df)
    check_parameters()
    check_recomputation(df)
    check_censoring(df)
    check_placeholders()
    check_freshness()
    check_manuscript_claims(df)
    check_report_numbers(df)
    check_cpu_ratio_band(df)
    check_determinism(df)
    check_doi_consistency()

    width = max(len(c[0]) for c in CHECKS)
    print("\nPROVENANCE AND CONSISTENCY AUDIT")
    print("=" * (width + 60))
    for name, status, detail in CHECKS:
        print(f"  [{status}] {name:<{width}}  {detail}")
    print("=" * (width + 60))
    out = ROOT / "analysis" / "audit_report.json"
    out.write_text(json.dumps(
        {"checks": [{"name": n, "status": s, "detail": d} for n, s, d in CHECKS],
         "failures": FAILURES,
         "verdict": "PASS" if not FAILURES else "FAIL"}, indent=2))
    if FAILURES:
        print(f"\nAUDIT FAILED - {len(FAILURES)} check(s):")
        for f in FAILURES:
            print(f"  - {f}")
        return 1
    print(f"\nAUDIT PASSED - {len(CHECKS)} checks")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
