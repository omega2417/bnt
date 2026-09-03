"""Cell-level model of the 13S x P design profile (section 9.8).

``13S x P`` is a *design profile*, not an identified battery: ``P`` and the
chemistry are unknown, and the OCV curve below is an explicitly conditional
synthetic surrogate. Nothing here may be promoted to HIL before a datasheet
replaces it.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

__all__ = ["Cell", "CellStack", "SYNTHETIC_OCV_CURVE"]

#: (SoC fraction, open-circuit volts) - synthetic_demo_conditional
SYNTHETIC_OCV_CURVE = ((0.00, 3.00), (0.05, 3.30), (0.15, 3.52), (0.30, 3.62),
                       (0.50, 3.70), (0.70, 3.83), (0.85, 3.98), (0.95, 4.10),
                       (1.00, 4.18))


def synthetic_ocv(soc_fraction: float, temp_c: float = 25.0) -> float:
    """Piecewise-linear OCV with a small thermal term; uncalibrated."""

    soc = max(0.0, min(1.0, soc_fraction))
    for (x0, y0), (x1, y1) in zip(SYNTHETIC_OCV_CURVE, SYNTHETIC_OCV_CURVE[1:]):
        if soc <= x1:
            span = 0.0 if x1 == x0 else (soc - x0) / (x1 - x0)
            base = y0 + span * (y1 - y0)
            break
    else:  # pragma: no cover - soc clamped above
        base = SYNTHETIC_OCV_CURVE[-1][1]
    return base + 0.0004 * (temp_c - 25.0)


@dataclass
class Cell:
    index: int
    soc_fraction: float = 0.82
    imbalance_v: float = 0.0            # additive offset from the stack mean
    resistance_ohm: float = 0.0069      # per-cell share of the pack resistance

    def ocv(self, temp_c: float) -> float:
        return synthetic_ocv(self.soc_fraction, temp_c) + self.imbalance_v

    def terminal(self, current_a: float, temp_c: float) -> float:
        """Positive current discharges, negative charges."""

        return self.ocv(temp_c) - current_a * self.resistance_ohm


@dataclass
class CellStack:
    series_count: int = 13
    cells: list[Cell] = field(default_factory=list)
    evidence_status: str = "SYNTHETIC_DEMO_ONLY_UNVERIFIED"

    def __post_init__(self) -> None:
        if not self.cells:
            self.cells = [Cell(index) for index in range(self.series_count)]

    def set_soc(self, soc_fraction: float) -> None:
        for cell in self.cells:
            cell.soc_fraction = max(0.0, min(1.0, soc_fraction))

    def apply_imbalance(self, cell_index: int, delta_mv: float) -> None:
        for cell in self.cells:
            cell.imbalance_v = 0.0
        if 0 <= cell_index < len(self.cells):
            self.cells[cell_index].imbalance_v = -abs(delta_mv) / 1000.0

    def pack_ocv(self, temp_c: float) -> float:
        return sum(cell.ocv(temp_c) for cell in self.cells)

    def pack_resistance(self) -> float:
        return sum(cell.resistance_ohm for cell in self.cells)

    def terminals(self, current_a: float, temp_c: float) -> list[float]:
        return [cell.terminal(current_a, temp_c) for cell in self.cells]

    def summary(self, current_a: float, temp_c: float) -> dict[str, Any]:
        ocvs = [cell.ocv(temp_c) for cell in self.cells]
        terminals = self.terminals(current_a, temp_c)
        return {
            "pack_ocv_v": sum(ocvs),
            "pack_voltage_v": sum(terminals),
            "cell_ocv_min_v": min(ocvs),
            "cell_ocv_max_v": max(ocvs),
            "cell_min_v": min(terminals),
            "cell_max_v": max(terminals),
            "cell_imbalance_mv": (max(ocvs) - min(ocvs)) * 1000.0,
            "evidence_status": self.evidence_status,
        }
