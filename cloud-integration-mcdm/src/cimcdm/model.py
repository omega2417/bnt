"""The three-objective, time-aware cloud-integration portfolio model.

Implements Equations (1)-(11) of the article. Every objective is a minimization
objective:

    f1 = 1 - V(x, t)    benefit shortfall
    f2 = C(x)           normalized integration cost
    f3 = R(x, t)        normalized residual risk

subject to budget, implementation-effort, criticality-coverage, mean-reliability,
mean-technical-readiness and non-emptiness constraints.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from .config import DEFAULT_SCENARIO, ScenarioConfig
from .instance import Instance


@dataclass(frozen=True)
class KneeSolution:
    """One compromise portfolio selected by the normalized-distance rule (Eq. 11)."""

    x: np.ndarray
    objectives: np.ndarray
    selected: tuple[str, ...]
    benefit: float
    cost_units: float
    effort_units: float
    coverage: float
    mean_reliability: float
    mean_technical: float


class PortfolioModel:
    """Objectives and feasibility for one instance under one scenario setting.

    Parameters
    ----------
    instance:
        The candidate systems.
    scenario:
        Horizon, benefit weights, constraint fractions and thresholds.
    s_alpha, s_beta:
        Sensitivity multipliers applied to every adaptation rate ``alpha_i`` and
        every economic-benefit accumulation rate ``beta_i``. The normalization
        constant ``v_max`` is *not* rescaled with them: it stays fixed at the
        upper boundary of the tested grid so objective values remain comparable
        across the whole sensitivity analysis.
    """

    def __init__(
        self,
        instance: Instance,
        scenario: ScenarioConfig = DEFAULT_SCENARIO,
        s_alpha: float = 1.0,
        s_beta: float = 1.0,
    ) -> None:
        self.instance = instance
        self.scenario = scenario
        self.s_alpha = float(s_alpha)
        self.s_beta = float(s_beta)

        t = scenario.horizon
        self.benefit = self._benefit_vector(t, self.s_alpha, self.s_beta)
        self.risk = self._risk_vector(t)

        # Vmax is fixed before optimization at the upper boundary of the tested
        # temporal-rate range (Section 2.2).
        scale = scenario.vmax_rate_scale
        self.v_max = float(self._benefit_vector(t, scale, scale).sum())

        self.total_cost = float(instance.cost.sum())
        self.total_risk = float(instance.risk_initial.sum())
        self.total_criticality = float(instance.criticality.sum())
        self.total_effort = float(instance.effort.sum())

        self.budget = scenario.budget_fraction * self.total_cost
        self.time_cap = scenario.time_fraction * self.total_effort
        self.coverage_minimum = scenario.coverage_fraction * self.total_criticality

        # Centred forms of the two portfolio-average constraints (Eq. 7). Writing
        # them as sum((q_i - q_min) * x_i) >= 0 avoids dividing by |x|.
        self.reliability_slack = instance.reliability - scenario.min_mean_reliability
        self.technical_slack = instance.technical - scenario.min_mean_technical

    # ------------------------------------------------------------------
    # Time-dependent per-system quantities (Eqs. 2, 8-10)
    # ------------------------------------------------------------------
    def _benefit_vector(self, t: float, s_alpha: float, s_beta: float) -> np.ndarray:
        inst, cfg = self.instance, self.scenario
        performance = inst.p0 + inst.delta_p * (1.0 - np.exp(-inst.alpha * s_alpha * t))
        economic = inst.e0 + inst.delta_e * (1.0 - np.exp(-inst.beta * s_beta * t))
        return inst.reliability * (
            cfg.w_performance * performance
            + cfg.w_economic * economic
            + cfg.w_technical * inst.technical
            + cfg.w_human * inst.human
        )

    def _risk_vector(self, t: float) -> np.ndarray:
        inst = self.instance
        decay = np.exp(-inst.rho * t)
        return inst.risk_residual + (inst.risk_initial - inst.risk_residual) * decay

    # ------------------------------------------------------------------
    # Objectives and constraints
    # ------------------------------------------------------------------
    @staticmethod
    def _as_matrix(x: np.ndarray) -> tuple[np.ndarray, bool]:
        x = np.asarray(x, dtype=float)
        if x.ndim == 1:
            return x[None, :], True
        return x, False

    def objectives(self, x: np.ndarray) -> np.ndarray:
        """Return the three minimization objectives (Eq. 1) for one or many portfolios."""
        matrix, single = self._as_matrix(x)
        f1 = 1.0 - (matrix @ self.benefit) / self.v_max
        f2 = (matrix @ self.instance.cost) / self.total_cost
        f3 = (matrix @ self.risk) / self.total_risk
        out = np.column_stack([f1, f2, f3])
        return out[0] if single else out

    def is_feasible(self, x: np.ndarray, tolerance: float = 1e-9) -> np.ndarray:
        """Element-wise feasibility test against Equations (6) and (7)."""
        matrix, single = self._as_matrix(x)
        ok = (
            (matrix @ self.instance.cost <= self.budget + tolerance)
            & (matrix @ self.instance.effort <= self.time_cap + tolerance)
            & (matrix @ self.instance.criticality >= self.coverage_minimum - tolerance)
            & (matrix @ self.reliability_slack >= -tolerance)
            & (matrix @ self.technical_slack >= -tolerance)
            & (matrix.sum(axis=1) >= 1)
        )
        return bool(ok[0]) if single else ok

    def constraint_violation(self, x: np.ndarray) -> np.ndarray:
        """Total magnitude of constraint violation; 0 exactly when feasible."""
        matrix, single = self._as_matrix(x)
        parts = np.column_stack(
            [
                np.maximum(matrix @ self.instance.cost - self.budget, 0.0),
                np.maximum(matrix @ self.instance.effort - self.time_cap, 0.0),
                np.maximum(self.coverage_minimum - matrix @ self.instance.criticality, 0.0),
                np.maximum(-(matrix @ self.reliability_slack), 0.0),
                np.maximum(-(matrix @ self.technical_slack), 0.0),
                np.maximum(1.0 - matrix.sum(axis=1), 0.0),
            ]
        )
        total = parts.sum(axis=1)
        return float(total[0]) if single else total

    # ------------------------------------------------------------------
    # Portfolio reporting
    # ------------------------------------------------------------------
    def describe(self, x: np.ndarray) -> dict[str, object]:
        """Human-readable summary of a single portfolio."""
        x = np.asarray(x, dtype=float)
        selected = tuple(
            name for name, on in zip(self.instance.names, x) if on > 0.5
        )
        size = max(int(x.sum()), 1)
        f = self.objectives(x)
        return {
            "selected": selected,
            "size": len(selected),
            "benefit": float(1.0 - f[0]),
            "cost_normalized": float(f[1]),
            "risk_normalized": float(f[2]),
            "cost_units": float(x @ self.instance.cost),
            "effort_units": float(x @ self.instance.effort),
            "coverage": float(x @ self.instance.criticality),
            "mean_reliability": float(x @ self.instance.reliability / size),
            "mean_technical": float(x @ self.instance.technical / size),
            "feasible": bool(self.is_feasible(x)),
        }

    def knee(self, X: np.ndarray, F: np.ndarray | None = None) -> KneeSolution:
        """Normalized-distance knee portfolio of a front (Eq. 11).

        Minimizes the Euclidean distance to the ideal point after min-max scaling
        of the front, so that the three objectives contribute comparably.
        """
        X = np.atleast_2d(np.asarray(X, dtype=float))
        F = self.objectives(X) if F is None else np.asarray(F, dtype=float)
        ideal, nadir = F.min(axis=0), F.max(axis=0)
        span = np.where(nadir - ideal > 0, nadir - ideal, 1.0)
        distance = np.linalg.norm((F - ideal) / span, axis=1)
        best = int(np.argmin(distance))
        info = self.describe(X[best])
        return KneeSolution(
            x=X[best].copy(),
            objectives=F[best].copy(),
            selected=info["selected"],
            benefit=info["benefit"],
            cost_units=info["cost_units"],
            effort_units=info["effort_units"],
            coverage=info["coverage"],
            mean_reliability=info["mean_reliability"],
            mean_technical=info["mean_technical"],
        )
