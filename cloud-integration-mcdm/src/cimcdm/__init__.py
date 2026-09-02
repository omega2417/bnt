"""cimcdm - Cloud-Integration Multicriteria Decision Model.

Reference implementation of the three-objective, time-aware portfolio model in

    Torstensson, O.; Prokopovych-Tkachenko, D.; Lakhno, V.; Desiatko, A.;
    Fedotov, S. "Multicriteria Model for Integrating Distributed Systems into
    Cloud Services."

The package reproduces the article's exact enumeration, its NSGA-II / NSGA-III /
weighted-sum comparison, its paired statistical tests and its 25-cell temporal
sensitivity analysis.

Quick start
-----------
>>> from cimcdm import load_published_instance, PortfolioModel, enumerate_exact
>>> model = PortfolioModel(load_published_instance())
>>> exact = enumerate_exact(model)
>>> exact.front_size
446
"""

from .algorithms import (
    das_dennis_directions,
    run_nsga2,
    run_nsga3,
    run_weighted_sum,
)
from .config import (
    DEFAULT_ALGORITHM,
    DEFAULT_SCENARIO,
    DEFAULT_SENSITIVITY,
    AlgorithmConfig,
    ScenarioConfig,
    SensitivityConfig,
)
from .exact import ExactResult, enumerate_exact
from .experiment import BenchmarkResult, representative_run, run_benchmark
from .instance import Instance, generate_instance, load_published_instance
from .metrics import (
    evaluate_front,
    exact_front_coverage,
    hypervolume,
    igd_plus,
    spacing,
)
from .model import KneeSolution, PortfolioModel
from .pareto import ParetoArchive, nondominated_mask, nondominated_sort
from .sensitivity import corner_summary, knee_is_invariant, sensitivity_grid
from .statistics import compare_methods, holm_adjust
from .validation import (
    validate_algorithms,
    validate_exact,
    validate_scenario,
    validate_sensitivity,
)

__version__ = "1.0.0"

__all__ = [
    "AlgorithmConfig",
    "BenchmarkResult",
    "DEFAULT_ALGORITHM",
    "DEFAULT_SCENARIO",
    "DEFAULT_SENSITIVITY",
    "ExactResult",
    "Instance",
    "KneeSolution",
    "ParetoArchive",
    "PortfolioModel",
    "ScenarioConfig",
    "SensitivityConfig",
    "compare_methods",
    "corner_summary",
    "das_dennis_directions",
    "enumerate_exact",
    "evaluate_front",
    "exact_front_coverage",
    "generate_instance",
    "holm_adjust",
    "hypervolume",
    "igd_plus",
    "knee_is_invariant",
    "load_published_instance",
    "nondominated_mask",
    "nondominated_sort",
    "representative_run",
    "run_benchmark",
    "run_nsga2",
    "run_nsga3",
    "run_weighted_sum",
    "sensitivity_grid",
    "spacing",
    "validate_algorithms",
    "validate_exact",
    "validate_scenario",
    "validate_sensitivity",
    "__version__",
]
