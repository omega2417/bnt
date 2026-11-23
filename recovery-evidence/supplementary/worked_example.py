#!/usr/bin/env python3
"""Dependency-free check of the worked example, the static importances and the
two audit cases (Sections 3.3-3.4 and Appendix A).

Needs only the Python standard library and shares no code with the simulation
package, so it is an independent second implementation of the formulas:

    python worked_example.py

Exit status 0 means every printed value equals the value in the manuscript.
"""
from fractions import Fraction
from itertools import product

COMPONENTS = "ABCDEFGH"
W = 7  # notice weight


def g(x):
    """Readiness of S1, S2, S3 (Section 3.2)."""
    A, B, C, D, E, F, G, H = x
    return (A * B * max(D, E) * F, A * C * max(D, E) * F, A * G * H)


def flip(x, j):
    return x[:j] + (1 - x[j],) + x[j + 1:]


def influence(z):
    """D_j(z): number of verdicts that change when record j is reversed."""
    return tuple(sum(abs(a - b) for a, b in zip(g(z), g(flip(z, j)))) for j in range(8))


def static_importance():
    """c_j: mean of D_j over all 256 states (exact)."""
    states = list(product((0, 1), repeat=8))
    return tuple(Fraction(sum(influence(v)[j] for v in states), len(states)) for j in range(8))


def argmax_first(values):
    """Largest value; ties go to the alphabetically first component."""
    return max(range(len(values)), key=lambda j: (values[j], -j))


def main():
    ok = True

    def expect(label, got, want):
        nonlocal ok
        good = got == want
        ok &= good
        print(f"  [{'ok' if good else 'MISMATCH'}] {label}: {got}")

    z = (1, 1, 1, 0, 1, 1, 1, 1)
    ages = (3, 10, 4, 8, 2, 1, 2, 9)
    n = (0, 0, 0, 0, 1, 0, 0, 0)

    print("Section 3.3-3.4")
    u = tuple(1 + a + W * f for a, f in zip(ages, n))
    d = influence(z)
    c = static_importance()
    expect("urgency u", u, (4, 11, 5, 9, 10, 2, 3, 10))
    expect("current influence D(z)", d, (3, 1, 1, 0, 2, 2, 1, 1))
    expect("static importance c", tuple(float(v) for v in c),
           (0.625, 0.1875, 0.1875, 0.125, 0.125, 0.375, 0.25, 0.25))
    p0 = tuple(1 + a for a in ages)
    p1 = u
    p2 = tuple((1 + c[j]) * u[j] for j in range(8))
    p3 = tuple((1 + d[j]) * u[j] for j in range(8))
    expect("P3 priorities", p3, (16, 22, 10, 9, 30, 6, 6, 20))
    expect("P2 priorities of B, E, H", (float(p2[1]), float(p2[4]), float(p2[7])), (13.0625, 11.25, 12.5))
    picks = "".join(COMPONENTS[argmax_first(p)] for p in (p0, p1, p2, p3))
    expect("selections of P0, P1, P2, P3", picks, "BBBE")

    print("Appendix A")
    for name, hidden, want_truth, want_fa, want_diff in (
        ("case I  (E = 0)", (1, 1, 1, 0, 0, 1, 1, 1), (0, 0, 1), (2, 0), "-66.67"),
        ("case II (B = 0)", (1, 0, 1, 0, 1, 1, 1, 1), (0, 1, 1), (0, 1), "+33.33"),
    ):
        truth = g(hidden)
        fa = []
        for pr in (p1, p3):
            j = argmax_first(pr)
            record = z[:j] + (hidden[j],) + z[j + 1:]
            fa.append(sum(1 for v, y in zip(g(record), truth) if v == 1 and y == 0))
        diff = f"{100 * (fa[1] - fa[0]) / 3:+.2f}"
        expect(f"{name} true readiness", truth, want_truth)
        expect(f"{name} falsely assured services P1 / P3", tuple(fa), want_fa)
        expect(f"{name} paired difference per 100 service-days", diff, want_diff)

    print("all values agree with the manuscript" if ok else "MISMATCH FOUND")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
