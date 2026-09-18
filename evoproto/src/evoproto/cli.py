"""Command-line entry point: ``evoproto <command>``.

Commands
--------
``dryrun``
    Run the synthetic dry run of Section 7.7 and write ``results.json``,
    ``cells.csv`` and a Table 7-style summary.
``figures``
    Regenerate every figure of the article from code.
``demo``
    Walk the whole pipeline once - knowledge graph, phylogenetic tests, analog
    scoring, search, gate - and print the decision with its traceability chain.
``verify-dois``
    Check every DOI in the reference list against CrossRef (needs network).
``env``
    Print the environment record used in the reproducibility appendix.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Sequence


def _cmd_dryrun(args: argparse.Namespace) -> int:
    from evoproto.experiment import run_protocol

    result = run_protocol(
        replicates=args.replicates,
        population=args.population,
        generations=args.generations,
    )
    directory = result.save(args.output)
    print("# Dry run of the protocol on task T1 (SYNTHETIC; pipeline validation only)")
    print(f"# replicates={args.replicates} population={args.population} "
          f"generations={args.generations}")
    print(f"{'arm':<4}{'FSR':>16}{'HV':>16}{'D':>16}{'ITS':>16}")
    for arm, row in result.table().items():
        print(f"{arm:<4}{row['FSR']:>16}{row['HV']:>16}{row['D']:>16}{row['ITS']:>16}")
    print()
    print(f"{'contrast':<10}{'metric':<7}{'p':>10}{'p_holm':>10}{'delta':>8}  magnitude")
    for row in result.statistics["T1"]:
        print(f"{row['contrast']:<10}{row['metric']:<7}{row['p_value']:>10.4f}"
              f"{row['p_holm']:>10.4f}{row['cliffs_delta']['delta']:>8.2f}"
              f"  {row['cliffs_delta']['magnitude']}")
    print(f"\nwritten to {directory}")
    return 0


def _cmd_figures(args: argparse.Namespace) -> int:
    from evoproto.figures import render_all

    paths = render_all(args.output, names=args.only or None)
    for path in paths:
        print(path)
    return 0


def _cmd_demo(args: argparse.Namespace) -> int:
    import numpy as np

    from evoproto.design import BracketSpec, bounds_array, evaluate_population
    from evoproto.gate import decide
    from evoproto.kg import demo_graph
    print("[1] knowledge graph")
    graph = demo_graph()
    summary = graph.summary()
    print("    nodes:", {k: v for k, v in summary["nodes"].items() if v})
    print("    edges:", {k: v for k, v in summary["edges"].items() if v})
    origins = graph.independent_origins("mech:sandwich_cellular_stiffening")
    print(f"    independent origins of the mechanism: N_conv = {origins:.0f}")

    print("[2] traceability chain (Eq. 4)")
    chain = graph.evidence_chain("par:flexural_rigidity_per_mass")[0]
    for link in chain.links:
        print(f"    {link.edge_type.value:<12} {link.tail} -> {link.head}"
              f"  s={link.support:.2f}  {link.provenance.tag.value}")

    print("[3] analog scoring (Eq. 8)")
    from evoproto.retrieval import AnalogCandidate, score_analog

    candidate = AnalogCandidate(
        identifier="avian_long_bone",
        taxon="Aves",
        trait="trait:strutted_cortical_bone",
        mechanism="mech:sandwich_cellular_stiffening",
        functional_match=0.82,
        mechanism_evidence=chain.measured_fraction,
        n_independent_origins=origins,
        length_ratio=3.0,
    )
    scored = score_analog(candidate)
    print(f"    S = {scored['S']:.3f}  (F={scored['F']:.2f}, M={scored['M']:.2f}, "
          f"U={scored['U']:.2f}, dominant {scored['dominant_uncertainty']})")

    print("[4] constrained search (Algorithm 1)")
    from evoproto.data import stable_seed
    from evoproto.design import analog_prior_sampler as prior
    from evoproto.optimize import constrained_search, normalized_hypervolume

    spec = BracketSpec()
    lower, upper = bounds_array(spec)

    def evaluator(x):
        f, g, _ = evaluate_population(x, spec)
        return f, g

    result = constrained_search(evaluator, prior(spec), lower, upper,
                                population=40, generations=25,
                                seed=stable_seed("T1", "C", 0), arm="C")
    pareto_x, pareto_f = result.pareto()
    reference = np.array([spec.mass_max, spec.delta_max])
    print(f"    feasible fraction {np.mean(result.feasible):.2f}, "
          f"|Pareto| = {len(pareto_x)}, "
          f"HV = {normalized_hypervolume(pareto_f, reference):.3f}")
    if len(pareto_x):
        best = pareto_x[int(np.argmin(pareto_f[:, 0]))]
        print(f"    lightest feasible design: b={best[0]*1e3:.1f} mm, h={best[1]*1e3:.1f} mm, "
              f"t={best[2]*1e3:.2f} mm, rho={best[3]:.2f}  "
              f"({np.min(pareto_f[:, 0])*1e3:.1f} g)")

    print("[5] evidence gate (Algorithm 2)")
    from evoproto.retrieval import transfer_uncertainty

    uncertainty = transfer_uncertainty(3.0, "hierarchical_composite", "monolithic_alloy",
                                       "cyclic", "intermittent_inertial")
    gate = decide(True, chain.supports, uncertainty, chain.reconstructed, origins, chain=chain)
    print(f"    decision: {gate.decision.value} - {gate.reason}")
    print(f"    E = {gate.evidence:.3f}, U = {gate.transfer_uncertainty:.3f}")
    print(f"    next step: {gate.report.get('next_step')}")
    print("\nAll numbers above are SYNTHETIC or MODELED; none is an empirical result.")
    return 0


def _cmd_verify_dois(args: argparse.Namespace) -> int:
    from evoproto.tools.verify_dois import main as verify_main

    return verify_main(["--references", args.references] + (["--offline"] if args.offline else []))


def _cmd_env(args: argparse.Namespace) -> int:
    from evoproto.experiment import environment_record

    print(json.dumps(environment_record(), indent=2, sort_keys=True))
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="evoproto",
        description="Reference implementation of the evolution-informed design framework.",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("dryrun", help="run the synthetic protocol dry run (Section 7.7)")
    p.add_argument("--replicates", type=int, default=10)
    p.add_argument("--population", type=int, default=40)
    p.add_argument("--generations", type=int, default=25)
    p.add_argument("--output", default="results/dry_run")
    p.set_defaults(func=_cmd_dryrun)

    p = sub.add_parser("figures", help="regenerate the figures of the article")
    p.add_argument("--output", default="figures")
    p.add_argument("--only", nargs="*", help="figure names, e.g. fig3 fig7")
    p.set_defaults(func=_cmd_figures)

    p = sub.add_parser("demo", help="walk the pipeline once and print the decision")
    p.set_defaults(func=_cmd_demo)

    p = sub.add_parser("verify-dois", help="check every DOI of the reference list")
    p.add_argument("--references", default="docs/references/references.json")
    p.add_argument("--offline", action="store_true", help="validate syntax only")
    p.set_defaults(func=_cmd_verify_dois)

    p = sub.add_parser("env", help="print the environment record")
    p.set_defaults(func=_cmd_env)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(list(argv) if argv is not None else None)
    return int(args.func(args))


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
