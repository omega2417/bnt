"""Resource-aware exact profile selector (Equations 3 and 4).

Utility of a candidate capability::

    U(c, t) = r(c, t) * e(c) - lambda * k(c)                        (3)

Selection::

    S*(t) = argmax_S sum_{c in S} U(c, t)
            subject to  sum_{c in S} k(c) <= B  and  prereq(S) = 1  (4)

The selector is *exact*: it enumerates every dependency-valid subset of the 14
capabilities and keeps the maximum-utility subset inside the budget.  Budget
feasibility and prerequisite satisfaction are therefore algorithmic invariants
of the returned profile, not empirical success rates.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, FrozenSet, Iterable, Mapping, Optional, Sequence, Tuple

from .capabilities import (
    BY_CODE,
    CODES,
    cost_of,
    dependency_valid_subsets,
    is_dependency_valid,
    order,
)

#: Parsimony penalty of Equation (3), per selected resource-cost unit (Table A3).
DEFAULT_LAMBDA = 0.002

#: Cached feasible region.  Independent of scenario, so computed once.
_VALID_SUBSETS: Optional[Tuple[FrozenSet[str], ...]] = None


def valid_subsets() -> Tuple[FrozenSet[str], ...]:
    global _VALID_SUBSETS
    if _VALID_SUBSETS is None:
        _VALID_SUBSETS = dependency_valid_subsets()
    return _VALID_SUBSETS


@dataclass(frozen=True)
class Selection:
    """Outcome of one exact selection."""

    capabilities: Tuple[str, ...]
    utility: float
    cost: int
    budget: int
    deferred: Tuple[str, ...]
    exception_queue: Tuple[str, ...] = ()

    @property
    def slack(self) -> int:
        return self.budget - self.cost


def utility(code: str, relevance: float, lam: float = DEFAULT_LAMBDA) -> float:
    """Equation (3) for a single capability."""
    cap = BY_CODE[code]
    return relevance * cap.effectiveness - lam * cap.cost


def select(
    relevance: Mapping[str, float],
    budget: int,
    lam: float = DEFAULT_LAMBDA,
    mandatory: Iterable[str] = (),
) -> Selection:
    """Solve Equation (4) exactly.

    Parameters
    ----------
    relevance:
        Context weight ``r(c, t)`` per capability code.  Missing codes are
        treated as zero relevance, never as "no risk known" (see R6: a missing
        connector must raise a verification task upstream, which is the
        detector's responsibility, not the selector's).
    budget:
        Approved resource-unit envelope ``B``.
    mandatory:
        Capabilities carrying a legal or contractual obligation.  They are
        forced into the profile together with their prerequisites.  When the
        forced set alone exceeds the budget the selector does not silently drop
        them: it returns them in ``exception_queue`` for human escalation.

    Ties are broken deterministically (lowest cost, then canonical code order)
    so that a replay of the same inputs yields the same profile.
    """
    if budget < 0:
        raise ValueError("budget must be non-negative")
    weights: Dict[str, float] = {code: float(relevance.get(code, 0.0)) for code in CODES}

    forced: FrozenSet[str] = frozenset()
    exception_queue: Tuple[str, ...] = ()
    if mandatory:
        from .capabilities import closure

        forced = closure(mandatory)
        if cost_of(forced) > budget:
            # R4/R5: an infeasible obligation is escalated, never discarded.
            exception_queue = order(forced)
            forced = frozenset()

    best_subset: FrozenSet[str] = frozenset()
    best_utility = float("-inf")
    best_cost = 0
    for subset in valid_subsets():
        if forced and not forced <= subset:
            continue
        cost = cost_of(subset)
        if cost > budget:
            continue
        total = sum(utility(code, weights[code], lam) for code in subset)
        if total > best_utility or (
            total == best_utility
            and (cost, order(subset)) < (best_cost, order(best_subset))
        ):
            best_subset, best_utility, best_cost = subset, total, cost

    deferred = tuple(
        code
        for code in order(set(CODES) - best_subset)
        if utility(code, weights[code], lam) > 0
    )
    return Selection(
        capabilities=order(best_subset),
        utility=best_utility,
        cost=best_cost,
        budget=budget,
        deferred=deferred,
        exception_queue=exception_queue,
    )


def explain(selection: Selection, relevance: Mapping[str, float]) -> Sequence[str]:
    """Human-readable justification lines for one selection (R3, R5)."""
    lines = [
        f"budget {selection.budget} units, allocated {selection.cost}, "
        f"slack {selection.slack}, utility {selection.utility:.4f}",
    ]
    for code in selection.capabilities:
        cap = BY_CODE[code]
        r = float(relevance.get(code, 0.0))
        lines.append(
            f"  selected {code:<3} {cap.name:<32} r={r:.2f} e={cap.effectiveness:.2f} "
            f"k={cap.cost} U={utility(code, r):+.4f}"
        )
    for code in selection.deferred:
        cap = BY_CODE[code]
        r = float(relevance.get(code, 0.0))
        lines.append(
            f"  deferred {code:<3} {cap.name:<32} r={r:.2f} k={cap.cost} "
            f"U={utility(code, r):+.4f} (not affordable within budget)"
        )
    for code in selection.exception_queue:
        lines.append(f"  EXCEPTION {code}: mandatory but not affordable; escalate")
    return lines


def assert_invariants(selection: Selection) -> None:
    """Check the two invariants claimed for the selector in Section 4.2."""
    if not is_dependency_valid(selection.capabilities):
        raise AssertionError(f"prerequisite violation: {selection.capabilities}")
    if selection.cost > selection.budget:
        raise AssertionError(
            f"budget violation: {selection.cost} > {selection.budget}"
        )
