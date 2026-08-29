"""Command-line driver.

    python -m uavews.cli generate   --out build            # rehearsal corpus
    python -m uavews.cli run        --raw build/raw --out build/package
    python -m uavews.cli figures    --raw build/raw --out build
    python -m uavews.cli plan                              # field-trial sizing only
    python -m uavews.cli all        --out build            # everything, in order

``all`` is the reproducible entry point: from an empty directory it generates the
rehearsal corpus, runs every pipeline stage, writes the deposit-shaped package,
renders every figure, and emits ``report/validation_report.json`` - the single
file from which the manuscript's bracketed placeholders are to be filled.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import pandas as pd

from . import config, pipeline, simulate, trialdesign, viz


def _clean(obj):
    """Replace NaN and infinities with null before serialization.

    ``json.dumps`` emits bare ``NaN`` and ``Infinity`` tokens by default. They
    are not valid JSON, so every strict parser - including the one that builds
    the engineering report - rejects the file. Missing statistics are genuinely
    absent here (a modality with no measurable synchronization error has no
    median), so null is also the correct representation, not merely the
    parseable one.
    """
    import math
    if isinstance(obj, dict):
        return {k: _clean(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_clean(v) for v in obj]
    if isinstance(obj, float) and not math.isfinite(obj):
        return None
    if hasattr(obj, "item") and not isinstance(obj, (str, bytes)):
        try:
            return _clean(obj.item())
        except Exception:
            return obj
    return obj


def _json_default(o):
    if isinstance(o, (pd.DataFrame,)):
        return o.to_dict(orient="records")
    if isinstance(o, (pd.Series,)):
        return o.to_dict()
    if hasattr(o, "item"):
        try:
            return o.item()
        except Exception:
            pass
    return str(o)


def write_report(result, cfg, out_root: Path) -> Path:
    """Emit the machine-readable report the manuscript should be filled from.

    Placeholder names are carried explicitly so that filling the paper is a
    lookup rather than a transcription, and so that a reviewer can trace any
    number in the manuscript back to the run that produced it.
    """
    cov = result.reports["coverage"]
    m = result.metrics
    placeholders = {
        "[[DATASET_VERSION]]": cfg.release["dataset_version"],
        "[[COLLECTION_START]]": cov["collection_start_utc"],
        "[[COLLECTION_END]]": cov["collection_end_utc"],
        "[[N_LOCATIONS]]": cov["n_generalized_locations"],
        "[[N_FLIGHT_EVENTS]]": cov["event_kind_counts"].get("controlled_flight", 0),
        "[[N_CONTROLLED_EVENTS]]": cov["event_kind_counts"].get("controlled_flight", 0),
        "[[N_VERIFIED_EVENTS]]": cov["event_kind_counts"].get("verified_observation", 0),
        "[[N_WEAK_EVENTS]]": cov["event_kind_counts"].get("weak_observation", 0),
        "[[N_NEGATIVE_EVENTS]]": cov["event_kind_counts"].get("negative_control", 0),
        "[[N_OBSERVATIONS]]": m["n_observations"],
        "[[AUDIO_HOURS]]": round(m["audio_hours"], 4),
        "[[N_VISUAL_OBJECTS]]": m["n_visual_objects"],
        "[[SCHEMA PASS RATE]]": round(100 * m["schema_pass_rate"], 3),
        "[[N_SCHEMA_ERRORS]]": m["n_schema_issues"],
        "[[MEDIAN COMPLETENESS]]": round(m["median_completeness"], 4),
        "[[P05 COMPLETENESS]]": round(m["p05_completeness"], 4),
        "[[SYNC MEDIAN]]": round(m["sync_median_ms"], 3),
        "[[SYNC P95]]": round(m["sync_p95_ms"], 3),
        "[[SYNC MAX]]": round(m["sync_max_ms"], 3),
        "[[EXACT DUPLICATE RATE]]": round(100 * m["exact_duplicate_rate"], 3),
        "[[NEAR DUPLICATE RATE]]": round(100 * m["near_duplicate_rate"], 3),
        "[[CROSS-MODAL CONSISTENCY]]": round(100 * m["cross_modal_consistency"], 2),
        "[[CHECKSUM PASS RATE]]": round(100 * m["checksum_pass_rate"], 3),
        "[[DELTA_T]]": cfg.delta_t_s,
        "[[EPSILON_DISTANCE]]": round(cfg.epsilon_m, 4),
        "[[TEMPORAL_GAP]]": f"{cfg['splits']['temporal_gap_days']} d",
        "[[N_ANNOTATORS]]": cfg["annotation"]["n_annotators"],
        "[[PUBLIC_SPATIAL_RESOLUTION]]": f"{cfg.release['public_spatial_resolution_m']} m",
    }
    report = {
        "PROVENANCE_WARNING":
            "Computed from the SYNTHETIC rehearsal corpus. These values "
            "demonstrate that the computation is correct and reproducible. They "
            "are NOT measurements and must not be transcribed into the "
            "manuscript. Re-run this pipeline on the deposited release and use "
            "the values it produces there.",
        "dataset_version": cfg.release["dataset_version"],
        "metrics": result.metrics,
        "coverage": cov,
        "gates": result.gates.to_dict(orient="records"),
        "manuscript_placeholders": placeholders,
        "sync_by_modality": result.reports["sync"].to_dict(orient="records"),
        "completeness_by_table": result.reports["completeness"].to_dict(orient="records"),
        "media_quality": result.reports["media_quality"].to_dict(orient="records"),
        "predicted_vs_achieved": result.reports["predicted_vs_achieved"]
        .to_dict(orient="records"),
        "agreement": result.reports["agreement"].to_dict(orient="records"),
        "split_audit": result.reports["split_audit"].to_dict(orient="records"),
        "k_anonymity": result.reports["k_anonymity"],
        "duplicates": result.reports["duplicates"],
        "integrity": {k: v for k, v in result.reports["integrity"].items()
                      if k != "failures"},
        "campaign_plan": result.reports["campaign_plan"],
    }
    path = Path(out_root) / "report" / "validation_report.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(_clean(report), indent=2, default=_json_default,
                               allow_nan=False), encoding="utf-8")
    return path


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="uavews", description=__doc__)
    ap.add_argument("command", choices=["generate", "run", "figures", "plan", "all"])
    ap.add_argument("--config", default=None)
    ap.add_argument("--raw", default="build/raw")
    ap.add_argument("--out", default="build")
    ap.add_argument("--seed", type=int, default=20250411)
    ap.add_argument("--quiet", action="store_true")
    args = ap.parse_args(argv)

    cfg = config.load(args.config)
    out = Path(args.out)
    verbose = not args.quiet

    if args.command == "plan":
        plan = trialdesign.campaign_plan(cfg)
        print(json.dumps(plan, indent=2))
        print(trialdesign.detectability_table(cfg).to_string(index=False))
        return 0

    if args.command in ("generate", "all"):
        paths = simulate.generate(cfg, out, seed=args.seed)
        if verbose:
            print(f"rehearsal corpus -> {paths['manifest']}")

    raw = out / "raw" if args.command == "all" else Path(args.raw)

    if args.command in ("run", "figures", "all"):
        result = pipeline.run(cfg, raw, out / "package", verbose=verbose)
        report = write_report(result, cfg, out)
        if verbose:
            print(f"\n{result.gates.to_string(index=False)}\n")
            print(f"validation report -> {report}")
        if args.command in ("figures", "all"):
            figs = viz.render_all(result, cfg, out / "figures")
            if verbose:
                print(f"{len(figs)} figures -> {out / 'figures'}")
        failed = result.gates[result.gates["status"] == "FAIL"]
        if len(failed) and verbose:
            print(f"\n{len(failed)} gate(s) failed: "
                  f"{', '.join(failed['gate'])}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
