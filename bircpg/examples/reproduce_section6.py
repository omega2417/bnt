#!/usr/bin/env python3
"""Reproduce every claim of Section 6 from the manuscript's stated parameters.

The manuscript notes that the arithmetic of Section 6 can be reproduced directly
from its parameters and Equations (3)-(5).  This script does exactly that, in
exact rational arithmetic, and checks each printed value against the published
table so that a mismatch is an error rather than something a reader has to spot.

    python examples/reproduce_section6.py
"""

from __future__ import annotations

import sys
from fractions import Fraction

from bircpg.equilibria import price_of_anarchy, pure_nash_equilibria, verify_exact_potential
from bircpg.section6 import build_game, equation15, format_table2, table2

PUBLISHED_TABLE2 = {
    "(A, A)": (3, 2, 5, 9, 3, False),
    "(A, B)": (7, 5, 12, 12, 0, True),
    "(B, A)": (4, 6, 10, 10, 0, True),
    "(B, B)": (1, 2, 3, 6, 6, False),
}
PUBLISHED_EQ15 = {"(A, A)": 0.04192, "(A, B)": 0.84203, "(B, A)": 0.11396, "(B, B)": 0.00209}


def main() -> int:
    game = build_game()
    failures = []

    print(format_table2())
    print()
    for row in table2():
        expected = PUBLISHED_TABLE2[row["profile"]]
        actual = (
            row["u_1"], row["u_2"], row["welfare"],
            row["potential"], row["nash_gap"], row["is_pne"],
        )
        if actual != expected:
            failures.append(f"Table 2 row {row['profile']}: {actual} != {expected}")

    check = verify_exact_potential(game)
    print(check)
    if not check.exact:
        failures.append(f"Equation (6) residual {check.max_residual} is not zero")

    poa = price_of_anarchy(game, active_only=True)
    equilibria = pure_nash_equilibria(game, active_only=True)
    welfare = sorted(game.welfare(a) for a in equilibria)
    print(f"pure equilibria: {len(equilibria)}, welfare {[str(w) for w in welfare]}")
    print(f"price of anarchy (this instance only): {poa} = {float(poa)}")
    if poa != Fraction(6, 5):
        failures.append(f"price of anarchy {poa} != 6/5")
    if welfare != [10, 12]:
        failures.append(f"equilibrium welfare {welfare} != [10, 12]")

    print()
    pi = equation15(1.0)
    for name, value in pi.items():
        published = PUBLISHED_EQ15[name]
        print(f"pi{name} = {value:.5f}   (manuscript: {published})")
        if abs(value - published) > 5e-6:
            failures.append(f"Equation (15) {name}: {value:.5f} != {published}")

    print()
    if failures:
        print("MISMATCHES against the published manuscript:")
        for line in failures:
            print(f"  - {line}")
        return 1
    print("Every value matches the manuscript exactly.")
    print()
    print("This is an exact arithmetic illustration, not a simulation and not a")
    print("measurement.  The two pure equilibria have welfare 12 and 10, so an")
    print("equilibrium certificate alone does not identify the best allocation.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
