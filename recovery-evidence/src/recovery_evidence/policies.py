"""Verification policies P0-P3 (Section 3.3, Table 3).

A policy is a pure function of what the operator can see: the public
dependency map, the stored check results ``z``, the evidence ages ``a`` and the
notice flags ``n``.  Nothing in this module can reach a hidden state.

Priorities are exact: P0, P1 and P3 are integers, P2 is a
:class:`fractions.Fraction`, so ties are decided by the documented rule
(alphabetically first identifier) and never by floating-point rounding.
"""
from __future__ import annotations

from fractions import Fraction
from typing import Callable, Dict, Sequence, Tuple, Union

from .topology import DependencyMap

Number = Union[int, Fraction]
POLICIES: Tuple[str, ...] = ("P0", "P1", "P2", "P3")
POLICY_LABELS: Dict[str, str] = {
    "P0": "age",
    "P1": "event-driven",
    "P2": "static importance",
    "P3": "current influence",
}


def urgency(ages: Sequence[int], notices: Sequence[int], w: int) -> Tuple[int, ...]:
    """u_j = 1 + a_j + w * n_j."""
    return tuple(1 + a + w * n for a, n in zip(ages, notices))


def priorities(
    policy: str,
    dep_map: DependencyMap,
    records: Sequence[int],
    ages: Sequence[int],
    notices: Sequence[int],
    w: int,
) -> Tuple[Number, ...]:
    """Priority of every component under ``policy`` (Table 3)."""
    if policy == "P0":
        return tuple(1 + a for a in ages)
    u = urgency(ages, notices, w)
    if policy == "P1":
        return u
    if policy == "P2":
        c = dep_map.static_importance
        return tuple((1 + c[j]) * u[j] for j in range(dep_map.m))
    if policy == "P3":
        d = dep_map.influence(records)
        return tuple((1 + d[j]) * u[j] for j in range(dep_map.m))
    raise ValueError(f"unknown policy {policy!r}")


def select(priority: Sequence[Number], excluded: Sequence[int] = ()) -> int:
    """Index of the largest priority; ties go to the lowest index.

    Components are stored in alphabetical order, so the lowest index is the
    alphabetically first identifier.  ``excluded`` holds components already
    checked today (a component is checked at most once per day).
    """
    best = -1
    for j, value in enumerate(priority):
        if j in excluded:
            continue
        if best < 0 or value > priority[best]:
            best = j
    if best < 0:
        raise ValueError("no component left to select")
    return best


PriorityFn = Callable[[DependencyMap, Sequence[int], Sequence[int], Sequence[int], int], Tuple[Number, ...]]
