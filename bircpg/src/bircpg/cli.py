"""Command line entry point: ``python -m bircpg <command>``.

Commands
--------
``section6``   Reproduce Table 2, the Equation (6) identity and Equation (15).
``level1``     Run the exact verification sweep of Section 7.1.
``figures``    Regenerate Figure 3 and its table view.
``study``      Run a Level II study (demonstration scale unless ``--full``).
``all``        Everything above at demonstration scale, writing to ``results/``.
"""

from __future__ import annotations

import argparse
import json
import random
import sys
from pathlib import Path
from typing import List, Optional, Sequence

from . import __version__


def _cmd_section6(args) -> int:
    from .section6 import format_table2, summary

    s = summary()
    print("Section 6 -- constructed two-agent example (exact rational arithmetic)")
    print()
    print(format_table2())
    print()
    print(f"Equation (6) identity exact on all {s['deviations_checked']} deviations: "
          f"{s['potential_identity_exact']}")
    print(f"Pure Nash equilibria: {', '.join(s['pure_equilibria'])}")
    print(f"Welfare optimum W* = {s['welfare_optimum']}; "
          f"equilibrium welfare {[str(w) for w in s['equilibrium_welfare']]}")
    print(f"Additive welfare loss at the worse equilibrium: {s['additive_welfare_loss']}")
    print(f"Pure-equilibrium price of anarchy (this instance only): "
          f"{s['price_of_anarchy']} = {float(s['price_of_anarchy']):.4g}")
    print()
    print("Equation (15), stationary law of the active-action subgame at tau = 1:")
    for name, p in s["equation15"].items():
        print(f"  pi{name} = {p:.5f}")
    print()
    print("This is an exact arithmetic illustration, not a simulation and not a")
    print("measurement.  An equilibrium certificate alone does not identify the")
    print("best allocation.")
    return 0


def _cmd_level1(args) -> int:
    from .level1 import level1_sweep

    reports = level1_sweep(
        agent_counts=tuple(args.agents),
        task_counts=tuple(args.tasks),
        seeds=args.seeds,
        chain_tau=args.tau,
    )
    exact = sum(1 for r in reports if r.potential_exact)
    phi_pne = sum(1 for r in reports if r.potential_maximiser_is_pne)
    with_eq = [r for r in reports if r.n_pure_equilibria > 0]
    chains = [r.chain for r in reports if r.chain]
    print(f"Level I sweep: {len(reports)} instances "
          f"({sum(r.profiles for r in reports)} profiles enumerated)")
    print(f"  Equation (6) exact (residual identically zero): {exact}/{len(reports)}")
    print(f"  potential maximiser is a pure NE:               {phi_pne}/{len(reports)}")
    print(f"  instances with at least one pure NE:            {len(with_eq)}/{len(reports)}")
    if chains:
        print(f"  Markov chains checked: {len(chains)}")
        print(f"    max row-sum residual        {max(c['row_sum'] for c in chains):.3e}")
        print(f"    max detailed-balance residual {max(c['detailed_balance'] for c in chains):.3e}")
        print(f"    max stationary residual       {max(c['stationary'] for c in chains):.3e}")
        print(f"    Corollary 2 bound satisfied:  "
              f"{sum(1 for c in chains if c['satisfied'])}/{len(chains)}")
    losses = [float(r.additive_welfare_loss) for r in with_eq if r.additive_welfare_loss is not None]
    if losses:
        print(f"  additive welfare loss at the worst pure NE: "
              f"mean {sum(losses)/len(losses):.4f}, max {max(losses):.4f}")
    print()
    print("A stationary-law check is not a finite-time convergence study; the two")
    print("are reported separately (Section 7.1).")
    if args.out:
        rows = [
            {
                "label": r.label,
                "n_agents": r.n_agents,
                "n_tasks": r.n_tasks,
                "profiles": r.profiles,
                "potential_exact": r.potential_exact,
                "potential_residual": str(r.potential_residual),
                "n_pure_equilibria": r.n_pure_equilibria,
                "welfare_optimum": str(r.welfare_optimum),
                "worst_equilibrium_welfare": str(r.worst_equilibrium_welfare),
                "additive_welfare_loss": str(r.additive_welfare_loss),
                "price_of_anarchy": str(r.price_of_anarchy),
            }
            for r in reports
        ]
        path = Path(args.out)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(rows, indent=2))
        print(f"wrote {path}")
    return 0


def _cmd_figures(args) -> int:
    from .figures import figure3, write_figure_data

    out = Path(args.out)
    written = write_figure_data(out)
    try:
        figure3(out / "figure3.png", theme="light", dpi=args.dpi)
        figure3(out / "figure3.pdf", theme="light", dpi=args.dpi)
        figure3(out / "figure3_dark.png", theme="dark", dpi=args.dpi)
    except ImportError as exc:
        print(f"table view written, figure skipped: {exc}", file=sys.stderr)
        for key, path in written.items():
            print(f"  {key}: {path}")
        return 0
    for key, path in written.items():
        print(f"  {key}: {path}")
    print(f"  figure3: {out / 'figure3.png'} (and .pdf, and a dark variant)")
    return 0


def _cmd_study(args) -> int:
    from .study import (
        PRIMARY_OUTCOMES,
        demonstration_design,
        paired_comparison,
        preregistered_design,
        run_study,
        write_endpoints_csv,
    )

    design = preregistered_design() if args.full else demonstration_design()
    if args.epochs:
        design.epochs = args.epochs
    if args.seeds:
        design.seeds = args.seeds
    scale = "preregistered (Section 7.2)" if args.full else "demonstration"
    print(f"Level II study at {scale} scale: "
          f"{design.runs_per_method} runs per method, {design.epochs} epochs each")
    if not args.full:
        print("This is NOT the preregistered design and supports no confirmatory claim.")

    def progress(done: int, total: int) -> None:
        if done % max(1, total // 20) == 0 or done == total:
            print(f"  {done}/{total} runs", end="\r", file=sys.stderr)

    results = run_study(design, progress=progress)
    print()
    out = Path(args.out) / "level2_endpoints.csv"
    write_endpoints_csv(results, out, gap_tolerance=design.gap_tolerance)
    print(f"wrote {out} ({len(results)} runs)")
    rng = random.Random(args.seed)
    print()
    print("Paired bootstrap over complete runs (10,000 resamples, 95% interval).")
    print("Pairing is on identical environmental seeds; censored pairs are dropped.")
    for hypothesis, spec in PRIMARY_OUTCOMES.items():
        if hypothesis == "H3":
            continue  # H3 needs a controller-by-coordination factorial, not run here
        try:
            result = paired_comparison(
                results,
                "proposed-logit",
                "B2-uniform-logit",
                spec["outcome"],
                gap_tolerance=design.gap_tolerance,
                rng=rng,
            )
        except ValueError as exc:
            print(f"  {hypothesis}: not estimable -- {exc}")
            continue
        print(f"  {hypothesis} ({spec['outcome']}, {spec['direction']}): "
              f"mean diff {result.mean_difference:+.4g} "
              f"[{result.ci_low:+.4g}, {result.ci_high:+.4g}], "
              f"n = {result.n_pairs}, censored {result.censored_pairs}")
        if result.ci_low == result.ci_high == 0.0:
            print("       every pair is identical: this endpoint does not discriminate at")
            print("       this scale, which is a property of the run, not a null result.")
        if result.censored_pairs > result.n_pairs:
            print("       more pairs were censored than analysed; the interval describes")
            print("       the runs that converged, not the method overall.")
    print()
    print("H3 requires a controller-by-coordination factorial comparison on")
    print("measured energy (Level III) and is not estimated here.")
    return 0


def _cmd_all(args) -> int:
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    namespace = argparse.Namespace
    _cmd_section6(namespace())
    print("\n" + "=" * 72 + "\n")
    _cmd_level1(namespace(agents=[2, 3, 4], tasks=[2, 3], seeds=10, tau=0.5,
                          out=str(out / "level1_reports.json")))
    print("\n" + "=" * 72 + "\n")
    _cmd_figures(namespace(out=str(out), dpi=200))
    print("\n" + "=" * 72 + "\n")
    _cmd_study(namespace(full=False, epochs=30, seeds=5, out=str(out), seed=0))
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="bircpg",
        description="Reference implementation of a bio-inspired resource-constrained "
                    "potential game for multi-agent task allocation.",
    )
    parser.add_argument("--version", action="version", version=f"bircpg {__version__}")
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("section6", help="reproduce Table 2 and Equation (15) exactly")
    p.set_defaults(func=_cmd_section6)

    p = sub.add_parser("level1", help="exact verification sweep (Section 7.1)")
    p.add_argument("--agents", type=int, nargs="+", default=[2, 3, 4])
    p.add_argument("--tasks", type=int, nargs="+", default=[2, 3])
    p.add_argument("--seeds", type=int, default=30)
    p.add_argument("--tau", type=float, default=0.5, help="temperature for the chain checks")
    p.add_argument("--out", default="", help="optional JSON report path")
    p.set_defaults(func=_cmd_level1)

    p = sub.add_parser("figures", help="regenerate Figure 3 and its table view")
    p.add_argument("--out", default="results")
    p.add_argument("--dpi", type=int, default=300)
    p.set_defaults(func=_cmd_figures)

    p = sub.add_parser("study", help="run a Level II study (Sections 7.2-7.5)")
    p.add_argument("--full", action="store_true", help="run the preregistered design")
    p.add_argument("--epochs", type=int, default=0)
    p.add_argument("--seeds", type=int, default=0)
    p.add_argument("--out", default="results")
    p.add_argument("--seed", type=int, default=0, help="bootstrap RNG seed")
    p.set_defaults(func=_cmd_study)

    p = sub.add_parser("all", help="everything at demonstration scale")
    p.add_argument("--out", default="results")
    p.set_defaults(func=_cmd_all)
    return parser


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
