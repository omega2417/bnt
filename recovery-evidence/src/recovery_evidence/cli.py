"""Command-line interface: ``recovery-evidence <command>``."""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

from . import __version__


def _cmd_checks(args) -> int:
    from .checks import run_checks

    results, text = run_checks()
    sys.stdout.write(text)
    if args.output:
        Path(args.output).parent.mkdir(parents=True, exist_ok=True)
        Path(args.output).write_text(text, encoding="utf-8")
    return 0 if all(ok for _, ok, _ in results) else 1


def _cmd_example(args) -> int:
    from .checks import EX_AGES, EX_N, EX_W, EX_Z
    from .policies import POLICIES, priorities, select, urgency
    from .topology import reference_map

    ref = reference_map()
    print("Worked example of Section 3.4 (components A..H)")
    print("  records z      :", EX_Z)
    print("  evidence ages  :", EX_AGES)
    print("  notice flags   :", EX_N, f"(w = {EX_W})")
    print("  urgency u      :", urgency(EX_AGES, EX_N, EX_W))
    print("  influence D(z) :", ref.influence(EX_Z))
    print("  static c       :", tuple(float(c) for c in ref.static_importance))
    for pol in POLICIES:
        pr = priorities(pol, ref, EX_Z, EX_AGES, EX_N, EX_W)
        shown = ", ".join(f"{float(p):g}" for p in pr)
        print(f"  {pol} priorities : ({shown}) -> selects {ref.components[select(pr)]}")
    return 0


def _cmd_params(args) -> int:
    from .conditions import load_conditions, load_raw

    raw = load_raw()
    doc = {k: raw[k] for k in ("schema", "root_entropy", "analysis_seed", "bootstrap_resamples", "policies", "streams")}
    doc["conditions"] = [c.to_dict() for c in load_conditions()]
    text = json.dumps(doc, indent=2) + "\n"
    if args.output:
        Path(args.output).write_text(text, encoding="utf-8")
    else:
        sys.stdout.write(text)
    return 0


def _cmd_run(args) -> int:
    from .experiment import run_experiment

    run_experiment(Path(args.output), args.conditions, args.replicates, args.jobs, not args.no_logs)
    return 0


def _cmd_analyze(args) -> int:
    from .analysis import analyse

    out = analyse(Path(args.output))
    print(" ", out["integrity"]["verdict"])
    return 0 if out["integrity"]["verdict"] == "ALL COMPARISONS AGREED" else 1


def _cmd_figures(args) -> int:
    from .figures import make_figures

    for path in make_figures(Path(args.output)):
        print(" ", path)
    return 0


def _cmd_claims(args) -> int:
    from .claims import write_register

    counts = write_register(Path(args.output))
    print(f"  {counts['total']} printed numbers: {counts['identical']} identical, {counts['differs']} differ "
          f"(see tables/manuscript_alignment.md)")
    return 0


def _cmd_hash(args) -> int:
    from .integrity import write_manifest

    print(f"  {write_manifest(Path(args.output))} files hashed")
    return 0


def _cmd_verify(args) -> int:
    from .integrity import verify

    ok, bad, absent = verify(Path(args.output))
    print(f"  {len(ok)} files match SHA256SUMS.txt; {len(bad)} differ; {len(absent)} not present")
    for name in bad:
        print("   DIFFERS:", name)
    if absent:
        print("   Not present (regenerate with `recovery-evidence run`):", ", ".join(absent[:6]),
              "..." if len(absent) > 6 else "")
    return 1 if bad else 0


def _cmd_reproduce(args) -> int:
    from .analysis import analyse
    from .checks import run_checks
    from .claims import write_register
    from .experiment import run_experiment
    from .integrity import MANIFEST, verify, write_manifest

    out = Path(args.output)
    t0 = time.time()
    print("[1/6] implementation checks")
    results, text = run_checks()
    out.mkdir(parents=True, exist_ok=True)
    (out / "control_checks.txt").write_text(text, encoding="utf-8")
    passed = sum(ok for _, ok, _ in results)
    print(f"  {passed} of {len(results)} checks passed")
    if passed != len(results):
        return 1
    print("[2/6] experiment: 13 conditions x 300 paired trajectories x 4 policies")
    run_experiment(out, None, None, args.jobs, True)
    print("[3/6] independent analysis of the logs")
    verdict = analyse(out)["integrity"]["verdict"]
    print(" ", verdict)
    print("[4/6] claim-to-evidence register")
    counts = write_register(out)
    print(f"  {counts['identical']} of {counts['total']} printed numbers identical")
    print("[5/6] figures")
    if args.no_figures:
        print("  skipped")
    else:
        try:
            from .figures import make_figures

            print(f"  {len(make_figures(out))} files")
        except ImportError:
            print("  matplotlib not installed: skipped (pip install 'recovery-evidence[figures]')")
    print("[6/6] SHA-256")
    if args.check and (out / MANIFEST).exists():
        ok, bad, absent = verify(out)
        print(f"  {len(ok)} files identical to the released SHA256SUMS.txt; {len(bad)} differ; {len(absent)} absent")
        for name in bad:
            print("   DIFFERS:", name)
        status = 1 if bad else 0
    else:
        print(f"  {write_manifest(out)} files hashed -> {MANIFEST}")
        status = 0
    print(f"done in {time.time() - t0:.0f} s")
    return status if verdict == "ALL COMPARISONS AGREED" else 1


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="recovery-evidence", description=__doc__)
    p.add_argument("--version", action="version", version=f"recovery-evidence {__version__}")
    sub = p.add_subparsers(dest="command", required=True)

    def add(name, fn, help_, output_default="results"):
        sp = sub.add_parser(name, help=help_)
        sp.set_defaults(fn=fn)
        if output_default is not None:
            sp.add_argument("-o", "--output", default=output_default, help="results directory (default: results)")
        return sp

    sp = add("checks", _cmd_checks, "run the 27 implementation checks of Section 4.6", None)
    sp.add_argument("-o", "--output", help="also write the report to this file")
    add("example", _cmd_example, "print the worked example of Section 3.4", None)
    sp = add("params", _cmd_params, "print the resolved configuration of all conditions", None)
    sp.add_argument("-o", "--output")
    sp = add("run", _cmd_run, "run the experiment and write the primary logs")
    sp.add_argument("-c", "--conditions", nargs="+", metavar="Cx", help="subset of conditions (default: all)")
    sp.add_argument("-r", "--replicates", type=int, help="override R (default: 300)")
    sp.add_argument("-j", "--jobs", type=int, help="worker processes (default: CPU count)")
    sp.add_argument("--no-logs", action="store_true", help="write trace summaries only")
    add("analyze", _cmd_analyze, "recompute outcomes from the logs and build the tables")
    add("figures", _cmd_figures, "draw Figures 1-5 (PDF, PNG, TIFF)")
    add("claims", _cmd_claims, "build the claim-to-evidence register")
    add("hash", _cmd_hash, "write SHA256SUMS.txt for the results directory")
    add("verify", _cmd_verify, "compare the results directory with SHA256SUMS.txt")
    sp = add("reproduce", _cmd_reproduce, "checks + experiment + analysis + register + figures + hashes")
    sp.add_argument("-j", "--jobs", type=int)
    sp.add_argument("--no-figures", action="store_true")
    sp.add_argument("--check", action="store_true",
                    help="compare the regenerated files with the released SHA256SUMS.txt instead of rewriting it")
    return p


def main(argv=None) -> int:
    args = build_parser().parse_args(argv)
    return args.fn(args)


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
