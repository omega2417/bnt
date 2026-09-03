"""Command line interface of the twin.

Subcommands mirror the workflow of section 18: ``validate`` an inventory,
``run`` a scenario, ``doe`` a factor sweep, ``mc`` a Monte Carlo campaign,
``gates`` a data-quality check of an existing run, ``report`` a run write-up,
``calibrate`` against measured series and ``verify`` the determinism of the
engine.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from . import __version__
from .core.provenance import canonical_hash
from .core.safety import SafetyPolicy
from .experiment.doe import Factor, design_matrix, randomize_blocks, to_overrides
from .experiment.montecarlo import run_monte_carlo
from .experiment.report import write_report
from .experiment.runner import run_experiment, run_replicate
from .experiment.scenario import load_scenario
from .pipelines.validation import DEFAULT_GATES, run_gates

__all__ = ["main", "build_parser"]


def _load_policy(path: str | None, mode: str) -> SafetyPolicy:
    if path:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
        policy = SafetyPolicy.from_dict(data)
        policy.mode = mode or policy.mode
    else:
        policy = SafetyPolicy(mode=mode)
    policy.check_mode()
    return policy


def cmd_validate(args: argparse.Namespace) -> int:
    scenario = load_scenario(args.config, _load_policy(args.policy, args.mode),
                             strict_invariants=not args.allow_invariant_drift)
    print(json.dumps({
        "experiment_id": scenario.experiment_id,
        "config_hash": scenario.config_hash,
        "events": len(scenario.events),
        "parameters": len(scenario.registry),
        "evidence": scenario.registry.evidence_histogram(),
        "unknown_parameters": scenario.registry.unknowns(),
        "invariant_notes": list(scenario.invariant_notes),
    }, indent=2, ensure_ascii=False))
    return 0


def cmd_run(args: argparse.Namespace) -> int:
    scenario = load_scenario(args.config, _load_policy(args.policy, args.mode),
                             strict_invariants=not args.allow_invariant_drift)
    result = run_experiment(scenario, args.output, replicates=args.replicates,
                            run_id=args.run_id)
    if args.report:
        write_report(result["run_dir"])
    print(json.dumps({"run_dir": result["run_dir"],
                      "gates_passed": result["summary"]["gates"]["passed"],
                      "failed_gates": result["summary"]["gates"]["failed_blocking"],
                      "rows": result["summary"]["aggregate"]["rows"]},
                     indent=2, ensure_ascii=False))
    return 0 if result["summary"]["gates"]["passed"] else 2


def cmd_doe(args: argparse.Namespace) -> int:
    factors = [Factor(**item) for item in json.loads(Path(args.factors).read_text("utf-8"))]
    design = design_matrix(factors, args.count, args.method, args.seed)
    design = randomize_blocks(design, args.block_size, args.seed)
    results = []
    for index, setting in enumerate(design):
        scenario = load_scenario(args.config, _load_policy(args.policy, args.mode),
                                 strict_invariants=not args.allow_invariant_drift,
                                 overrides=to_overrides(setting))
        outcome = run_experiment(scenario, args.output, replicates=args.replicates,
                                 run_id=f"{args.run_id}-{index:03d}")
        results.append({"setting": setting, "run_dir": outcome["run_dir"],
                        "summary": outcome["summary"]["aggregate"]})
    Path(args.output, f"{args.run_id}-design.json").write_text(
        json.dumps(results, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps({"runs": len(results), "design_hash": canonical_hash(design)},
                     indent=2))
    return 0


def cmd_mc(args: argparse.Namespace) -> int:
    scenario = load_scenario(args.config, _load_policy(args.policy, args.mode),
                             strict_invariants=not args.allow_invariant_drift)
    result = run_monte_carlo(scenario, args.metric, max_replicates=args.replicates,
                             target_half_width=args.half_width, run_id=args.run_id)
    print(json.dumps(result.to_dict(), indent=2, ensure_ascii=False))
    return 0


def cmd_gates(args: argparse.Namespace) -> int:
    import csv

    with Path(args.telemetry).open(encoding="utf-8") as handle:
        rows: list[dict[str, Any]] = list(csv.DictReader(handle))
    verdict = run_gates(rows, DEFAULT_GATES)
    print(json.dumps(verdict, indent=2, ensure_ascii=False))
    return 0 if verdict["passed"] else 2


def cmd_report(args: argparse.Namespace) -> int:
    path = write_report(args.run_dir)
    print(str(path))
    return 0


def cmd_verify(args: argparse.Namespace) -> int:
    """Two identical replicates must produce byte-identical artifacts."""

    scenario = load_scenario(args.config, _load_policy(args.policy, args.mode),
                             strict_invariants=not args.allow_invariant_drift)
    first = run_replicate(scenario, 0, "verify")
    second = run_replicate(scenario, 0, "verify")
    identical = canonical_hash(first["rows"]) == canonical_hash(second["rows"])
    other = run_replicate(scenario, 1, "verify")
    differs = canonical_hash(first["rows"]) != canonical_hash(other["rows"])
    print(json.dumps({"deterministic": identical,
                      "replicates_differ": differs,
                      "rows": len(first["rows"])}, indent=2))
    return 0 if identical and differs else 3


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="umsf-twin",
        description="UMSF cyber-range digital twin (synthetic, pre-experimental)")
    parser.add_argument("--version", action="version", version=__version__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    def common(sub: argparse.ArgumentParser) -> None:
        sub.add_argument("--config", required=True, help="scenario/inventory JSON")
        sub.add_argument("--policy", help="safety policy JSON")
        sub.add_argument("--mode", default="SIM", choices=("SIM", "EMU", "REPLAY", "HIL"))
        sub.add_argument("--allow-invariant-drift", action="store_true",
                         help="report inventory deviations instead of refusing to run")

    validate = subparsers.add_parser("validate", help="validate an inventory/scenario")
    common(validate)
    validate.set_defaults(func=cmd_validate)

    run = subparsers.add_parser("run", help="run one experiment")
    common(run)
    run.add_argument("--output", default="runs")
    run.add_argument("--replicates", type=int, default=1)
    run.add_argument("--run-id")
    run.add_argument("--report", action="store_true")
    run.set_defaults(func=cmd_run)

    doe = subparsers.add_parser("doe", help="run a factor sweep")
    common(doe)
    doe.add_argument("--factors", required=True)
    doe.add_argument("--output", default="runs")
    doe.add_argument("--count", type=int, default=8)
    doe.add_argument("--method", default="lhs",
                     choices=("lhs", "sobol", "full", "fractional"))
    doe.add_argument("--block-size", type=int, default=4)
    doe.add_argument("--seed", type=int, default=0)
    doe.add_argument("--replicates", type=int, default=1)
    doe.add_argument("--run-id", default="doe")
    doe.set_defaults(func=cmd_doe)

    mc = subparsers.add_parser("mc", help="Monte Carlo with sequential stopping")
    common(mc)
    mc.add_argument("--metric", default="network.site_a.rtt_p95_ms")
    mc.add_argument("--replicates", type=int, default=20)
    mc.add_argument("--half-width", type=float)
    mc.add_argument("--run-id", default="mc")
    mc.set_defaults(func=cmd_mc)

    gates = subparsers.add_parser("gates", help="check an existing telemetry.csv")
    gates.add_argument("--telemetry", required=True)
    gates.set_defaults(func=cmd_gates)

    report = subparsers.add_parser("report", help="render report.md for a run")
    report.add_argument("--run-dir", required=True)
    report.set_defaults(func=cmd_report)

    verify = subparsers.add_parser("verify", help="check determinism and seed separation")
    common(verify)
    verify.set_defaults(func=cmd_verify)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
