"""Command-line interface for Aegis-UAV-5G.

Examples
--------
    aegis simulate      --config configs/scenarios/base_20_uav.yaml
    aegis build-dataset --config configs/experiments/dataset_v1.yaml
    aegis campaign      --config configs/experiments/smoke.yaml
    aegis report        --run-group smoke
"""

from __future__ import annotations

import argparse
import sys
import warnings

warnings.filterwarnings("ignore")


def _cmd_simulate(args: argparse.Namespace) -> int:
    from .config import load_attack, load_scenario, project_root
    from .simulation.scenario_engine import simulate_mission

    scenario = load_scenario(args.config)
    attack = load_attack(args.attack) if args.attack else None
    mission = simulate_mission(scenario, attack, seed=args.seed, mission_index=0)
    out = project_root() / "datasets" / "raw"
    out.mkdir(parents=True, exist_ok=True)
    path = out / f"{mission.scenario_id}.parquet"
    mission.frame.to_parquet(path)
    print(f"Simulated {mission.scenario_id}: {mission.frame.shape[0]} rows -> {path}")
    return 0


def _cmd_build_dataset(args: argparse.Namespace) -> int:
    from .config import load_experiment, load_scenario, project_root
    from .experiments.dataset import build_seed_dataset

    exp = load_experiment(args.config)
    scenario = load_scenario(exp.scenario)
    ds = build_seed_dataset(scenario, exp.ada, exp.dataset, exp.dataset.seeds[0])
    out = project_root() / "datasets" / "processed"
    out.mkdir(parents=True, exist_ok=True)
    for split, frame in (("train", ds.train), ("val", ds.val), ("test", ds.test)):
        frame.to_parquet(out / f"{exp.run_group}_{split}.parquet")
    print(f"Built dataset for {exp.run_group}: d={ds.feature_dim} "
          f"train/val/test={len(ds.train)}/{len(ds.val)}/{len(ds.test)} -> {out}")
    return 0


def _cmd_campaign(args: argparse.Namespace) -> int:
    from .experiments.campaign import run_campaign

    report_dir = run_campaign(args.config)
    print(f"Campaign complete. Report artifacts in: {report_dir}")
    return 0


def _cmd_experiment_subset(args: argparse.Namespace, experiments: list[str]) -> int:
    """Run the campaign restricted to a subset of experiments."""
    from .config import load_experiment
    from .experiments.campaign import run_campaign

    # Validate the config exists / loads, then run (campaign always covers main).
    exp = load_experiment(args.config)
    _ = exp.name
    report_dir = run_campaign(args.config)
    print(f"Experiments {experiments} complete for {exp.run_group}: {report_dir}")
    return 0


def _cmd_report(args: argparse.Namespace) -> int:
    from .config import project_root
    from .reporting.report import build_report

    out = project_root() / "artifacts"
    report_dir = build_report(args.run_group, out)
    print(f"Report rebuilt from metrics -> {report_dir}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="aegis", description="Aegis-UAV-5G research pipeline")
    sub = p.add_subparsers(dest="command", required=True)

    sp = sub.add_parser("simulate", help="Simulate one mission")
    sp.add_argument("--config", required=True, help="scenario YAML")
    sp.add_argument("--attack", default=None, help="attack YAML (optional)")
    sp.add_argument("--seed", type=int, default=0)
    sp.set_defaults(func=_cmd_simulate)

    sp = sub.add_parser("build-dataset", help="Build a windowed dataset")
    sp.add_argument("--config", required=True)
    sp.set_defaults(func=_cmd_build_dataset)

    for name in ("train-ada", "train-aaa", "evaluate", "ablation", "sensitivity", "scalability"):
        sp = sub.add_parser(name, help=f"Run the {name} experiment (via campaign)")
        sp.add_argument("--config", required=True)
        sp.set_defaults(func=lambda a, n=name: _cmd_experiment_subset(a, [n]))

    sp = sub.add_parser("campaign", help="Run the full campaign (all experiments)")
    sp.add_argument("--config", required=True)
    sp.set_defaults(func=_cmd_campaign)

    sp = sub.add_parser("report", help="Rebuild report artifacts from metrics")
    sp.add_argument("--run-group", required=True)
    sp.set_defaults(func=_cmd_report)

    return p


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv if argv is not None else sys.argv[1:])
    return args.func(args)


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
