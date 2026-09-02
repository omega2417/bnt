"""Check computed results against the values printed in the article.

This module is what makes the archive self-verifying: it re-derives the headline
numbers and reports, per claim, whether the code reproduces the publication
within a stated tolerance. Small residuals are expected because Appendix A
publishes inputs rounded to six decimal places.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

PUBLISHED = {
    "n_portfolios": 262_144,
    "n_feasible": 83_657,
    "feasible_percent": 31.91,
    "front_size": 446,
    "exact_hypervolume": 0.421542857,
    "knee_systems": (
        "S01", "S04", "S05", "S10", "S12", "S13", "S16", "S17", "S18",
    ),
    "knee_benefit": 0.522919,
    "knee_cost_normalized": 0.416107,
    "knee_risk_normalized": 0.241278,
    "knee_cost_units": 124.0,
    "knee_effort_units": 35.0,
    "knee_coverage": 5.954293,
    "knee_mean_reliability": 0.939143,
    "knee_mean_technical": 0.745268,
    "budget": 172.84,
    "time_cap": 43.4,
    "coverage_minimum": 5.8382,
    "sensitivity_low_hypervolume": 0.398392,
    "sensitivity_low_front": 459,
    "sensitivity_low_knee_benefit": 0.492618,
    "sensitivity_high_hypervolume": 0.429727,
    "sensitivity_high_front": 478,
    "sensitivity_high_knee_benefit": 0.532203,
    "nsga2_mean_hypervolume": 0.418638,
    "nsga3_mean_hypervolume": 0.418961,
    "wsm_hypervolume": 0.417759,
    "wsm_igd_plus": 0.008742,
    "wsm_front_size": 29,
    "wsm_spacing": 0.016338,
    "wsm_coverage_percent": 6.50,
}


@dataclass(frozen=True)
class Check:
    """One reproduced claim."""

    name: str
    published: object
    computed: object
    tolerance: float
    passed: bool

    @property
    def difference(self) -> float | None:
        try:
            return float(self.computed) - float(self.published)
        except (TypeError, ValueError):
            return None

    def __str__(self) -> str:
        mark = "PASS" if self.passed else "FAIL"
        if isinstance(self.published, (int, float)) and not isinstance(self.published, bool):
            return (
                f"[{mark}] {self.name}: published={self.published}, "
                f"computed={self.computed}, diff={self.difference:+.3e}"
            )
        return f"[{mark}] {self.name}: published={self.published}, computed={self.computed}"


def _check(name: str, published, computed, tolerance: float = 0.0) -> Check:
    if isinstance(published, (int, float)) and not isinstance(published, bool):
        passed = abs(float(computed) - float(published)) <= tolerance
    else:
        passed = tuple(computed) == tuple(published)
    return Check(name, published, computed, tolerance, passed)


def validate_exact(exact) -> list[Check]:
    """Verify the exact-enumeration claims of Section 3.1 and Section 3.3."""
    knee = exact.knee
    return [
        _check("portfolios enumerated", PUBLISHED["n_portfolios"], exact.n_total),
        _check("feasible portfolios", PUBLISHED["n_feasible"], exact.n_feasible),
        _check(
            "feasible percent",
            PUBLISHED["feasible_percent"],
            round(100 * exact.feasible_fraction, 2),
            0.01,
        ),
        _check("exact front size", PUBLISHED["front_size"], exact.front_size),
        _check(
            "exact hypervolume",
            PUBLISHED["exact_hypervolume"],
            exact.hypervolume,
            1e-6,
        ),
        _check("knee systems", PUBLISHED["knee_systems"], knee.selected),
        _check("knee benefit", PUBLISHED["knee_benefit"], knee.benefit, 1e-5),
        _check(
            "knee normalized cost",
            PUBLISHED["knee_cost_normalized"],
            float(knee.objectives[1]),
            1e-5,
        ),
        _check(
            "knee normalized risk",
            PUBLISHED["knee_risk_normalized"],
            float(knee.objectives[2]),
            1e-4,
        ),
        _check("knee cost units", PUBLISHED["knee_cost_units"], knee.cost_units, 1e-9),
        _check("knee effort units", PUBLISHED["knee_effort_units"], knee.effort_units, 1e-9),
        _check("knee coverage", PUBLISHED["knee_coverage"], knee.coverage, 1e-5),
        _check(
            "knee mean reliability",
            PUBLISHED["knee_mean_reliability"],
            knee.mean_reliability,
            1e-5,
        ),
        _check(
            "knee mean technical",
            PUBLISHED["knee_mean_technical"],
            knee.mean_technical,
            1e-5,
        ),
    ]


def validate_scenario(model) -> list[Check]:
    """Verify the derived feasibility bounds of Table 2."""
    return [
        _check("budget B", PUBLISHED["budget"], model.budget, 1e-9),
        _check("time cap Tmax", PUBLISHED["time_cap"], model.time_cap, 1e-9),
        _check(
            "coverage minimum Kmin",
            PUBLISHED["coverage_minimum"],
            model.coverage_minimum,
            1e-4,
        ),
    ]


def validate_sensitivity(grid_frame) -> list[Check]:
    """Verify the three corner rows of Table 7 and knee invariance."""
    def cell(s_alpha: float, s_beta: float):
        match = grid_frame[
            np.isclose(grid_frame["s_alpha"], s_alpha)
            & np.isclose(grid_frame["s_beta"], s_beta)
        ]
        return match.iloc[0]

    low, high = cell(0.5, 0.5), cell(1.5, 1.5)
    return [
        _check(
            "low-corner hypervolume",
            PUBLISHED["sensitivity_low_hypervolume"],
            low["hypervolume"],
            1e-5,
        ),
        _check("low-corner front size", PUBLISHED["sensitivity_low_front"], int(low["front_size"])),
        _check(
            "low-corner knee benefit",
            PUBLISHED["sensitivity_low_knee_benefit"],
            low["knee_benefit"],
            1e-5,
        ),
        _check(
            "high-corner hypervolume",
            PUBLISHED["sensitivity_high_hypervolume"],
            high["hypervolume"],
            1e-5,
        ),
        _check("high-corner front size", PUBLISHED["sensitivity_high_front"], int(high["front_size"])),
        _check(
            "high-corner knee benefit",
            PUBLISHED["sensitivity_high_knee_benefit"],
            high["knee_benefit"],
            1e-5,
        ),
        _check(
            "knee composition invariant across 25 cells",
            1,
            int(grid_frame["knee_systems"].nunique()),
        ),
    ]


def validate_algorithms(result, tolerance: float = 5e-3) -> list[Check]:
    """Compare mean evolutionary and WSM outcomes with Table 5.

    Evolutionary means are stochastic, so the default tolerance is loose. A
    reduced-seed run will drift further than the full 30-seed protocol.
    """
    mean_hv = lambda method: float(
        result.runs[result.runs["method"] == method]["hypervolume"].mean()
    )
    return [
        _check("NSGA-II mean hypervolume", PUBLISHED["nsga2_mean_hypervolume"], mean_hv("NSGA-II"), tolerance),
        _check("NSGA-III mean hypervolume", PUBLISHED["nsga3_mean_hypervolume"], mean_hv("NSGA-III"), tolerance),
        _check("WSM hypervolume", PUBLISHED["wsm_hypervolume"], result.wsm["hypervolume"], 1e-5),
        _check("WSM IGD+", PUBLISHED["wsm_igd_plus"], result.wsm["igd_plus"], 1e-5),
        _check("WSM front size", PUBLISHED["wsm_front_size"], int(result.wsm["front_size"])),
        _check("WSM spacing", PUBLISHED["wsm_spacing"], result.wsm["spacing"], 1e-5),
        _check(
            "WSM coverage percent",
            PUBLISHED["wsm_coverage_percent"],
            round(100 * result.wsm["coverage"], 2),
            0.02,
        ),
    ]


def report(checks: list[Check], title: str = "Validation") -> bool:
    """Print a check list and return True when every check passed."""
    passed = sum(check.passed for check in checks)
    print(f"\n{title}: {passed}/{len(checks)} checks passed")
    print("-" * 78)
    for check in checks:
        print(f"  {check}")
    return passed == len(checks)
