"""Command-line entry point: ``python -m cimcdm``.

Sub-commands
------------
``exact``        exact enumeration only (seconds)
``benchmark``    exact enumeration + matched evolutionary runs + statistics
``sensitivity``  25-cell temporal-rate grid
``all``          everything, plus figures and CSV exports
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd

from . import __version__
from .config import DEFAULT_ALGORITHM, DEFAULT_SCENARIO, AlgorithmConfig
from .exact import enumerate_exact
from .experiment import representative_run, run_benchmark
from .instance import generate_instance, load_published_instance
from .model import PortfolioModel
from .sensitivity import corner_summary, sensitivity_grid
from .validation import (
    report,
    validate_algorithms,
    validate_exact,
    validate_scenario,
    validate_sensitivity,
)


def _instance(args):
    if args.generated:
        return generate_instance(args.generator_seed)
    return load_published_instance()


def _write(frame: pd.DataFrame, directory: Path, name: str) -> None:
    directory.mkdir(parents=True, exist_ok=True)
    frame.to_csv(directory / name, index=False)
    print(f"  wrote {directory / name}")


def _algorithm_config(args) -> AlgorithmConfig:
    seeds = tuple(DEFAULT_ALGORITHM.seeds[: args.seeds]) if args.seeds else DEFAULT_ALGORITHM.seeds
    return AlgorithmConfig(
        population=args.population,
        generations=args.generations,
        seeds=seeds,
    )


def command_exact(args) -> bool:
    model = PortfolioModel(_instance(args), DEFAULT_SCENARIO)
    exact = enumerate_exact(model)
    print(json.dumps(exact.summary(), indent=2, default=str))

    ok = report(validate_scenario(model), "Scenario bounds (Table 2)")
    ok &= report(validate_exact(exact), "Exact enumeration (Sections 3.1, 3.3)")

    if args.output:
        directory = Path(args.output)
        _write(
            pd.DataFrame(exact.F_front, columns=["f1_benefit_shortfall", "f2_cost", "f3_risk"]),
            directory, "exact_front_objectives.csv",
        )
        _write(
            pd.DataFrame(exact.X_front.astype(int), columns=list(model.instance.names)),
            directory, "exact_front_portfolios.csv",
        )
    return ok


def command_benchmark(args) -> bool:
    instance = _instance(args)
    result = run_benchmark(instance, DEFAULT_SCENARIO, _algorithm_config(args))

    print("\nTable 5 - quality and runtime")
    print(result.summary_table().to_string(index=False))
    print("\nTable 4 - convergence checkpoints")
    print(result.convergence_table().to_string(index=False))
    print("\nTable 6 - paired Wilcoxon tests with Holm correction")
    print(result.tests_table().to_string(index=False))
    print("\nShare of exact hypervolume recovered:")
    for method, percent in result.recovery_percentages().items():
        print(f"  {method}: {percent:.2f}%")

    ok = report(validate_exact(result.exact), "Exact enumeration")
    ok &= report(validate_algorithms(result), "Algorithm comparison (Table 5)")

    if args.output:
        directory = Path(args.output)
        _write(result.runs, directory, "run_level_metrics.csv")
        _write(result.convergence, directory, "convergence_by_generation.csv")
        _write(result.tests_table(), directory, "wilcoxon_holm_tests.csv")
    return ok


def command_sensitivity(args) -> bool:
    instance = _instance(args)
    grid = sensitivity_grid(instance, DEFAULT_SCENARIO, progress=True)

    print("\nTable 7 - selected exact sensitivity outcomes")
    print(corner_summary(grid).to_string(index=False))
    print(f"\nDistinct knee portfolios across {len(grid)} cells: {grid['knee_systems'].nunique()}")

    ok = report(validate_sensitivity(grid), "Sensitivity grid (Table 7)")
    if args.output:
        _write(grid, Path(args.output), "sensitivity_grid.csv")
    return ok


def command_all(args) -> bool:
    # Headless by construction: the CLI only ever writes figures to disk.
    import matplotlib

    matplotlib.use("Agg")

    from . import figures

    directory = Path(args.output or "results")
    instance = _instance(args)

    result = run_benchmark(instance, DEFAULT_SCENARIO, _algorithm_config(args))
    print("\nTable 5 - quality and runtime")
    print(result.summary_table().to_string(index=False))
    print("\nTable 6 - paired Wilcoxon tests with Holm correction")
    print(result.tests_table().to_string(index=False))

    print("\nSensitivity grid ...")
    grid = sensitivity_grid(instance, DEFAULT_SCENARIO, progress=True)
    print(corner_summary(grid).to_string(index=False))

    _write(result.runs, directory, "run_level_metrics.csv")
    _write(result.convergence, directory, "convergence_by_generation.csv")
    _write(result.tests_table(), directory, "wilcoxon_holm_tests.csv")
    _write(result.summary_table(), directory, "quality_summary.csv")
    _write(grid, directory, "sensitivity_grid.csv")
    _write(
        pd.DataFrame(result.exact.F_front, columns=["f1_benefit_shortfall", "f2_cost", "f3_risk"]),
        directory, "exact_front_objectives.csv",
    )
    _write(
        pd.DataFrame(result.exact.X_front.astype(int), columns=list(instance.names)),
        directory, "exact_front_portfolios.csv",
    )

    figure_dir = directory / "figures"
    figures.figure_convergence(
        result.convergence, result.exact.hypervolume, figure_dir / "figure2_convergence.png"
    )
    figures.figure_metric_distributions(result.runs, figure_dir / "figure3_distributions.png")
    if result.run_objects:
        wsm_front = _wsm_front(result)
        figures.figure_front_projections(
            result.exact.F_front,
            representative_run(result, "NSGA-II").F,
            representative_run(result, "NSGA-III").F,
            wsm_front,
            figure_dir / "figure4_projections.png",
        )
    figures.figure_sensitivity(grid, figure_dir / "figure5_sensitivity.png")
    figures.figure_response_curves(result.model, figure_dir / "figureA_response_curves.png")
    print(f"  wrote figures to {figure_dir}")

    ok = report(validate_scenario(result.model), "Scenario bounds (Table 2)")
    ok &= report(validate_exact(result.exact), "Exact enumeration (Sections 3.1, 3.3)")
    ok &= report(validate_algorithms(result), "Algorithm comparison (Table 5)")
    ok &= report(validate_sensitivity(grid), "Sensitivity grid (Table 7)")
    return ok


def _wsm_front(result) -> np.ndarray:
    from .algorithms import run_weighted_sum

    run, _ = run_weighted_sum(
        result.model, result.exact.F_feasible, result.exact.X_feasible, DEFAULT_ALGORITHM
    )
    return run.F


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="cimcdm",
        description="Reproduce the cloud-integration multicriteria benchmark.",
    )
    parser.add_argument("--version", action="version", version=f"cimcdm {__version__}")

    subparsers = parser.add_subparsers(dest="command", required=True)
    commands = {
        "exact": command_exact,
        "benchmark": command_benchmark,
        "sensitivity": command_sensitivity,
        "all": command_all,
    }

    for name, handler in commands.items():
        sub = subparsers.add_parser(name, help=handler.__doc__)
        sub.set_defaults(handler=handler)
        sub.add_argument("-o", "--output", help="Directory for CSV and figure output")
        sub.add_argument(
            "--generated",
            action="store_true",
            help="Use a freshly generated instance instead of the published Appendix A values",
        )
        sub.add_argument("--generator-seed", type=int, default=20260902)
        if name in {"benchmark", "all"}:
            sub.add_argument(
                "--seeds",
                type=int,
                default=None,
                help="Use only the first N of the 30 published seeds (quick runs)",
            )
            sub.add_argument("--population", type=int, default=DEFAULT_ALGORITHM.population)
            sub.add_argument("--generations", type=int, default=DEFAULT_ALGORITHM.generations)

    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    ok = args.handler(args)
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
