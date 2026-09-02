"""Scenario, algorithm and replication settings for the cloud-integration benchmark.

Every value here is taken from Tables 2 and 3 of the article
"Multicriteria Model for Integrating Distributed Systems into Cloud Services".
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Tuple


@dataclass(frozen=True)
class ScenarioConfig:
    """Decision context (Table 2)."""

    horizon: float = 12.0
    """Decision horizon t, in months."""

    w_performance: float = 0.35
    w_economic: float = 0.25
    w_technical: float = 0.25
    w_human: float = 0.15

    budget_fraction: float = 0.58
    """Budget B as a fraction of the cost of integrating every candidate system."""

    time_fraction: float = 0.62
    """Time cap Tmax as a fraction of total implementation effort."""

    coverage_fraction: float = 0.46
    """Kmin as a fraction of total business criticality."""

    min_mean_reliability: float = 0.875
    """qmin: lower bound on the portfolio-average reliability."""

    min_mean_technical: float = 0.68
    """Tmin: lower bound on the portfolio-average technical readiness."""

    reference_point: Tuple[float, float, float] = (1.05, 1.05, 1.05)
    """Fixed hypervolume reference point, shared by every method and sensitivity cell."""

    vmax_rate_scale: float = 1.5
    """Vmax is evaluated at the upper boundary of the tested temporal-rate grid
    (s_alpha = s_beta = 1.5) and then held fixed, so objective values stay
    comparable across the whole sensitivity grid."""

    def __post_init__(self) -> None:
        total = self.w_performance + self.w_economic + self.w_technical + self.w_human
        if abs(total - 1.0) > 1e-12:
            raise ValueError(f"Benefit weights must sum to 1, got {total}")


@dataclass(frozen=True)
class AlgorithmConfig:
    """Algorithm and replication settings (Table 3)."""

    population: int = 60
    generations: int = 100
    """Update generations, on top of the initial population (generation 0)."""

    crossover_probability: float = 0.90
    """Uniform crossover applied to a parent pair with this probability."""

    mutation_probability: float | None = None
    """Bit-flip probability per bit. ``None`` resolves to 1/n at run time,
    i.e. one expected flipped bit per child."""

    tournament_size: int = 2
    """Binary tournament parent selection."""

    das_dennis_divisions: int = 9
    """H = 9 on a 3-objective simplex gives 55 NSGA-III reference directions."""

    wsm_divisions: int = 20
    """H = 20 on a 3-objective simplex gives 231 weighted-sum weight vectors."""

    seeds: Tuple[int, ...] = tuple(range(1001, 1031))
    """30 matched seeds, shared by NSGA-II and NSGA-III."""

    repair_max_iterations: int = 200
    """Safety bound on the constraint-repair loop."""


@dataclass(frozen=True)
class SensitivityConfig:
    """Two-factor temporal-rate sensitivity grid (Section 3.3)."""

    alpha_multipliers: Tuple[float, ...] = (0.50, 0.75, 1.00, 1.25, 1.50)
    beta_multipliers: Tuple[float, ...] = (0.50, 0.75, 1.00, 1.25, 1.50)


GENERATOR_SEED = 20260902
"""Seed of the deterministic synthetic-scenario generator."""

CONVERGENCE_CHECKPOINTS: Tuple[int, ...] = (0, 10, 25, 50, 75, 100)
"""Generations reported in Table 4 / Table C1."""

DEFAULT_SCENARIO = ScenarioConfig()
DEFAULT_ALGORITHM = AlgorithmConfig()
DEFAULT_SENSITIVITY = SensitivityConfig()
