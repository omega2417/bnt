"""Data-quality gates of section 15 plus the run invariants of section 5.3.

Gates return structured verdicts instead of printing: the runner stores them
in the manifest, the CLI prints them, and the Monte Carlo driver can discard a
replicate whose data would not survive review.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Iterable

from ..core.errors import GateFailure

__all__ = ["Gate", "GateResult", "DEFAULT_GATES", "run_gates", "step_invariants"]


@dataclass
class GateResult:
    name: str
    passed: bool
    value: Any
    threshold: Any
    detail: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {"gate": self.name, "passed": self.passed, "value": self.value,
                "threshold": self.threshold, "detail": self.detail}


@dataclass
class Gate:
    name: str
    check: Callable[[list[dict[str, Any]]], GateResult]
    blocking: bool = True


def _numbers(rows: list[dict[str, Any]], key: str) -> list[float]:
    values = []
    for row in rows:
        raw = row.get(key, "")
        if raw in ("", None):
            continue
        try:
            values.append(float(raw))
        except (TypeError, ValueError):
            continue
    return values


def gate_completeness(rows: list[dict[str, Any]], minimum_pct: float = 90.0) -> GateResult:
    if not rows:
        return GateResult("completeness", False, 0.0, minimum_pct, "no rows")
    present = sum(1 for row in rows if row.get("telemetry_gap_marker") in (0, "0"))
    pct = 100.0 * present / len(rows)
    return GateResult("completeness", pct >= minimum_pct, round(pct, 3), minimum_pct)


def gate_time_monotonic(rows: list[dict[str, Any]]) -> GateResult:
    """Steps must not go backwards inside one (replicate, site) series.

    Replicates are separate series concatenated into one file, so the counter
    legitimately restarts at each replicate boundary; only a regression inside
    a series is a defect.
    """

    per_series: dict[tuple[str, str], int] = {}
    violations = 0
    for row in rows:
        if "OUT_OF_ORDER" in str(row.get("quality_flags", "")):
            continue
        key = (str(row.get("replicate_id")), str(row.get("site_id")))
        step = int(row.get("step", 0))
        if key in per_series and step < per_series[key]:
            violations += 1
        per_series[key] = step
    return GateResult("time_monotonic", violations == 0, violations, 0,
                      "excluding rows explicitly flagged OUT_OF_ORDER")


def gate_duplicate_rate(rows: list[dict[str, Any]], maximum_pct: float = 5.0) -> GateResult:
    if not rows:
        return GateResult("duplicate_rate", False, 100.0, maximum_pct, "no rows")
    duplicates = sum(1 for row in rows if "DUPLICATE" in str(row.get("quality_flags", "")))
    pct = 100.0 * duplicates / len(rows)
    return GateResult("duplicate_rate", pct <= maximum_pct, round(pct, 3), maximum_pct)


def gate_soc_continuity(rows: list[dict[str, Any]],
                        max_step_pct: float = 0.5) -> GateResult:
    """State of charge must move smoothly inside each replicate.

    Replicates restart from the configured initial SoC, so the check runs per
    replicate; a jump across a replicate boundary is expected, a jump inside
    one is a modelling defect.
    """

    worst = 0.0
    series: dict[str, list[float]] = {}
    for row in rows:
        if row.get("site_id") != "site_a":
            continue
        raw = row.get("soc_pct", "")
        if raw in ("", None):
            continue
        series.setdefault(str(row.get("replicate_id")), []).append(float(raw))
    for values in series.values():
        worst = max([worst] + [abs(b - a) for a, b in zip(values, values[1:])])
    return GateResult("soc_continuity", worst <= max_step_pct, round(worst, 4), max_step_pct)


def gate_energy_sign(rows: list[dict[str, Any]]) -> GateResult:
    bad = 0
    for row in rows:
        state = str(row.get("charge_state", ""))
        current = row.get("pack_current_a", "")
        if current in ("", None):
            continue
        current = float(current)
        if state == "DISCHARGE" and current < -1e-9:
            bad += 1
        if state == "CHARGE" and current > 1e-9:
            bad += 1
    return GateResult("energy_sign", bad == 0, bad, 0,
                      "discharge must be positive current, charge negative")


def gate_voltage_consistency(rows: list[dict[str, Any]],
                             tolerance_v: float = 1e-3) -> GateResult:
    """Pack terminal voltage must lie inside the cell envelope.

    The tolerance absorbs CSV export rounding only (pack voltage is written
    with four decimals, cell voltages with five); it is far below any
    physically meaningful deviation.
    """

    bad = 0
    for row in rows:
        try:
            pack = float(row["pack_voltage_v"])
            cell_min = float(row["cell_min_v"])
            cell_max = float(row["cell_max_v"])
        except (KeyError, TypeError, ValueError):
            continue
        if not (13 * cell_min - tolerance_v <= pack <= 13 * cell_max + tolerance_v):
            bad += 1
    return GateResult("voltage_consistency", bad == 0, bad, 0,
                      "pack terminal voltage must lie between 13*Vcell_min and 13*Vcell_max")


def gate_gap_blanking(rows: list[dict[str, Any]]) -> GateResult:
    bad = 0
    for row in rows:
        if row.get("telemetry_gap_marker") in (1, "1"):
            if row.get("rtt_ms") not in ("", None) or row.get("detector_score") not in ("", None):
                bad += 1
    return GateResult("gap_blanking", bad == 0, bad, 0,
                      "gap rows must not carry measurements or detector output")


DEFAULT_GATES: tuple[Gate, ...] = (
    Gate("completeness", gate_completeness),
    Gate("time_monotonic", gate_time_monotonic),
    Gate("duplicate_rate", gate_duplicate_rate, blocking=False),
    Gate("soc_continuity", gate_soc_continuity),
    Gate("energy_sign", gate_energy_sign),
    Gate("voltage_consistency", gate_voltage_consistency),
    Gate("gap_blanking", gate_gap_blanking),
)


def run_gates(rows: list[dict[str, Any]], gates: Iterable[Gate] = DEFAULT_GATES,
              raise_on_block: bool = False) -> dict[str, Any]:
    results = [gate.check(rows) for gate in gates]
    blocking = {gate.name for gate in gates if gate.blocking}
    failed = [result for result in results if not result.passed and result.name in blocking]
    verdict = {
        "passed": not failed,
        "results": [result.to_dict() for result in results],
        "failed_blocking": [result.name for result in failed],
    }
    if failed and raise_on_block:
        raise GateFailure(f"blocking gates failed: {verdict['failed_blocking']}")
    return verdict


def step_invariants(result: dict[str, Any], orchestrator: Any) -> None:
    """Cheap per-step checks wired into the orchestrator."""

    power = result.get("power")
    if power:
        if not 0.0 <= power["soc_pct"] <= 100.0:
            raise GateFailure(f"SoC out of range: {power['soc_pct']}")
        if power["load_w"] < 0.0:
            raise GateFailure("negative retained load")
        if 1 in power.get("shed_groups", ()) and power["soc_pct"] > 5.0:
            raise GateFailure("group I shed above the safety limit")
    wifi = result.get("wifi", {})
    for site_id, row in wifi.items():
        if row["ap_online"] > row["ap_total"]:
            raise GateFailure(f"{site_id}: more APs online than installed")
