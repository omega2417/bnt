"""End-to-end benchmark: exact enumeration, matched replications, statistics.

``run_benchmark`` reproduces Tables 4-6 of the article. It is deliberately
parameterized by ``seeds`` so a Colab session can run a quick 5-seed pass before
committing to the full 30-seed protocol.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable, Sequence

import numpy as np
import pandas as pd

from .algorithms import RunResult, run_nsga2, run_nsga3, run_weighted_sum
from .config import (
    CONVERGENCE_CHECKPOINTS,
    DEFAULT_ALGORITHM,
    DEFAULT_SCENARIO,
    AlgorithmConfig,
    ScenarioConfig,
)
from .exact import ExactResult, enumerate_exact
from .instance import Instance
from .metrics import evaluate_front
from .model import PortfolioModel
from .statistics import TestResult, compare_methods, mean_confidence_interval


@dataclass
class BenchmarkResult:
    """Everything Tables 4-6 and Figures 2-4 are drawn from."""

    model: PortfolioModel
    exact: ExactResult
    runs: pd.DataFrame
    """One row per (method, seed) with all five run-level metrics."""
    convergence: pd.DataFrame
    """Mean and 95% CI half-width of archive hypervolume per generation."""
    wsm: dict[str, float]
    tests: list[TestResult]
    run_objects: dict[str, list[RunResult]] = field(default_factory=dict)

    def summary_table(self) -> pd.DataFrame:
        """Table 5: mean +/- sample SD per method, plus the deterministic WSM row."""
        rows = []
        for method in ("NSGA-II", "NSGA-III"):
            subset = self.runs[self.runs["method"] == method]
            rows.append(
                {
                    "method": method,
                    "hypervolume": f"{subset['hypervolume'].mean():.6f} ± {subset['hypervolume'].std(ddof=1):.6f}",
                    "igd_plus": f"{subset['igd_plus'].mean():.6f} ± {subset['igd_plus'].std(ddof=1):.6f}",
                    "spacing": f"{subset['spacing'].mean():.6f} ± {subset['spacing'].std(ddof=1):.6f}",
                    "coverage_%": f"{100 * subset['coverage'].mean():.2f} ± {100 * subset['coverage'].std(ddof=1):.2f}",
                    "front_size": f"{subset['front_size'].mean():.1f} ± {subset['front_size'].std(ddof=1):.1f}",
                    "cpu_time_s": f"{subset['cpu_time'].mean():.3f} ± {subset['cpu_time'].std(ddof=1):.3f}",
                }
            )
        rows.append(
            {
                "method": "WSM",
                "hypervolume": f"{self.wsm['hypervolume']:.6f}",
                "igd_plus": f"{self.wsm['igd_plus']:.6f}",
                "spacing": f"{self.wsm['spacing']:.6f}",
                "coverage_%": f"{100 * self.wsm['coverage']:.2f}",
                "front_size": f"{int(self.wsm['front_size'])}",
                "cpu_time_s": f"{self.wsm['cpu_time']:.3f}*",
            }
        )
        return pd.DataFrame(rows)

    def tests_table(self) -> pd.DataFrame:
        """Table 6: paired Wilcoxon results after Holm correction."""
        return pd.DataFrame(
            [
                {
                    "metric": t.metric,
                    "W": t.statistic,
                    "p_raw": t.p_value,
                    "p_adjusted": t.adjusted_p,
                    "rank_biserial_r": t.rank_biserial,
                    "interpretation": t.interpretation,
                }
                for t in self.tests
            ]
        )

    def convergence_table(
        self, checkpoints: Sequence[int] = CONVERGENCE_CHECKPOINTS
    ) -> pd.DataFrame:
        """Table 4 / C1: mean hypervolume at the reported checkpoints."""
        available = [g for g in checkpoints if g in set(self.convergence["generation"])]
        return self.convergence[self.convergence["generation"].isin(available)].reset_index(
            drop=True
        )

    def recovery_percentages(self) -> dict[str, float]:
        """Share of the exact hypervolume recovered by each method."""
        exact_hv = self.exact.hypervolume
        out = {
            method: 100.0
            * self.runs[self.runs["method"] == method]["hypervolume"].mean()
            / exact_hv
            for method in ("NSGA-II", "NSGA-III")
        }
        out["WSM"] = 100.0 * self.wsm["hypervolume"] / exact_hv
        return out


def run_benchmark(
    instance: Instance,
    scenario: ScenarioConfig = DEFAULT_SCENARIO,
    algorithm: AlgorithmConfig = DEFAULT_ALGORITHM,
    seeds: Sequence[int] | None = None,
    progress: Callable[[str], None] | None = print,
    keep_runs: bool = True,
) -> BenchmarkResult:
    """Run exact enumeration, both evolutionary methods and WSM, then test.

    Parameters
    ----------
    seeds:
        Matched seeds shared by both evolutionary methods. Defaults to the 30
        seeds of the article (1001-1030). Pass a shorter sequence for a fast
        smoke run; statistical conclusions then carry correspondingly less weight.
    """
    # Flush every progress line: stdout is block-buffered when redirected to a
    # file, so without this a long run looks stalled in its own log.
    if progress is None:
        say = lambda _message: None
    elif progress is print:
        say = lambda message: print(message, flush=True)
    else:
        say = progress
    seeds = tuple(algorithm.seeds if seeds is None else seeds)

    model = PortfolioModel(instance, scenario)

    say(f"Exact enumeration of 2^{instance.n} = {1 << instance.n:,} portfolios ...")
    exact = enumerate_exact(model)
    say(
        f"  feasible: {exact.n_feasible:,} ({100 * exact.feasible_fraction:.2f}%)  "
        f"front: {exact.front_size}  hypervolume: {exact.hypervolume:.6f}"
    )

    reference_point = scenario.reference_point
    records: list[dict[str, object]] = []
    histories: dict[str, list[np.ndarray]] = {"NSGA-II": [], "NSGA-III": []}
    run_objects: dict[str, list[RunResult]] = {"NSGA-II": [], "NSGA-III": []}

    for method, runner in (("NSGA-II", run_nsga2), ("NSGA-III", run_nsga3)):
        say(f"{method}: {len(seeds)} matched runs ...")
        for seed in seeds:
            run = runner(model, seed, algorithm)
            quality = evaluate_front(run.F, exact.F_front, reference_point)
            records.append(
                {
                    "method": method,
                    "seed": seed,
                    "cpu_time": run.cpu_time,
                    **quality,
                }
            )
            histories[method].append(run.hypervolume_history)
            if keep_runs:
                run_objects[method].append(run)

    runs = pd.DataFrame(records)

    say("Weighted-sum baseline ...")
    wsm_run, n_weights = run_weighted_sum(
        model, exact.F_feasible, exact.X_feasible, algorithm
    )
    wsm = {
        **evaluate_front(wsm_run.F, exact.F_front, reference_point),
        "cpu_time": wsm_run.cpu_time,
        "n_weights": float(n_weights),
    }

    convergence = _convergence_frame(histories)

    metric_names = ["hypervolume", "igd_plus", "spacing", "cpu_time", "coverage"]
    tests = compare_methods(
        {m: runs[runs["method"] == "NSGA-II"][m].to_numpy() for m in metric_names},
        {m: runs[runs["method"] == "NSGA-III"][m].to_numpy() for m in metric_names},
    )

    return BenchmarkResult(
        model=model,
        exact=exact,
        runs=runs,
        convergence=convergence,
        wsm=wsm,
        tests=tests,
        run_objects=run_objects if keep_runs else {},
    )


def _convergence_frame(histories: dict[str, list[np.ndarray]]) -> pd.DataFrame:
    """Per-generation mean and 95% CI half-width for both methods."""
    lengths = [len(h) for hs in histories.values() for h in hs]
    n_generations = min(lengths) if lengths else 0

    rows = []
    for generation in range(n_generations):
        row: dict[str, object] = {"generation": generation}
        for method, runs in histories.items():
            values = np.array([h[generation] for h in runs])
            mean, half_width = mean_confidence_interval(values)
            key = "nsga2" if method == "NSGA-II" else "nsga3"
            row[f"{key}_mean"] = mean
            row[f"{key}_ci"] = half_width
        rows.append(row)
    return pd.DataFrame(rows)


def representative_run(result: BenchmarkResult, method: str) -> RunResult:
    """The run whose hypervolume is closest to that method's median (Figure 4)."""
    subset = result.runs[result.runs["method"] == method].reset_index(drop=True)
    median = subset["hypervolume"].median()
    position = int((subset["hypervolume"] - median).abs().idxmin())
    return result.run_objects[method][position]
