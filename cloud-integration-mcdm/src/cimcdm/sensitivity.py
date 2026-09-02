"""Two-factor sensitivity of the exact front to the temporal rates.

Every adaptation rate ``alpha_i`` is multiplied by ``s_alpha`` and every
economic-benefit accumulation rate ``beta_i`` by ``s_beta``. The normalization
constant ``Vmax`` and the hypervolume reference point stay fixed, so cells of the
grid are directly comparable. Exact enumeration is repeated in every cell, which
is what lets the analysis report whether the recommended portfolio itself changes.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from .config import DEFAULT_SCENARIO, DEFAULT_SENSITIVITY, ScenarioConfig, SensitivityConfig
from .exact import enumerate_exact
from .instance import Instance
from .model import PortfolioModel


def sensitivity_grid(
    instance: Instance,
    scenario: ScenarioConfig = DEFAULT_SCENARIO,
    grid: SensitivityConfig = DEFAULT_SENSITIVITY,
    progress: bool = False,
) -> pd.DataFrame:
    """Run exact enumeration for every (s_alpha, s_beta) cell.

    Returns one row per cell with the exact hypervolume, front size and the full
    description of that cell's knee portfolio.
    """
    rows = []
    total = len(grid.alpha_multipliers) * len(grid.beta_multipliers)

    for index, s_alpha in enumerate(grid.alpha_multipliers):
        for jndex, s_beta in enumerate(grid.beta_multipliers):
            if progress:
                cell = index * len(grid.beta_multipliers) + jndex + 1
                print(f"  cell {cell}/{total}: s_alpha={s_alpha}, s_beta={s_beta}", flush=True)

            model = PortfolioModel(instance, scenario, s_alpha=s_alpha, s_beta=s_beta)
            result = enumerate_exact(model)
            knee = result.knee

            rows.append(
                {
                    "s_alpha": s_alpha,
                    "s_beta": s_beta,
                    "feasible": result.n_feasible,
                    "front_size": result.front_size,
                    "hypervolume": result.hypervolume,
                    "knee_benefit": knee.benefit,
                    "knee_cost": float(knee.objectives[1]),
                    "knee_risk": float(knee.objectives[2]),
                    "knee_size": len(knee.selected),
                    "knee_systems": " ".join(knee.selected),
                    "knee_cost_units": knee.cost_units,
                    "knee_effort_units": knee.effort_units,
                    "knee_coverage": knee.coverage,
                    "knee_mean_reliability": knee.mean_reliability,
                    "knee_mean_technical": knee.mean_technical,
                }
            )

    return pd.DataFrame(rows)


def knee_is_invariant(grid_frame: pd.DataFrame) -> bool:
    """True when every cell of the grid selects the same set of systems."""
    return grid_frame["knee_systems"].nunique() == 1


def corner_summary(grid_frame: pd.DataFrame) -> pd.DataFrame:
    """Low-rate corner, baseline and high-rate corner rows (Table 7)."""
    def cell(s_alpha: float, s_beta: float) -> pd.Series:
        match = grid_frame[
            np.isclose(grid_frame["s_alpha"], s_alpha)
            & np.isclose(grid_frame["s_beta"], s_beta)
        ]
        return match.iloc[0]

    lo = grid_frame["s_alpha"].min()
    hi = grid_frame["s_alpha"].max()
    rows = [
        ("Low-rate corner", cell(lo, grid_frame["s_beta"].min())),
        ("Baseline", cell(1.0, 1.0)),
        ("High-rate corner", cell(hi, grid_frame["s_beta"].max())),
    ]
    return pd.DataFrame(
        [
            {
                "case": label,
                "s_alpha": row["s_alpha"],
                "s_beta": row["s_beta"],
                "hypervolume": row["hypervolume"],
                "front_size": int(row["front_size"]),
                "knee_benefit": row["knee_benefit"],
                "knee_cost": row["knee_cost"],
                "knee_risk": row["knee_risk"],
            }
            for label, row in rows
        ]
    )
