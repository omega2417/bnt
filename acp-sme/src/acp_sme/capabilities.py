"""Capability layer of ACP-SME.

Implements Table A1 of the article: the 14 shared capabilities used by the
exact selector, with their dimensionless cost units, effectiveness
coefficients and prerequisite relations.

The cost and effectiveness values are *design values*.  They are transparent
prioritization parameters and must not be read as market prices or as observed
control performance.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, FrozenSet, Iterable, List, Sequence, Tuple

#: Version of the capability parameter pack (see R7, independent versioning).
CAPABILITY_PACK_VERSION = "cap-pack-0.1.0"


@dataclass(frozen=True)
class Capability:
    """A shared capability node of the typed capability graph."""

    code: str
    name: str
    cost: int
    effectiveness: float
    prerequisites: Tuple[str, ...] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        if self.cost <= 0:
            raise ValueError(f"{self.code}: cost units must be positive")
        if not 0.0 < self.effectiveness <= 1.0:
            raise ValueError(f"{self.code}: effectiveness must lie in (0, 1]")


#: Table A1.  Order is canonical and fixed: it defines the bit order used by
#: the exact selector and the column order of every emitted record.
CAPABILITIES: Tuple[Capability, ...] = (
    Capability("GOV", "Governance and risk", 4, 0.93, ()),
    Capability("AST", "Asset inventory", 3, 0.92, ()),
    Capability("IAM", "Identity and access", 5, 0.95, ("AST",)),
    Capability("DAT", "Data protection", 5, 0.94, ("AST",)),
    Capability("CFG", "Secure configuration", 4, 0.88, ("AST",)),
    Capability("TPR", "Supplier assurance", 4, 0.86, ("GOV",)),
    Capability("DET", "Logging and detection", 5, 0.90, ("AST",)),
    Capability("IR", "Incident response", 4, 0.87, ("GOV",)),
    Capability("REC", "Recovery and continuity", 4, 0.86, ("IR",)),
    Capability("CLD", "Cloud-edge security", 4, 0.88, ("IAM",)),
    Capability("XRI", "XR identity and virtual assets", 5, 0.91, ("IAM", "DAT")),
    Capability("DTI", "IoT and digital-twin integrity", 6, 0.93, ("DAT", "DET")),
    Capability("AIG", "AI service governance", 5, 0.89, ("GOV", "DAT")),
    Capability("TRN", "Awareness and role training", 3, 0.83, ("GOV",)),
)

CODES: Tuple[str, ...] = tuple(c.code for c in CAPABILITIES)
INDEX: Dict[str, int] = {code: i for i, code in enumerate(CODES)}
BY_CODE: Dict[str, Capability] = {c.code: c for c in CAPABILITIES}

#: Capabilities whose observation is subject to the modelled sensing
#: attenuation of Table A3 (immersive / twin / AI signals are the ones an SME
#: is least likely to observe reliably).
ATTENUATED_CODES: Tuple[str, ...] = ("XRI", "DTI", "AIG")

#: Total cost of implementing every capability, i.e. the unconstrained ceiling.
TOTAL_COST: int = sum(c.cost for c in CAPABILITIES)


def cost_of(codes: Iterable[str]) -> int:
    """Return the encoded resource-unit cost of a set of capability codes."""
    return sum(BY_CODE[code].cost for code in codes)


def effectiveness_of(code: str) -> float:
    return BY_CODE[code].effectiveness


def validate_prerequisites() -> None:
    """Fail closed if the pack declares an unknown or cyclic prerequisite."""
    for cap in CAPABILITIES:
        for prereq in cap.prerequisites:
            if prereq not in BY_CODE:
                raise ValueError(f"{cap.code}: unknown prerequisite {prereq!r}")
    # Depth-first cycle check over the prerequisite relation.
    state: Dict[str, int] = {code: 0 for code in CODES}

    def visit(code: str, path: List[str]) -> None:
        if state[code] == 1:
            raise ValueError("prerequisite cycle: " + " -> ".join(path + [code]))
        if state[code] == 2:
            return
        state[code] = 1
        for prereq in BY_CODE[code].prerequisites:
            visit(prereq, path + [code])
        state[code] = 2

    for code in CODES:
        visit(code, [])


def is_dependency_valid(codes: Iterable[str]) -> bool:
    """True when every selected capability has its prerequisites selected.

    This is the ``prereq(S) = 1`` predicate of Equation (4).
    """
    selected = set(codes)
    return all(
        set(BY_CODE[code].prerequisites) <= selected for code in selected
    )


def closure(codes: Iterable[str]) -> FrozenSet[str]:
    """Return ``codes`` extended with everything they transitively require."""
    pending = list(codes)
    out: set = set()
    while pending:
        code = pending.pop()
        if code in out:
            continue
        out.add(code)
        pending.extend(BY_CODE[code].prerequisites)
    return frozenset(out)


def dependency_valid_subsets() -> Tuple[FrozenSet[str], ...]:
    """Enumerate every prerequisite-closed subset of the 14 capabilities.

    The enumeration is exhaustive (2**14 candidates) and its result is the
    feasible region of Equation (4) before the budget constraint is applied.
    """
    subsets: List[FrozenSet[str]] = []
    n = len(CODES)
    for mask in range(1 << n):
        codes = frozenset(CODES[i] for i in range(n) if mask >> i & 1)
        if is_dependency_valid(codes):
            subsets.append(codes)
    return tuple(subsets)


def order(codes: Iterable[str]) -> Tuple[str, ...]:
    """Return capability codes in the canonical Table A1 order."""
    present = set(codes)
    return tuple(code for code in CODES if code in present)


def format_profile(codes: Sequence[str]) -> str:
    return "+".join(order(codes)) if codes else "(empty)"


validate_prerequisites()
