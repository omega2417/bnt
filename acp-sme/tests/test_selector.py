"""R4: budget, dependency and exception-queue tests for the exact selector."""

import pytest

from acp_sme.capabilities import CODES, TOTAL_COST, cost_of, is_dependency_valid
from acp_sme.scenarios import ARCHETYPES
from acp_sme.selector import DEFAULT_LAMBDA, assert_invariants, select, utility


def test_budget_is_never_exceeded():
    for archetype in ARCHETYPES:
        for day in range(0, 120, 7):
            selection = select(archetype.demand_at(day), archetype.budget)
            assert selection.cost <= archetype.budget
            assert_invariants(selection)


def test_prerequisites_always_satisfied():
    for archetype in ARCHETYPES:
        for day in (0, 45, 119):
            selection = select(archetype.demand_at(day), archetype.budget)
            assert is_dependency_valid(selection.capabilities)


def test_zero_budget_yields_empty_profile():
    selection = select({code: 1.0 for code in CODES}, 0)
    assert selection.capabilities == ()
    assert selection.cost == 0


def test_unlimited_budget_selects_every_useful_capability():
    selection = select({code: 1.0 for code in CODES}, TOTAL_COST)
    assert set(selection.capabilities) == set(CODES)


def test_zero_relevance_capability_is_not_selected_when_penalised():
    # With no demand at all, every utility is negative, so the empty profile wins.
    selection = select({code: 0.0 for code in CODES}, TOTAL_COST)
    assert selection.capabilities == ()


def test_selection_is_optimal_against_brute_force():
    relevance = {code: (i % 5) / 4.0 for i, code in enumerate(CODES)}
    budget = 20
    chosen = select(relevance, budget)
    from acp_sme.selector import valid_subsets

    best = max(
        (
            sum(utility(c, relevance[c]) for c in s)
            for s in valid_subsets()
            if cost_of(s) <= budget
        )
    )
    assert chosen.utility == pytest.approx(best)


def test_selection_is_deterministic():
    relevance = {code: 0.5 for code in CODES}
    assert select(relevance, 25).capabilities == select(relevance, 25).capabilities


def test_mandatory_capability_is_forced_with_its_prerequisites():
    relevance = {code: 0.0 for code in CODES}
    relevance["GOV"] = 0.1
    selection = select(relevance, 30, mandatory=["XRI"])
    assert {"XRI", "IAM", "DAT", "AST"} <= set(selection.capabilities)
    assert selection.exception_queue == ()


def test_infeasible_mandatory_capability_goes_to_the_exception_queue():
    # XRI closure costs 18 units; a budget of 5 cannot hold it.
    selection = select({code: 1.0 for code in CODES}, 5, mandatory=["XRI"])
    assert selection.exception_queue  # escalated, not silently dropped
    assert "XRI" in selection.exception_queue
    assert selection.cost <= 5


def test_parsimony_penalty_breaks_marginal_ties():
    # A capability whose demand barely exceeds the penalty is still worth taking;
    # one below it is not.
    below = DEFAULT_LAMBDA * 3 / 0.92 - 1e-6
    assert utility("AST", below) < 0
    assert utility("AST", below + 1e-3) > 0
