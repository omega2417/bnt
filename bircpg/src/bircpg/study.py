"""Level II study driver (Sections 7.2, 7.3, 7.5).

The proposed core design crosses four population sizes with six prespecified
conditions -- stationary nominal, heterogeneous budgets, noisy sensing,
communication loss, changing task values, and a combined stress condition --
with thirty independent environmental seeds per cell.  That is 720
seed-condition runs per method and it is an *initial design size*, not a claim
of adequate statistical power.

The defaults here are deliberately smaller so a study finishes inside a
notebook session.  :func:`preregistered_design` returns the full manuscript
design; pass it to :func:`run_study` to run it as specified.

Methods are paired on identical environmental seeds, and the paired analysis
resamples whole runs (Section 7.5).  Nothing in this module selects the winner
after seeing the results: the primary outcome for each hypothesis is declared in
:data:`PRIMARY_OUTCOMES` before any run.
"""

from __future__ import annotations

import csv
import random
from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Sequence, Tuple

from .baselines import CoordinationMethod, default_methods
from .environments import EnvironmentConfig, make_environment
from .metrics import BootstrapResult, endpoints, holm_adjust, paired_bootstrap
from .protocol import RunResult, run_trial

__all__ = [
    "CONDITIONS",
    "REFERENCE_HORIZON",
    "scale_dynamics",
    "PRIMARY_OUTCOMES",
    "StudyDesign",
    "preregistered_design",
    "demonstration_design",
    "run_study",
    "paired_comparison",
    "write_endpoints_csv",
]

#: The six prespecified conditions of Section 7.2, as deltas on a base config.
CONDITIONS: Dict[str, Dict[str, object]] = {
    "stationary_nominal": {},
    "heterogeneous_budgets": {"heterogeneous_caps": True},
    "noisy_sensing": {"observation_noise": 0.15},
    "communication_loss": {"comm_loss": 0.3},
    "changing_values": {"value_change_period": 100, "value_change_fraction": 0.25},
    "combined_stress": {
        "heterogeneous_caps": True,
        "observation_noise": 0.15,
        "comm_loss": 0.3,
        "value_change_period": 100,
        "value_change_fraction": 0.25,
        "dropout_epoch": 500,
        "dropout_fraction": 0.10,
        "trace_delay": 5,
    },
}

#: One primary outcome per hypothesis, declared before any run (Section 7.5).
PRIMARY_OUTCOMES: Dict[str, Dict[str, str]] = {
    "H1": {
        "outcome": "evaluations_to_threshold",
        "direction": "lower_is_better",
        "comparison": "proposed-logit vs B2-uniform-logit",
        "note": "slowly varying environments only; censored runs are dropped, not imputed",
    },
    "H2": {
        "outcome": "cumulative_realised_value",
        "direction": "higher_is_better",
        "comparison": "proposed-logit vs B2-uniform-logit under changing_values",
        "note": "post-change accumulation; H2 predicts the H1 advantage can reverse",
    },
    "H3": {
        "outcome": "inference_energy",
        "direction": "lower_is_better",
        "comparison": "controller architectures at matched coordination rule",
        "note": "non-inferiority on realised task value required; margin set in advance",
    },
}


@dataclass
class StudyDesign:
    """A declared configuration.  Freeze it before opening evaluation seeds."""

    population_sizes: Tuple[int, ...] = (10,)
    conditions: Tuple[str, ...] = ("stationary_nominal",)
    seeds: int = 5
    epochs: int = 50
    base: EnvironmentConfig = field(default_factory=EnvironmentConfig)
    gap_tolerance: float = 0.05
    non_inferiority_margin: float = 0.05   # a design choice needing domain justification

    @property
    def cells(self) -> int:
        return len(self.population_sizes) * len(self.conditions)

    @property
    def runs_per_method(self) -> int:
        return self.cells * self.seeds


def preregistered_design() -> StudyDesign:
    """The core design as written in Section 7.2: 4 sizes x 6 conditions x 30 seeds.

    720 seed-condition runs per method over 1000 epochs.  This is expensive; it
    is provided so that the manuscript's design can be run verbatim, not because
    it is the default.
    """
    return StudyDesign(
        population_sizes=(10, 30, 50, 100),
        conditions=tuple(CONDITIONS),
        seeds=30,
        epochs=1000,
    )


def demonstration_design() -> StudyDesign:
    """A small design that finishes in a notebook.  Not the preregistered study."""
    return StudyDesign(
        population_sizes=(10, 20),
        conditions=("stationary_nominal", "noisy_sensing", "changing_values"),
        seeds=8,
        epochs=40,
    )


#: The manuscript's reference horizon.  The change schedule of Section 7.2 --
#: 25% of task values every 100 epochs, 10% of agents removed at epoch 500 -- is
#: written against it.
REFERENCE_HORIZON = 1000


def scale_dynamics(overrides: Dict[str, object], epochs: int) -> Tuple[Dict[str, object], bool]:
    """Keep a shortened run's change schedule proportional to the manuscript's.

    At the preregistered 1000-epoch horizon this is a no-op.  At a shorter
    demonstration horizon an unscaled schedule would simply never fire -- a
    "changing values" condition in which nothing ever changes is worse than
    useless, because it silently reports the stationary condition twice.  The
    caller is told whether scaling happened so the condition label can say so.
    """
    if epochs >= REFERENCE_HORIZON:
        return dict(overrides), False
    factor = epochs / REFERENCE_HORIZON
    scaled = dict(overrides)
    changed = False
    for key in ("value_change_period", "dropout_epoch"):
        value = scaled.get(key)
        if value:
            new = max(1, int(round(float(value) * factor)))
            if new != value:
                scaled[key] = new
                changed = True
    return scaled, changed


def run_study(
    design: StudyDesign,
    methods: Optional[Sequence[CoordinationMethod]] = None,
    progress: Optional[callable] = None,
) -> List[RunResult]:
    """Run every (size, condition, seed, method) cell.

    Each method faces an environment built from the same seed, so the paired
    analysis of Section 7.5 is valid.  A fresh :class:`Environment` is generated
    per method from that seed, since running an environment mutates it.

    Below the preregistered horizon the change schedule is scaled proportionally
    (see :func:`scale_dynamics`) and the condition label is suffixed ``+scaled``
    so that no result can be mistaken for one produced at the declared schedule.
    """
    methods = list(methods or default_methods(tau=design.base.tau))
    results: List[RunResult] = []
    total = design.runs_per_method * len(methods)
    done = 0
    for n in design.population_sizes:
        for condition in design.conditions:
            overrides, scaled = scale_dynamics(CONDITIONS[condition], design.epochs)
            label = f"{condition}+scaled" if scaled else condition
            config = replace(
                design.base, n_agents=n, epochs=design.epochs, **overrides
            )
            for seed in range(design.seeds):
                for method in methods:
                    env = make_environment(config, seed=seed)
                    result = run_trial(
                        env, method, seed=seed, condition=f"{label}/n={n}"
                    )
                    results.append(result)
                    done += 1
                    if progress is not None:
                        progress(done, total)
    return results


def paired_comparison(
    results: Sequence[RunResult],
    method_a: str,
    method_b: str,
    outcome: str,
    condition: Optional[str] = None,
    gap_tolerance: float = 0.05,
    resamples: int = 10_000,
    rng: Optional[random.Random] = None,
) -> BootstrapResult:
    """Paired bootstrap of ``outcome`` for ``method_a - method_b`` on shared seeds.

    Runs where either method's outcome is censored (e.g. the Nash-gap tolerance
    was never reached) are dropped and counted, never replaced by a favourable
    value.
    """
    rows = {}
    for run in results:
        if condition is not None and run.condition != condition:
            continue
        if run.method not in (method_a, method_b):
            continue
        rows.setdefault((run.condition, run.seed), {})[run.method] = endpoints(
            run, gap_tolerance
        )
    a_values, b_values, censored = [], [], []
    for key in sorted(rows):
        pair = rows[key]
        if method_a not in pair or method_b not in pair:
            continue
        va = getattr(pair[method_a], outcome)
        vb = getattr(pair[method_b], outcome)
        is_censored = va is None or vb is None
        a_values.append(float(va) if va is not None else 0.0)
        b_values.append(float(vb) if vb is not None else 0.0)
        censored.append(is_censored)
    return paired_bootstrap(
        a_values, b_values, resamples=resamples, rng=rng, censored=censored
    )


def write_endpoints_csv(
    results: Sequence[RunResult], path: str | Path, gap_tolerance: float = 0.05
) -> Path:
    """Write one endpoint row per run (Section 7.6: every table reproducible).

    Censored runs keep an empty ``evaluations_to_threshold`` cell and a
    ``reached_threshold`` flag, so a reader can see the missingness rather than
    infer it.
    """
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    rows = [endpoints(r, gap_tolerance).as_dict() for r in results]
    if not rows:
        raise ValueError("no runs to write")
    with path.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        for row in rows:
            if row["evaluations_to_threshold"] is None:
                row = dict(row, evaluations_to_threshold="")
            writer.writerow(row)
    return path
