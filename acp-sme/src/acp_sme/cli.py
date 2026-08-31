"""Command-line entry point for the ACP-SME reference prototype.

    python -m acp_sme reproduce      # full reproduction package (Tables 6, 7 + figures)
    python -m acp_sme experiment     # primary experiment only (Table 6)
    python -m acp_sme sensitivity    # sensitivity analysis only (Table 7)
    python -m acp_sme demo           # worked end-to-end governance walkthrough
    python -m acp_sme selftest       # selector and guard invariants
    python -m acp_sme params         # dump the parameter packs as JSON
"""

from __future__ import annotations

import argparse
import json
import platform
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, Sequence

from . import __version__

DEFAULT_RESULTS = Path("results")

CLAIMS_BANNER = (
    "ACP-SME v{version} - synthetic model output only.\n"
    "These results verify internal behaviour under encoded assumptions. They do "
    "not demonstrate\nreal-world incident reduction, standards conformity, or "
    "certification readiness.\n"
)


def _banner() -> str:
    return CLAIMS_BANNER.format(version=__version__)


def cmd_experiment(args: argparse.Namespace) -> int:
    from .experiment import (
        format_primary_table,
        run_primary,
        summarise_primary,
        write_daily_coverage_csv,
        write_summary_json,
        write_trace_csv,
    )

    print(_banner())
    print(f"Running primary experiment: 3 archetypes x {args.replicates} replicates ...")
    results = run_primary(replicates=args.replicates)
    summary = summarise_primary(results)
    print()
    print("Table 6. Primary synthetic results")
    print(format_primary_table(summary))

    out = Path(args.output)
    write_trace_csv(results, out / "trace_outcomes.csv")
    write_summary_json(summary, out / "primary_summary.json")
    if args.daily:
        write_daily_coverage_csv(results, out / "daily_coverage.csv")
    print(f"\nWrote trace outcomes and summary to {out}/")
    return 0


def cmd_sensitivity(args: argparse.Namespace) -> int:
    from .experiment import format_sensitivity_table, run_sensitivity, write_sensitivity_csv

    print(_banner())
    print("Running sensitivity analysis: 5 thresholds x 3 budget factors ...")
    rows = run_sensitivity(replicates=args.replicates)
    print()
    print("Table 7. ACP-SME sensitivity")
    print(format_sensitivity_table(rows))
    out = Path(args.output)
    write_sensitivity_csv(rows, out / "sensitivity.csv")
    print(f"\nWrote sensitivity grid to {out}/sensitivity.csv")
    return 0


def cmd_reproduce(args: argparse.Namespace) -> int:
    from .experiment import (
        format_primary_table,
        format_sensitivity_table,
        run_primary,
        run_sensitivity,
        summarise_primary,
        write_daily_coverage_csv,
        write_sensitivity_csv,
        write_summary_json,
        write_trace_csv,
    )

    out = Path(args.output)
    print(_banner())

    print("[1/3] Primary experiment ...")
    results = run_primary(replicates=args.replicates)
    summary = summarise_primary(results)
    print()
    print("Table 6. Primary synthetic results")
    print(format_primary_table(summary))

    print("\n[2/3] Sensitivity analysis ...")
    rows = run_sensitivity()
    print()
    print("Table 7. ACP-SME sensitivity")
    print(format_sensitivity_table(rows))

    write_trace_csv(results, out / "trace_outcomes.csv")
    write_summary_json(summary, out / "primary_summary.json")
    write_sensitivity_csv(rows, out / "sensitivity.csv")
    if args.daily:
        write_daily_coverage_csv(results, out / "daily_coverage.csv")

    environment = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "acp_sme_version": __version__,
        "python": sys.version.split()[0],
        "implementation": platform.python_implementation(),
        "platform": platform.platform(),
    }
    (out / "run_environment.json").write_text(
        json.dumps(environment, indent=2) + "\n", encoding="utf-8"
    )

    print("\n[3/3] Figures ...")
    if args.no_figures:
        print("  skipped (--no-figures)")
    else:
        from .figures import render_all

        for path in render_all(results, rows, out / "figures"):
            print(f"  {path}")

    print(f"\nReproduction package written to {out}/")
    return 0


def cmd_demo(args: argparse.Namespace) -> int:
    from .demo import run_demo

    print(_banner())
    run_demo()
    return 0


def cmd_selftest(args: argparse.Namespace) -> int:
    from .capabilities import dependency_valid_subsets, validate_prerequisites
    from .crosswalk import EDGES, validate_pack
    from .metadata_model import MetadataGuard, MetadataRejected
    from .scenarios import ARCHETYPES
    from .selector import assert_invariants, select
    from .simulator import run_trace

    print(_banner())
    checks = []

    validate_prerequisites()
    checks.append(("capability prerequisite graph is acyclic and complete", True))

    subsets = dependency_valid_subsets()
    checks.append((f"dependency-valid subsets enumerated ({len(subsets)} of 16384)", True))

    validate_pack()
    checks.append((f"crosswalk pack covers all three frameworks ({len(EDGES)} edges)", True))

    ok = True
    for archetype in ARCHETYPES:
        for day in (0, 60, 119):
            selection = select(archetype.demand_at(day), archetype.budget)
            try:
                assert_invariants(selection)
            except AssertionError:
                ok = False
    checks.append(("selector respects budget and prerequisites at every checkpoint", ok))

    guard = MetadataGuard("selftest", b"key")
    blocked = 0
    for record in ({"employee_name": "x"}, {"raw_log": "y"}, {"api_key": "z"}, {"unknown": 1}):
        try:
            guard.accept(record, "test")
        except MetadataRejected:
            blocked += 1
    checks.append((f"metadata guard fails closed on prohibited fields ({blocked}/4)", blocked == 4))

    a = run_trace(ARCHETYPES[0], 0)
    b = run_trace(ARCHETYPES[0], 0)
    same = all(
        a.conditions[c].profiles == b.conditions[c].profiles for c in a.conditions
    )
    checks.append(("repeated runs of the same seed are bit-identical", same))

    print("Self-test")
    for label, passed in checks:
        print(f"  [{'PASS' if passed else 'FAIL'}] {label}")
    return 0 if all(passed for _, passed in checks) else 1


def cmd_params(args: argparse.Namespace) -> int:
    from .capabilities import CAPABILITIES, CAPABILITY_PACK_VERSION
    from .crosswalk import CROSSWALK_PACK_VERSION, coverage_report
    from .detector import RULE_PACK_VERSION
    from .metadata_model import SCHEMA_VERSION, SPECS
    from .scenarios import ARCHETYPES, SCENARIO_PACK_VERSION
    from . import simulator as sim

    payload = {
        "artifact_version": __version__,
        "packs": {
            "capability": CAPABILITY_PACK_VERSION,
            "crosswalk": CROSSWALK_PACK_VERSION,
            "rule": RULE_PACK_VERSION,
            "scenario": SCENARIO_PACK_VERSION,
            "mnmm_schema": SCHEMA_VERSION,
        },
        "capabilities": [
            {
                "code": c.code,
                "name": c.name,
                "cost_units": c.cost,
                "effectiveness": c.effectiveness,
                "prerequisites": list(c.prerequisites),
            }
            for c in CAPABILITIES
        ],
        "archetypes": [
            {
                "key": a.key,
                "label": a.label,
                "staff": a.staff,
                "budget_units": a.budget,
                "principal_exposure": a.exposure,
                "base_demand": {k: v for k, v in a.base_demand.items() if v},
                "events": [
                    {"day": e.day, "name": e.name, "increments": dict(e.increments)}
                    for e in a.events
                ],
            }
            for a in ARCHETYPES
        ],
        "simulation": {
            "primary_seed": sim.PRIMARY_SEED,
            "seed_replicate_stride": sim.SEED_REPLICATE_STRIDE,
            "seed_archetype_stride": sim.SEED_ARCHETYPE_STRIDE,
            "sensitivity_replicate_offset": sim.SENSITIVITY_REPLICATE_OFFSET,
            "initial_noise_sigma": sim.INITIAL_NOISE_SIGMA,
            "reassessment_noise_sigma": sim.REASSESSMENT_NOISE_SIGMA,
            "attenuation_probability": sim.ATTENUATION_PROBABILITY,
            "attenuation_factor": sim.ATTENUATION_FACTOR,
            "event_score_noise_sigma": sim.EVENT_SCORE_NOISE_SIGMA,
            "primary_tau": sim.PRIMARY_TAU,
            "triggered_delay_days": list(sim.TRIGGERED_DELAY_DAYS),
            "triggered_delay_weights": list(sim.TRIGGERED_DELAY_WEIGHTS),
            "subthreshold_delay_range": list(sim.SUBTHRESHOLD_DELAY_RANGE),
            "false_trigger_base": sim.FALSE_TRIGGER_BASE,
            "false_trigger_scale": sim.FALSE_TRIGGER_SCALE,
            "false_trigger_decay": sim.FALSE_TRIGGER_DECAY,
            "monthly_review_days": list(sim.MONTHLY_REVIEW_DAYS),
            "review_hours": {
                "static": sim.STATIC_REVIEW_HOURS,
                "monthly_each": sim.MONTHLY_REVIEW_HOURS_EACH,
                "monthly_count": sim.MONTHLY_REVIEW_COUNT,
                "acp_initial": sim.ACP_INITIAL_HOURS,
                "acp_per_trigger": sim.ACP_HOURS_PER_TRIGGER,
                "acp_per_membership_change": sim.ACP_HOURS_PER_MEMBERSHIP_CHANGE,
            },
            "irrelevance_threshold": sim.IRRELEVANCE_THRESHOLD,
        },
        "mnmm_allowlist": sorted(SPECS),
        "crosswalk_edge_counts": coverage_report(),
    }
    text = json.dumps(payload, indent=2, sort_keys=False)
    if args.output_file:
        Path(args.output_file).write_text(text + "\n", encoding="utf-8")
        print(f"Wrote {args.output_file}")
    else:
        print(text)
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="acp-sme",
        description=(
            "ACP-SME reference prototype: a metadata-driven adaptive cybersecurity "
            "protector for SMEs. All outputs are synthetic model results."
        ),
    )
    parser.add_argument("--version", action="version", version=f"acp-sme {__version__}")
    sub = parser.add_subparsers(dest="command", required=True)

    common_output = dict(default=str(DEFAULT_RESULTS), help="output directory (default: results)")

    p = sub.add_parser("reproduce", help="run everything and write the reproduction package")
    p.add_argument("-o", "--output", **common_output)
    p.add_argument("-r", "--replicates", type=int, default=30)
    p.add_argument("--daily", action="store_true", help="also export per-day coverage (large)")
    p.add_argument("--no-figures", action="store_true", help="skip figure rendering")
    p.set_defaults(func=cmd_reproduce)

    p = sub.add_parser("experiment", help="primary experiment (Table 6)")
    p.add_argument("-o", "--output", **common_output)
    p.add_argument("-r", "--replicates", type=int, default=30)
    p.add_argument("--daily", action="store_true")
    p.set_defaults(func=cmd_experiment)

    p = sub.add_parser("sensitivity", help="sensitivity analysis (Table 7)")
    p.add_argument("-o", "--output", **common_output)
    p.add_argument("-r", "--replicates", type=int, default=10)
    p.set_defaults(func=cmd_sensitivity)

    p = sub.add_parser("demo", help="worked end-to-end governance walkthrough")
    p.set_defaults(func=cmd_demo)

    p = sub.add_parser("selftest", help="check selector, guard and reproducibility invariants")
    p.set_defaults(func=cmd_selftest)

    p = sub.add_parser("params", help="dump every parameter pack as JSON")
    p.add_argument("-o", "--output-file", default=None)
    p.set_defaults(func=cmd_params)

    return parser


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = build_parser().parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
