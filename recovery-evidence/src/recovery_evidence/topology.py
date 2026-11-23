"""Dependency maps, binary readiness functions and influence measures.

Section 3.2-3.3 of the manuscript.  A service is ready when every one of its
*requirement groups* contains at least one capable component.  A group with a
single member is a mandatory component; a group with several members is a
redundant set (the D/E pair in the reference map).

Everything in this module is deterministic, uses only the standard library and
is exact: static importance is returned as :class:`fractions.Fraction`.
"""
from __future__ import annotations

from dataclasses import dataclass
from fractions import Fraction
from functools import cached_property
from typing import Dict, List, Sequence, Tuple

Group = Tuple[str, ...]


@dataclass(frozen=True)
class DependencyMap:
    """A set of services over a fixed, alphabetically ordered component list."""

    components: Tuple[str, ...]
    services: Tuple[Tuple[str, Tuple[Group, ...]], ...]

    def __post_init__(self) -> None:
        if list(self.components) != sorted(self.components):
            raise ValueError("components must be in alphabetical order (tie-break rule)")
        if len(set(self.components)) != len(self.components):
            raise ValueError("duplicate component identifier")
        known = set(self.components)
        for name, groups in self.services:
            for group in groups:
                if not group or not set(group) <= known:
                    raise ValueError(f"service {name}: unknown or empty group {group}")

    # -- construction -----------------------------------------------------
    @classmethod
    def from_dict(cls, components: Sequence[str], services: Dict[str, Sequence[Sequence[str]]]) -> "DependencyMap":
        return cls(
            tuple(components),
            tuple((name, tuple(tuple(g) for g in groups)) for name, groups in services.items()),
        )

    def to_dict(self) -> dict:
        return {
            "components": list(self.components),
            "services": {name: [list(g) for g in groups] for name, groups in self.services},
        }

    # -- basic properties -------------------------------------------------
    @property
    def m(self) -> int:
        return len(self.components)

    @property
    def n_services(self) -> int:
        return len(self.services)

    @property
    def service_names(self) -> Tuple[str, ...]:
        return tuple(name for name, _ in self.services)

    def index(self, component: str) -> int:
        return self.components.index(component)

    def users(self, component: str) -> Tuple[str, ...]:
        """Services whose readiness function mentions ``component``."""
        return tuple(n for n, groups in self.services if any(component in g for g in groups))

    def shared_components(self) -> Tuple[str, ...]:
        return tuple(c for c in self.components if len(self.users(c)) >= 2)

    @cached_property
    def _group_indices(self) -> Tuple[Tuple[Tuple[int, ...], ...], ...]:
        return tuple(
            tuple(tuple(self.components.index(c) for c in g) for g in groups)
            for _, groups in self.services
        )

    # -- readiness (g_s) --------------------------------------------------
    def readiness(self, state: Sequence[int]) -> Tuple[int, ...]:
        """g_s(state) for every service; ``state`` is a 0/1 vector over components."""
        return tuple(
            int(all(any(state[i] for i in group) for group in groups))
            for groups in self._group_indices
        )

    # -- current influence (D_j) ------------------------------------------
    def influence(self, records: Sequence[int]) -> Tuple[int, ...]:
        """D_j(z): number of service verdicts that change when record j is reversed."""
        return self._influence_table[self._encode(records)]

    def _encode(self, state: Sequence[int]) -> int:
        code = 0
        for i, bit in enumerate(state):
            if bit:
                code |= 1 << i
        return code

    def _decode(self, code: int) -> Tuple[int, ...]:
        return tuple((code >> i) & 1 for i in range(self.m))

    @cached_property
    def _readiness_table(self) -> Tuple[Tuple[int, ...], ...]:
        return tuple(self.readiness(self._decode(v)) for v in range(1 << self.m))

    @cached_property
    def _influence_table(self) -> Tuple[Tuple[int, ...], ...]:
        table = self._readiness_table
        rows: List[Tuple[int, ...]] = []
        for v in range(1 << self.m):
            base = table[v]
            rows.append(
                tuple(
                    sum(abs(a - b) for a, b in zip(base, table[v ^ (1 << j)]))
                    for j in range(self.m)
                )
            )
        return tuple(rows)

    def readiness_fast(self, records: Sequence[int]) -> Tuple[int, ...]:
        """Table lookup equivalent of :meth:`readiness` (used in the simulation loop)."""
        return self._readiness_table[self._encode(records)]

    # -- static importance (c_j) ------------------------------------------
    @cached_property
    def static_importance(self) -> Tuple[Fraction, ...]:
        """c_j = 2^-m * sum over all states of D_j: summed Birnbaum structural importance."""
        n_states = 1 << self.m
        return tuple(
            Fraction(sum(row[j] for row in self._influence_table), n_states)
            for j in range(self.m)
        )


# ---------------------------------------------------------------------------
# Maps used in the study
# ---------------------------------------------------------------------------
def reference_map() -> DependencyMap:
    """Fig. 1 / Table 2: three services, eight components, A and F shared, D/E redundant."""
    return DependencyMap.from_dict(
        list("ABCDEFGH"),
        {
            "S1": [["A"], ["B"], ["D", "E"], ["F"]],
            "S2": [["A"], ["C"], ["D", "E"], ["F"]],
            "S3": [["A"], ["G"], ["H"]],
        },
    )


def operator_map_c8() -> DependencyMap:
    """Condition C8: the operator's map omits F from service S2."""
    return DependencyMap.from_dict(
        list("ABCDEFGH"),
        {
            "S1": [["A"], ["B"], ["D", "E"], ["F"]],
            "S2": [["A"], ["C"], ["D", "E"]],
            "S3": [["A"], ["G"], ["H"]],
        },
    )


def less_sharing_map_c9() -> DependencyMap:
    """Condition C9: S2 uses dedicated copies A2 and F2 (m = 10)."""
    return DependencyMap.from_dict(
        ["A", "A2", "B", "C", "D", "E", "F", "F2", "G", "H"],
        {
            "S1": [["A"], ["B"], ["D", "E"], ["F"]],
            "S2": [["A2"], ["C"], ["D", "E"], ["F2"]],
            "S3": [["A"], ["G"], ["H"]],
        },
    )


MAPS = {
    "reference": reference_map,
    "c8_operator_omits_F_from_S2": operator_map_c8,
    "c9_dedicated_A2_F2": less_sharing_map_c9,
}


def get_map(name: str) -> DependencyMap:
    try:
        return MAPS[name]()
    except KeyError as exc:  # pragma: no cover - configuration error
        raise KeyError(f"unknown dependency map {name!r}; known: {sorted(MAPS)}") from exc
