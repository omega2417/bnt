"""Command-line entry point: ``python -m alp <command>``.

The pipeline is one command per protocol stage, plus ``pipeline`` which
runs them in order.  Every stage writes its outputs and hashes them, so
any stage can be re-run and verified independently.
"""

from __future__ import annotations

import argparse
import json
import shutil
import sys
from pathlib import Path

import pandas as pd

from . import PROVENANCE_SIMULATED, __version__
from .config import DEFAULT_PROFILE, MASTER_SEED, PROFILES, get_profile

DEFAULT_DATA = Path("data/raw")
DEFAULT_RESULTS = Path("results")


# --------------------------------------------------------------------------
# Stages
# --------------------------------------------------------------------------

def cmd_schedule(args) -> int:
    from .schedule import write_schedule

    path = write_schedule(args.profile, Path(args.out), seed=args.seed)
    profile = get_profile(args.profile)
    print(f"schedule: {profile.n_runs} runs -> {path}")
    return 0


def cmd_traces(args) -> int:
    from .traces import build_all_traces

    profile = get_profile(args.profile)
    out_dir = Path(args.out)
    registry = build_all_traces(profile, out_dir if args.write_traces else None)
    registry_path = out_dir / "trace_registry.csv"
    registry_path.parent.mkdir(parents=True, exist_ok=True)
    registry.to_csv(registry_path, index=False, lineterminator="\n")
    print(f"traces: {len(registry)} immutable traces -> {registry_path}")
    return 0


def cmd_simulate(args) -> int:
    from .schedule import build_schedule
    from .simulate import run_campaign

    profile = get_profile(args.profile)
    schedule = build_schedule(profile, seed=args.seed)
    out = Path(args.data)
    if out.exists() and args.clean:
        shutil.rmtree(out)
    print(
        f"simulating campaign '{profile.name}': {profile.n_runs} runs, "
        f"{profile.n_scheduled_tx:,} scheduled transactions"
    )
    index = run_campaign(profile, schedule, out)
    print(f"raw dataset -> {out}  ({len(index)} runs)")
    return 0


def cmd_analyze(args) -> int:
    from . import analyze
    from .config import DATA_REQUIRED_FIELDS
    from .tables import (
        table14_latency_quantiles,
        table15_stability,
        table16_effects,
        table_data_required,
        write_table,
        write_theory_tables,
    )

    data = Path(args.data)
    out = Path(args.results)
    out.mkdir(parents=True, exist_ok=True)
    provenance = analyze.dataset_provenance(data)
    print(f"dataset provenance: {provenance}")

    summary = analyze.summarize_dataset(data)
    stability = analyze.classify_stability(summary)
    cells = analyze.cell_stability(stability)
    effects = analyze.holm_correction(analyze.all_effects(summary))
    reach = analyze.max_sustainable_load_both(cells)
    best = analyze.select_best_static(cells, stability)
    precision = analyze.precision_check(effects)

    for frame, name in [
        (summary, "run_level_summary"),
        (stability, "run_stability"),
        (cells, "cell_stability"),
        (effects, "paired_effects"),
    ]:
        frame.to_csv(out / f"{name}.csv", index=False, lineterminator="\n",
                     float_format="%.6f")

    write_theory_tables(out, args.profile, provenance)
    write_table(summary, "table_run_level_summary", out, provenance)
    t14 = table14_latency_quantiles(stability)
    t15 = table15_stability(cells)
    t16 = table16_effects(effects)
    write_table(t14, "table14_latency_quantiles", out, provenance)
    write_table(t15, "table15_stability", out, provenance)
    write_table(t16, "table16_effects", out, provenance)
    write_table(reach, "table_max_sustainable_load", out, provenance)
    write_table(best, "table_best_static", out, provenance)
    write_table(precision, "table_precision_check", out, provenance)
    write_table(table_data_required(DATA_REQUIRED_FIELDS), "table_data_required",
                out, "DATA_REQUIRED")

    if not args.no_figures:
        _figures(data, out, provenance, summary, effects, cells, stability)

    if not args.no_report:
        from .report import write_report

        paths = write_report(out, args.profile, provenance, summary, effects,
                             stability, cells, best, reach, t14, t15, t16, precision)
        print(f"report -> {paths['results_en']} / {paths['results_uk']}")
    print(f"analysis -> {out}")
    return 0


def _figures(data, out, provenance, summary, effects, cells, stability) -> None:
    from . import analyze, figures

    fig_dir = Path(out) / "figures"
    figures.draw_protocol_figures(fig_dir)
    figures.fig5_latency_vs_load(summary, fig_dir, provenance)
    figures.fig6_paired_effects(effects, fig_dir, provenance)
    figures.fig9_resource_cost(summary, fig_dir, provenance)
    figures.fig10_convergence(summary, fig_dir, provenance)
    figures.fig11_stability_map(cells, fig_dir, provenance)

    # A representative stratum: the highest load of the first topology.
    topology = summary.topology.iloc[0]
    load = int(summary.load_tps.max())
    picked = summary[(summary.topology == topology) & (summary.load_tps == load)]
    frames = []
    for config, group in picked.groupby("config"):
        run_id = group.sort_values("repeat").run_id.iloc[0]
        path = Path(data) / "tx" / f"{run_id}.jsonl.gz"
        if path.exists():
            rec = analyze.read_run_records(path)
            frames.append(rec[rec.status == "success"])
    if frames:
        figures.fig7_ecdf(pd.concat(frames), fig_dir, provenance, topology, load)

    # Queue depth of the least and most stable run in the same stratum.
    resources = {}
    ranked = stability[stability.load_tps == load].sort_values("queue_slope_tx_per_s")
    for label, row in [("most stable", ranked.iloc[0]), ("least stable", ranked.iloc[-1])]:
        path = Path(data) / "nodes" / f"{row.run_id}_resources.csv"
        if path.exists():
            resources[f"{label}: {row.config} @ {row.load_tps} tx/s"] = pd.read_csv(path)
    if resources:
        figures.fig8_queue_depth(resources, fig_dir, provenance)
    print(f"figures -> {fig_dir}")


def cmd_manifest(args) -> int:
    from .manifest import build

    for root in args.roots:
        root = Path(root)
        if not root.exists():
            print(f"skipping missing {root}")
            continue
        side = build(root, args.profile, args.provenance)
        print(f"manifest: {side['n_files']} files, "
              f"{side['total_bytes'] / 1e6:.1f} MB -> {root}/MANIFEST.sha256")
    return 0


def cmd_verify(args) -> int:
    from .manifest import verify

    ok = True
    for root in args.roots:
        root = Path(root)
        if not (root / "MANIFEST.sha256").exists():
            print(f"no manifest under {root}")
            ok = False
            continue
        report = verify(root)
        status = "OK" if report["ok"] else "FAILED"
        print(f"{status}: {root} ({report['n_present']} files)")
        for key in ("mismatched", "missing", "unexpected"):
            for item in report[key][:20]:
                print(f"  {key}: {item}")
        ok &= report["ok"]
    return 0 if ok else 1


def cmd_reproduce(args) -> int:
    """Regenerate the dataset into a scratch tree and diff the derived tables."""
    from .manifest import compare_trees

    scratch = Path(args.scratch)
    if scratch.exists():
        shutil.rmtree(scratch)
    data2, results2 = scratch / "raw", scratch / "results"

    cmd_schedule(argparse.Namespace(
        profile=args.profile, out=results2 / "randomized_schedule.csv",
        seed=args.seed))
    cmd_traces(argparse.Namespace(
        profile=args.profile, out=results2, write_traces=False))
    sim_args = argparse.Namespace(profile=args.profile, seed=args.seed,
                                  data=data2, clean=True)
    cmd_simulate(sim_args)
    # Figures are skipped (they are rendered bitmaps, not evidence), but the
    # report is regenerated: its hypothesis verdicts are derived data and must
    # reproduce too.
    ana_args = argparse.Namespace(profile=args.profile, data=data2, results=results2,
                                  no_figures=True, no_report=False)
    cmd_analyze(ana_args)

    report = compare_trees(Path(args.results), results2, patterns=("*.csv",))
    print(
        f"reproduction: {len(report['identical'])} identical, "
        f"{len(report['differing'])} differing, "
        f"{len(report['only_in_first'])} only in the committed tree, "
        f"{len(report['only_in_second'])} only in the regenerated tree"
    )
    for key, label in [("differing", "differs"),
                       ("only_in_first", "missing from the regenerated tree"),
                       ("only_in_second", "unexpected in the regenerated tree")]:
        for name in report[key][:20]:
            print(f"  {label}: {name}")
    if args.keep:
        print(f"scratch kept at {scratch}")
    else:
        shutil.rmtree(scratch)
    return 0 if report["ok"] else 1


def cmd_package(args) -> int:
    from .package import build_archive

    path = build_archive(
        root=Path(args.root),
        out_path=Path(args.out),
        include_raw=not args.no_raw,
    )
    size = path.stat().st_size / 1e6
    print(f"archive -> {path} ({size:.1f} MB)")
    return 0


def cmd_info(args) -> int:
    from .model import model_manifest
    from .theory import campaign_arithmetic

    profile = get_profile(args.profile)
    print(json.dumps(profile.as_dict(), indent=2))
    print(campaign_arithmetic(profile).to_string(index=False))
    if args.model:
        print(json.dumps(model_manifest(), indent=2))
    return 0


def cmd_pipeline(args) -> int:
    """Full reproduction: schedule, traces, dataset, analysis, manifests."""
    data, results = Path(args.data), Path(args.results)
    rc = cmd_schedule(argparse.Namespace(
        profile=args.profile, out=results / "randomized_schedule.csv", seed=args.seed))
    rc |= cmd_traces(argparse.Namespace(
        profile=args.profile, out=results, write_traces=args.write_traces))
    if not args.skip_simulation:
        rc |= cmd_simulate(argparse.Namespace(
            profile=args.profile, seed=args.seed, data=data, clean=args.clean))
    rc |= cmd_analyze(argparse.Namespace(
        profile=args.profile, data=data, results=results,
        no_figures=args.no_figures, no_report=False))
    rc |= cmd_manifest(argparse.Namespace(
        roots=[data, results], profile=args.profile,
        provenance=args.provenance))
    return rc


# --------------------------------------------------------------------------
# Parser
# --------------------------------------------------------------------------

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="alp",
        description="Reproducible field experiment on confirmed-state access "
                    "latency in a permissioned Avalanche L1.",
    )
    parser.add_argument("--version", action="version", version=f"alp {__version__}")
    sub = parser.add_subparsers(dest="command", required=True)

    def common(p, with_data=True, with_results=True):
        p.add_argument("--profile", default=DEFAULT_PROFILE, choices=sorted(PROFILES),
                       help="campaign size (default: %(default)s)")
        if with_data:
            p.add_argument("--data", default=str(DEFAULT_DATA),
                           help="raw dataset root (default: %(default)s)")
        if with_results:
            p.add_argument("--results", default=str(DEFAULT_RESULTS),
                           help="analysis output root (default: %(default)s)")

    p = sub.add_parser("info", help="print the campaign arithmetic")
    common(p, with_data=False, with_results=False)
    p.add_argument("--model", action="store_true", help="also print model parameters")
    p.set_defaults(func=cmd_info)

    p = sub.add_parser("schedule", help="write the randomized run schedule")
    common(p, with_data=False, with_results=False)
    p.add_argument("--out", default="results/randomized_schedule.csv")
    p.add_argument("--seed", type=int, default=MASTER_SEED)
    p.set_defaults(func=cmd_schedule)

    p = sub.add_parser("traces", help="build the immutable workload traces")
    common(p, with_data=False, with_results=False)
    p.add_argument("--out", default="results")
    p.add_argument("--write-traces", action="store_true",
                   help="also write every trace file (large)")
    p.set_defaults(func=cmd_traces)

    p = sub.add_parser("simulate", help="produce a reference dataset")
    common(p, with_results=False)
    p.add_argument("--seed", type=int, default=MASTER_SEED)
    p.add_argument("--clean", action="store_true", help="delete the dataset first")
    p.set_defaults(func=cmd_simulate)

    p = sub.add_parser("analyze", help="run the statistical plan and write outputs")
    common(p)
    p.add_argument("--no-figures", action="store_true")
    p.add_argument("--no-report", action="store_true")
    p.set_defaults(func=cmd_analyze)

    p = sub.add_parser("manifest", help="hash a tree and write MANIFEST.sha256")
    p.add_argument("roots", nargs="+")
    p.add_argument("--profile", default=DEFAULT_PROFILE, choices=sorted(PROFILES))
    p.add_argument("--provenance", default=PROVENANCE_SIMULATED)
    p.set_defaults(func=cmd_manifest)

    p = sub.add_parser("verify", help="re-hash a tree and compare to its manifest")
    p.add_argument("roots", nargs="+")
    p.set_defaults(func=cmd_verify)

    p = sub.add_parser("reproduce",
                       help="regenerate everything and diff the derived tables")
    common(p)
    p.add_argument("--seed", type=int, default=MASTER_SEED)
    p.add_argument("--scratch", default="build/reproduce")
    p.add_argument("--keep", action="store_true")
    p.set_defaults(func=cmd_reproduce)

    p = sub.add_parser("package", help="build the Zenodo archive")
    p.add_argument("--root", default=".")
    p.add_argument("--out", default="dist/avalanche-latency-experiment.zip")
    p.add_argument("--no-raw", action="store_true",
                   help="exclude the raw dataset from the archive")
    p.set_defaults(func=cmd_package)

    p = sub.add_parser("pipeline", help="schedule + traces + dataset + analysis")
    common(p)
    p.add_argument("--seed", type=int, default=MASTER_SEED)
    p.add_argument("--clean", action="store_true")
    p.add_argument("--skip-simulation", action="store_true",
                   help="analyse an existing dataset, e.g. real campaign logs")
    p.add_argument("--write-traces", action="store_true")
    p.add_argument("--no-figures", action="store_true")
    p.add_argument("--provenance", default=PROVENANCE_SIMULATED)
    p.set_defaults(func=cmd_pipeline)

    return parser


def main(argv=None) -> int:
    args = build_parser().parse_args(argv)
    return args.func(args)


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
