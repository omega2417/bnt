"""Command-line interface: ``evoproto <command>``.

Commands
--------
``info``         package, mode and the pre-registered constants
``dry-run``      Section 7.7: the protocol on synthetic arms
``case-study``   Section 6: retrieval, search, verification, gate
``ablation``     Section 7.5: arm C with one source of value removed
``figures``      regenerate every figure of the paper
``verify-dois``  CrossRef check of the reference list
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from typing import Any, Dict, Optional, Sequence

from .data import PACKAGE_VERSION, ProvenanceTag
from .gate import GateThresholds, KAPPA_DEFAULT
from .retrieval import RetrievalWeights, TransferWeights


def _dump(payload: Any, path: Optional[str] = None) -> None:
    text = json.dumps(payload, indent=2, default=str)
    if path:
        with open(path, "w", encoding="utf-8") as handle:
            handle.write(text + "\n")
        print(f"written: {path}")
    else:
        print(text)


def _cmd_info(args: argparse.Namespace) -> int:
    from . import design

    payload: Dict[str, Any] = {
        "package": "evoproto",
        "version": PACKAGE_VERSION,
        "mode": "SYNTHETIC (no biological records are bundled; connectors are offline by default)",
        "retrieval_weights_eq8": RetrievalWeights().as_dict(),
        "transfer_weights_eq9": TransferWeights().as_dict(),
        "gate_thresholds_eq14": GateThresholds().as_dict(),
        "convergence_bonus_kappa_eq13": KAPPA_DEFAULT,
        "specification_table6": design.EOAT_BRACKET.as_dict(),
        "seed_derivation": "blake2b over (package version, task id, arm, replicate)",
    }
    _dump(payload, args.out)
    return 0


def _cmd_dry_run(args: argparse.Namespace) -> int:
    from .experiment import dry_run

    result = dry_run(
        replicates=args.replicates,
        population_size=args.population,
        generations=args.generations,
    )
    if args.out:
        _dump(result, args.out)
    else:
        print(f"[{result['tag']}] {result['warning']}")
        print(f"corpus snapshot: {result['snapshot_hash']}\n")
        header = f"{'cell':<8}{'FSR':>16}{'HV':>16}{'D':>16}{'ITS':>16}"
        print(header)
        print("-" * len(header))
        for cell, metrics in sorted(result["summary"].items()):
            row = f"{cell:<8}"
            for metric in ("FSR", "HV", "D", "ITS"):
                row += f"{metrics[metric]['mean']:>10.3f} ± {metrics[metric]['sd']:<4.3f}"
            print(row)
        print("\nstatistical plan (two-sided Wilcoxon, Holm-corrected, Cliff's delta):")
        for row in result["comparisons"]:
            print(
                f"  {row['contrast']:<9} {row['metric']:<4} "
                f"p = {row['p_raw']:.4f}  p_holm = {row['p_holm']:.4f}  "
                f"delta = {row['cliffs_delta']:+.2f} ({row['effect_magnitude']})  "
                f"median diff = {row['median_difference']:+.4f} "
                f"[{row['ci_low']:+.4f}, {row['ci_high']:+.4f}]"
            )
        print(
            f"\npower: n = {result['power']['n_for_d_1.0']} pairs for d = 1.0, "
            f"n = {result['power']['n_for_d_0.8']} for d = 0.8 — {result['power']['note']}"
        )
    return 0


def _cmd_case_study(args: argparse.Namespace) -> int:
    from .casestudy import run_case_study

    result = run_case_study(population_size=args.population, generations=args.generations)
    if args.out:
        _dump(result, args.out)
    else:
        print(f"[{result['tag']}] query: {result['query']}")
        print(f"corpus snapshot: {result['snapshot_hash']}")
        print(
            f"independent origins N_conv = {result['independent_origins']} "
            f"(sampling-weighted {result['independent_origins_weighted']:.3f})\n"
        )
        print("candidate analogs (Eq. 8):")
        for analog in result["analogs"]:
            print(
                f"  {analog['name']:<52} S = {analog['score']:+.3f}  "
                f"F = {analog['F']:.2f}  M = {analog['M']:.2f}  U = {analog['U']:.3f}"
            )
        chain = result["chain"]
        print("\ntraceability chain (Eq. 4):")
        for node, edge, support, provenance in zip(
            chain["nodes"], chain["edges"] + [""], chain["supports"] + [None], chain["provenance"] + [None]
        ):
            if edge:
                print(f"  {node}\n      --{edge} (s = {support:.2f}, {provenance['tag']})-->")
            else:
                print(f"  {node}")
        print("\nprototypes (Section 6.4):")
        for prototype in result["prototypes"]:
            design_vector = prototype["design"]
            gate = prototype["gate"]
            print(
                f"  #{prototype['rank']}  b = {design_vector['b'] * 1000:5.1f} mm  "
                f"h = {design_vector['h'] * 1000:5.1f} mm  t = {design_vector['t'] * 1000:4.2f} mm  "
                f"rho = {design_vector['rho']:.3f}  |  "
                f"m = {prototype['predictions_modeled']['mass_kg'] * 1000:6.1f} g  "
                f"delta = {prototype['predictions_modeled']['deflection_m'] * 1e6:6.1f} um  "
                f"|  E = {gate['E']:.3f}  U = {gate['U']:.3f}  -> {gate['decision']}"
            )
            if gate["report"]:
                print(f"       report: {gate['report']['reason']}")
                print(f"       next:   {gate['report']['suggested_experiment']}")
        print(f"\nabstention rate: {result['abstention_rate']:.2f}")
        print(result["note"])
    return 0


def _cmd_ablation(args: argparse.Namespace) -> int:
    from .experiment import ablation

    _dump(ablation(replicates=args.replicates, population_size=args.population,
                   generations=args.generations), args.out)
    return 0


def _cmd_figures(args: argparse.Namespace) -> int:
    from .figures import generate, generate_all

    paths = [generate(args.name, args.outdir, args.format)] if args.name else generate_all(
        args.outdir, args.format
    )
    for path in paths:
        print(path)
    return 0


def _cmd_verify_dois(args: argparse.Namespace) -> int:
    from .tools.verify_dois import main as verify_main

    argv = ["--references", args.references]
    if args.online:
        argv.append("--online")
    if args.mailto:
        argv += ["--mailto", args.mailto]
    if args.json:
        argv.append("--json")
    return verify_main(argv)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="evoproto", description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--version", action="version", version=f"evoproto {PACKAGE_VERSION}")
    subparsers = parser.add_subparsers(dest="command", required=True)

    info = subparsers.add_parser("info", help="package, mode and pre-registered constants")
    info.add_argument("--out", default=None, help="write JSON to this path")
    info.set_defaults(func=_cmd_info)

    dry = subparsers.add_parser("dry-run", help="Section 7.7: protocol on synthetic arms")
    dry.add_argument("--replicates", type=int, default=10)
    dry.add_argument("--population", type=int, default=40)
    dry.add_argument("--generations", type=int, default=25)
    dry.add_argument("--out", default=None, help="write JSON to this path")
    dry.set_defaults(func=_cmd_dry_run)

    case = subparsers.add_parser("case-study", help="Section 6: the EOAT bracket end to end")
    case.add_argument("--population", type=int, default=40)
    case.add_argument("--generations", type=int, default=25)
    case.add_argument("--out", default=None, help="write JSON to this path")
    case.set_defaults(func=_cmd_case_study)

    abl = subparsers.add_parser("ablation", help="Section 7.5: ablations of arm C")
    abl.add_argument("--replicates", type=int, default=10)
    abl.add_argument("--population", type=int, default=40)
    abl.add_argument("--generations", type=int, default=25)
    abl.add_argument("--out", default=None)
    abl.set_defaults(func=_cmd_ablation)

    figures = subparsers.add_parser("figures", help="regenerate the figures of the paper")
    figures.add_argument("--outdir", default="figures")
    figures.add_argument("--format", default="png", choices=("png", "pdf", "svg"))
    figures.add_argument("--name", default=None, help="one figure instead of all")
    figures.set_defaults(func=_cmd_figures)

    from .tools.verify_dois import DEFAULT_REFERENCES

    dois = subparsers.add_parser("verify-dois", help="CrossRef check of the reference list")
    dois.add_argument("--references", default=DEFAULT_REFERENCES)
    dois.add_argument("--online", action="store_true")
    dois.add_argument("--mailto", default=None)
    dois.add_argument("--json", action="store_true")
    dois.set_defaults(func=_cmd_verify_dois)

    return parser


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return int(args.func(args))
    except BrokenPipeError:
        # the output was piped into something that closed early (`| head`);
        # silence the interpreter's shutdown message and report the usual code
        try:
            sys.stdout.close()
        finally:
            os.dup2(os.open(os.devnull, os.O_WRONLY), sys.stdout.fileno())
        return 141


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
