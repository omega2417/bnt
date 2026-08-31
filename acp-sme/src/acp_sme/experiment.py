"""Primary experiment (Table 6) and sensitivity analysis (Table 7).

Design: three archetypes x 30 seeded replicates x 120 daily windows
= 90 traces and 10,800 enterprise-days.  Sensitivity: five thresholds x three
budget factors, 10 fresh replicates per archetype per configuration.
"""

from __future__ import annotations

import csv
import json
from dataclasses import dataclass
from pathlib import Path
from statistics import fmean
from typing import Dict, List, Sequence, Tuple

from . import __version__
from .capabilities import CAPABILITY_PACK_VERSION
from .metrics import Interval, TraceOutcome, mean_ci, paired_difference, summarise_trace
from .scenarios import ARCHETYPES, HORIZON_DAYS, SCENARIO_PACK_VERSION, labelled_event_count
from .simulator import (
    PRIMARY_SEED,
    PRIMARY_TAU,
    SENSITIVITY_REPLICATE_OFFSET,
    TraceResult,
    false_trigger_probability,
    run_trace,
)

CONDITIONS: Tuple[str, ...] = ("static", "monthly", "acp")
CONDITION_LABELS: Dict[str, str] = {
    "static": "Static profile",
    "monthly": "Monthly review",
    "acp": "ACP-SME",
}

DEFAULT_REPLICATES = 30
SENSITIVITY_TAUS: Tuple[float, ...] = (0.18, 0.23, 0.28, 0.33, 0.38)
SENSITIVITY_BUDGET_FACTORS: Tuple[float, ...] = (0.85, 1.00, 1.15)
SENSITIVITY_REPLICATES = 10


@dataclass
class PrimaryResults:
    outcomes: Dict[str, List[TraceOutcome]]
    traces: List[TraceResult]

    @property
    def n_traces(self) -> int:
        return len(self.traces)


def run_primary(
    replicates: int = DEFAULT_REPLICATES,
    tau: float = PRIMARY_TAU,
    budget_factor: float = 1.0,
    keep_traces: bool = True,
) -> PrimaryResults:
    outcomes: Dict[str, List[TraceOutcome]] = {c: [] for c in CONDITIONS}
    traces: List[TraceResult] = []
    for archetype in ARCHETYPES:
        for replicate in range(replicates):
            trace = run_trace(archetype, replicate, tau=tau, budget_factor=budget_factor)
            for condition in CONDITIONS:
                outcomes[condition].append(summarise_trace(trace, condition))
            if keep_traces:
                traces.append(trace)
    return PrimaryResults(outcomes=outcomes, traces=traces)


def summarise_primary(results: PrimaryResults) -> Dict[str, object]:
    table: Dict[str, object] = {}
    for condition in CONDITIONS:
        rows = results.outcomes[condition]
        table[condition] = {
            "label": CONDITION_LABELS[condition],
            "mean_coverage_pct": _iv(mean_ci([100 * o.mean_coverage for o in rows])),
            "p10_coverage_pct": _iv(mean_ci([100 * o.p10_coverage for o in rows])),
            "adaptation_delay_days": _iv(mean_ci([o.adaptation_delay for o in rows])),
            "review_hours": _iv(mean_ci([o.review_hours for o in rows])),
            "irrelevant_units": round(fmean([o.irrelevant_units for o in rows]), 4),
            "false_alerts": (
                _iv(mean_ci([o.false_alerts for o in rows])) if condition == "acp" else None
            ),
        }

    acp, static, monthly = (results.outcomes[c] for c in ("acp", "static", "monthly"))
    dv_static, pos_static, n_static = paired_difference(acp, static)
    dv_monthly, pos_monthly, n_monthly = paired_difference(acp, monthly)
    table["paired"] = {
        "acp_minus_static_pp": _iv(dv_static),
        "acp_minus_static_positive": f"{pos_static}/{n_static}",
        "acp_minus_monthly_pp": _iv(dv_monthly),
        "acp_minus_monthly_positive": f"{pos_monthly}/{n_monthly}",
    }
    table["design"] = {
        "archetypes": len(ARCHETYPES),
        "replicates_per_archetype": len(results.outcomes["acp"]) // len(ARCHETYPES),
        "horizon_days": HORIZON_DAYS,
        "traces": results.n_traces,
        "enterprise_days": results.n_traces * HORIZON_DAYS,
        "labelled_material_events": labelled_event_count(
            len(results.outcomes["acp"]) // len(ARCHETYPES)
        ),
        "primary_seed": PRIMARY_SEED,
        "primary_tau": PRIMARY_TAU,
        "artifact_version": __version__,
        "capability_pack": CAPABILITY_PACK_VERSION,
        "scenario_pack": SCENARIO_PACK_VERSION,
    }
    return table


def _iv(interval: Interval) -> Dict[str, float]:
    return {
        "mean": round(interval.mean, 4),
        "ci_low": round(interval.low, 4),
        "ci_high": round(interval.high, 4),
        "n": interval.n,
    }


def run_sensitivity(
    taus: Sequence[float] = SENSITIVITY_TAUS,
    budget_factors: Sequence[float] = SENSITIVITY_BUDGET_FACTORS,
    replicates: int = SENSITIVITY_REPLICATES,
) -> List[Dict[str, float]]:
    """Cross thresholds with budget factors using fresh replicate indices."""
    rows: List[Dict[str, float]] = []
    for factor in budget_factors:
        for tau in taus:
            coverages: List[float] = []
            alerts: List[float] = []
            delays: List[float] = []
            for archetype in ARCHETYPES:
                for r in range(replicates):
                    replicate = SENSITIVITY_REPLICATE_OFFSET + r
                    trace = run_trace(
                        archetype,
                        replicate,
                        tau=tau,
                        budget_factor=factor,
                        conditions=("acp",),
                    )
                    outcome = summarise_trace(trace, "acp")
                    coverages.append(100 * outcome.mean_coverage)
                    alerts.append(outcome.false_alerts)
                    delays.append(outcome.adaptation_delay)
            rows.append(
                {
                    "budget_factor": factor,
                    "tau": tau,
                    "coverage_pct": round(fmean(coverages), 4),
                    "false_alerts": round(fmean(alerts), 4),
                    "adaptation_delay_days": round(fmean(delays), 4),
                    "modelled_daily_false_trigger_p": round(
                        false_trigger_probability(tau), 6
                    ),
                    # Design expectation of the disclosed nuisance process over
                    # days 1..119.  Reported next to the finite-sample value so
                    # that sampling noise at 30 traces is visible rather than
                    # mistaken for detector behaviour.
                    "expected_false_alerts": round(
                        (HORIZON_DAYS - 1) * false_trigger_probability(tau), 4
                    ),
                    "traces": len(coverages),
                }
            )
    return rows


# --------------------------------------------------------------------------
# Output writers
# --------------------------------------------------------------------------

TRACE_FIELDS = [
    "archetype",
    "replicate",
    "condition",
    "mean_coverage_pct",
    "p10_coverage_pct",
    "adaptation_delay_days",
    "review_hours",
    "false_alerts",
    "irrelevant_units",
    "reassessments",
]


def write_trace_csv(results: PrimaryResults, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=TRACE_FIELDS)
        writer.writeheader()
        for condition in CONDITIONS:
            for outcome in results.outcomes[condition]:
                writer.writerow(outcome.as_row())


def write_daily_coverage_csv(results: PrimaryResults, path: Path) -> None:
    from .metrics import daily_coverage

    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(["archetype", "replicate", "condition", "day", "coverage_pct"])
        for trace in results.traces:
            for condition in CONDITIONS:
                for day, value in enumerate(daily_coverage(trace, condition)):
                    writer.writerow(
                        [
                            trace.archetype,
                            trace.replicate,
                            condition,
                            day,
                            round(100 * value, 6),
                        ]
                    )


def write_sensitivity_csv(rows: Sequence[Dict[str, float]], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def write_summary_json(summary: Dict[str, object], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def format_primary_table(summary: Dict[str, object]) -> str:
    """Render Table 6 as plain text."""
    header = (
        f"{'Method':<16}{'Coverage %':>22}{'P10 %':>22}"
        f"{'Delay d':>20}{'Hours':>18}{'False alerts':>20}"
    )
    lines = [header, "-" * len(header)]
    for condition in CONDITIONS:
        row = summary[condition]
        false_alerts = row["false_alerts"]
        fa = (
            f"{false_alerts['mean']:.2f} [{false_alerts['ci_low']:.2f}, {false_alerts['ci_high']:.2f}]"
            if false_alerts
            else "N/A"
        )
        lines.append(
            f"{row['label']:<16}"
            f"{_fmt(row['mean_coverage_pct']):>22}"
            f"{_fmt(row['p10_coverage_pct']):>22}"
            f"{_fmt(row['adaptation_delay_days']):>20}"
            f"{_fmt(row['review_hours']):>18}"
            f"{fa:>20}"
        )
    paired = summary["paired"]
    lines.append("")
    lines.append(
        "Paired ACP-SME - static  : "
        f"{_fmt(paired['acp_minus_static_pp'])} pp, positive in "
        f"{paired['acp_minus_static_positive']} matched traces"
    )
    lines.append(
        "Paired ACP-SME - monthly : "
        f"{_fmt(paired['acp_minus_monthly_pp'])} pp, positive in "
        f"{paired['acp_minus_monthly_positive']} matched traces"
    )
    lines.append("")
    lines.append(
        "Mean irrelevant resource units: "
        + ", ".join(
            f"{CONDITION_LABELS[c]} {summary[c]['irrelevant_units']:.2f}" for c in CONDITIONS
        )
    )
    return "\n".join(lines)


def _fmt(interval: Dict[str, float]) -> str:
    return f"{interval['mean']:.2f} [{interval['ci_low']:.2f}, {interval['ci_high']:.2f}]"


def format_sensitivity_table(rows: Sequence[Dict[str, float]]) -> str:
    taus = sorted({row["tau"] for row in rows})
    factors = sorted({row["budget_factor"] for row in rows})
    index = {(row["budget_factor"], row["tau"]): row for row in rows}
    header = f"{'Budget factor':<15}" + "".join(f"{'cov@tau=' + str(t):>16}" for t in taus)
    lines = [header, "-" * len(header)]
    for factor in factors:
        cells = "".join(f"{index[(factor, t)]['coverage_pct']:>16.1f}" for t in taus)
        lines.append(f"{factor:<15.2f}{cells}")
    lines.append("")
    header2 = f"{'Budget factor':<15}" + "".join(f"{'alerts@tau=' + str(t):>16}" for t in taus)
    lines.append(header2)
    lines.append("-" * len(header2))
    for factor in factors:
        cells = "".join(f"{index[(factor, t)]['false_alerts']:>16.2f}" for t in taus)
        lines.append(f"{factor:<15.2f}{cells}")
    return "\n".join(lines)
