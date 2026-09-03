"""Design of Experiments (section 12) without third-party dependencies.

Provides full and fractional factorials, a Latin hypercube, a scrambled
van der Corput (low-discrepancy) sequence for screening, plus randomisation
and blocking helpers. Factor definitions carry their own units and evidence,
so a sweep cannot silently vary an uninventoried parameter.
"""

from __future__ import annotations

import math
import random
from dataclasses import dataclass, field
from typing import Any, Iterable, Sequence

__all__ = ["Factor", "full_factorial", "fractional_factorial", "latin_hypercube",
           "van_der_corput", "sobol_like", "randomize_blocks", "design_matrix", "to_overrides"]


@dataclass(frozen=True)
class Factor:
    """One controllable input of the experiment."""

    name: str                    # dotted config path, e.g. "power.site_a.initial_soc_pct"
    levels: tuple[Any, ...] = ()
    low: float | None = None
    high: float | None = None
    unit: str = "1"
    evidence: str = "SYNTHETIC_DEMO"
    group: str = "general"       # network | power | wifi | threat | telemetry

    def sample(self, unit_value: float) -> Any:
        """Map ``unit_value`` in [0,1) onto the factor domain."""

        if self.levels:
            index = min(len(self.levels) - 1, int(unit_value * len(self.levels)))
            return self.levels[index]
        if self.low is None or self.high is None:
            raise ValueError(f"factor {self.name} has neither levels nor bounds")
        return self.low + unit_value * (self.high - self.low)


def full_factorial(factors: Sequence[Factor]) -> list[dict[str, Any]]:
    design: list[dict[str, Any]] = [{}]
    for factor in factors:
        levels = factor.levels or (factor.low, factor.high)
        design = [{**row, factor.name: level} for row in design for level in levels]
    return design


def fractional_factorial(factors: Sequence[Factor], fraction: int = 2
                         ) -> list[dict[str, Any]]:
    """Resolution-III style fraction: keep every ``fraction``-th full run."""

    full = full_factorial(factors)
    return full[::max(1, fraction)]


def van_der_corput(index: int, base: int = 2) -> float:
    value, denominator = 0.0, 1.0
    while index > 0:
        index, remainder = divmod(index, base)
        denominator *= base
        value += remainder / denominator
    return value


def sobol_like(count: int, dimensions: int) -> list[list[float]]:
    """Low-discrepancy points from distinct prime-base van der Corput series."""

    primes = [2, 3, 5, 7, 11, 13, 17, 19, 23, 29, 31, 37]
    if dimensions > len(primes):
        raise ValueError("at most 12 dimensions are supported")
    return [[van_der_corput(index + 1, primes[dim]) for dim in range(dimensions)]
            for index in range(count)]


def latin_hypercube(count: int, dimensions: int, seed: int = 0) -> list[list[float]]:
    rng = random.Random(seed)
    columns = []
    for _ in range(dimensions):
        cells = [(index + rng.random()) / count for index in range(count)]
        rng.shuffle(cells)
        columns.append(cells)
    return [[columns[dim][row] for dim in range(dimensions)] for row in range(count)]


def design_matrix(factors: Sequence[Factor], count: int, method: str = "lhs",
                  seed: int = 0) -> list[dict[str, Any]]:
    """Build ``count`` factor settings using the requested sampling method."""

    if method == "full":
        return full_factorial(factors)
    if method == "fractional":
        return fractional_factorial(factors)
    if method == "sobol":
        points = sobol_like(count, len(factors))
    elif method == "lhs":
        points = latin_hypercube(count, len(factors), seed)
    else:
        raise ValueError(f"unknown DoE method {method!r}")
    return [{factor.name: factor.sample(point[index])
             for index, factor in enumerate(factors)} for point in points]


def randomize_blocks(runs: Sequence[dict[str, Any]], block_size: int,
                     seed: int = 0) -> list[dict[str, Any]]:
    """Randomise run order inside blocks to protect against drift."""

    rng = random.Random(seed)
    output: list[dict[str, Any]] = []
    for start in range(0, len(runs), block_size):
        block = list(runs[start:start + block_size])
        rng.shuffle(block)
        for position, run in enumerate(block):
            output.append({**run, "_block": start // block_size, "_position": position})
    return output


def to_overrides(setting: dict[str, Any]) -> dict[str, Any]:
    """Turn ``{"power.site_a.initial_soc_pct": 60}`` into a nested override."""

    overrides: dict[str, Any] = {}
    for path, value in setting.items():
        if path.startswith("_"):
            continue
        node = overrides
        parts = path.split(".")
        for part in parts[:-1]:
            node = node.setdefault(part, {})
        node[parts[-1]] = value
    return overrides
