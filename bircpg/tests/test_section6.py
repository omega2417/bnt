"""Section 6 is the manuscript's own published arithmetic: every number must match."""

from fractions import Fraction

import pytest

from bircpg.section6 import build_game, equation15, summary, table2
from bircpg.equilibria import price_of_anarchy, pure_nash_equilibria, verify_exact_potential


#: Table 2 exactly as printed in the manuscript.
TABLE2 = {
    "(A, A)": {"u_1": 3, "u_2": 2, "welfare": 5, "potential": 9, "nash_gap": 3, "is_pne": False},
    "(A, B)": {"u_1": 7, "u_2": 5, "welfare": 12, "potential": 12, "nash_gap": 0, "is_pne": True},
    "(B, A)": {"u_1": 4, "u_2": 6, "welfare": 10, "potential": 10, "nash_gap": 0, "is_pne": True},
    "(B, B)": {"u_1": 1, "u_2": 2, "welfare": 3, "potential": 6, "nash_gap": 6, "is_pne": False},
}


def test_table2_matches_the_manuscript_exactly():
    rows = {r["profile"]: r for r in table2()}
    assert set(rows) == set(TABLE2)
    for name, expected in TABLE2.items():
        for key, value in expected.items():
            assert rows[name][key] == value, f"{name}.{key}"


def test_every_value_is_exact_rational_not_float():
    for row in table2():
        for key in ("u_1", "u_2", "welfare", "potential", "nash_gap"):
            assert isinstance(row[key], (int, Fraction)), f"{key} became a float"


def test_price_of_anarchy_is_six_fifths():
    game = build_game()
    poa = price_of_anarchy(game, active_only=True)
    assert poa == Fraction(6, 5)
    assert float(poa) == pytest.approx(1.2)


def test_the_two_equilibria_have_welfare_twelve_and_ten():
    game = build_game()
    equilibria = pure_nash_equilibria(game, active_only=True)
    assert sorted(game.welfare(a) for a in equilibria) == [10, 12]


def test_additive_welfare_loss_is_two_utility_units():
    assert summary()["additive_welfare_loss"] == 2


def test_agent1_switch_from_AA_to_BA_raises_payoff_3_to_4_and_potential_9_to_10():
    """The worked step quoted in Section 6."""
    from bircpg.section6 import A1, B1

    game = build_game()
    before, after = (A1, A1), (B1, A1)
    assert game.payoff(0, before) == 3 and game.payoff(0, after) == 4
    assert game.potential(before) == 9 and game.potential(after) == 10


def test_all_eight_nontrivial_unilateral_changes_satisfy_equation_6():
    game = build_game()
    check = verify_exact_potential(game, active_only=True)
    assert check.deviations_checked == 8
    assert check.exact


def test_equation15_values():
    """0.04192, 0.84203, 0.11396, 0.00209 at tau = 1 with uniform references."""
    pi = equation15(1.0)
    assert pi["(A, A)"] == pytest.approx(0.04192, abs=5e-6)
    assert pi["(A, B)"] == pytest.approx(0.84203, abs=5e-6)
    assert pi["(B, A)"] == pytest.approx(0.11396, abs=5e-6)
    assert pi["(B, B)"] == pytest.approx(0.00209, abs=5e-6)
    assert sum(pi.values()) == pytest.approx(1.0)


def test_the_outside_action_adds_no_equilibrium():
    """Every active payoff is positive, so an inactive agent can profitably enter."""
    game = build_game()
    full = pure_nash_equilibria(game, active_only=False)
    active = pure_nash_equilibria(game, active_only=True)
    assert len(full) == len(active) == 2
