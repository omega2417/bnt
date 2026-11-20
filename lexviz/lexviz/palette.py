"""Palette validator with colour-vision-deficiency simulation.

Simulates protanopia, deuteranopia and tritanopia (Machado, Oliveira and
Fernandes 2009, severity 1.0) and checks that every pair of categorical
colours stays distinguishable (CIE76 ΔE in CIELAB).
"""
from __future__ import annotations

import itertools

from . import style

MACHADO = {
    "protanopia": ((0.152286, 1.052583, -0.204868), (0.114503, 0.786281, 0.099216), (-0.003882, -0.048116, 1.051998)),
    "deuteranopia": ((0.367322, 0.860646, -0.227968), (0.280085, 0.672501, 0.047413), (-0.011820, 0.042940, 0.968881)),
    "tritanopia": ((1.255528, -0.076749, -0.178779), (-0.078411, 0.930809, 0.147602), (0.004733, 0.691367, 0.303900)),
}


def _hex(c):
    c = c.lstrip("#")
    return tuple(int(c[i:i + 2], 16) / 255.0 for i in (0, 2, 4))


def _lin(v):
    return v / 12.92 if v <= 0.04045 else ((v + 0.055) / 1.055) ** 2.4


def _lab(rgb_lin):
    r, g, b = rgb_lin
    x = (0.4124 * r + 0.3576 * g + 0.1805 * b) / 0.95047
    y = 0.2126 * r + 0.7152 * g + 0.0722 * b
    z = (0.0193 * r + 0.1192 * g + 0.9505 * b) / 1.08883

    def f(t):
        return t ** (1 / 3.0) if t > 0.008856 else 7.787 * t + 16 / 116.0
    fx, fy, fz = f(x), f(y), f(z)
    return 116 * fy - 16, 500 * (fx - fy), 200 * (fy - fz)


def simulate(hex_colour, kind):
    lin = [_lin(v) for v in _hex(hex_colour)]
    if kind == "normal":
        return lin
    m = MACHADO[kind]
    return [max(0.0, min(1.0, sum(m[i][j] * lin[j] for j in range(3)))) for i in range(3)]


def delta_e(c1, c2, kind="normal"):
    a, b = _lab(simulate(c1, kind)), _lab(simulate(c2, kind))
    return sum((p - q) ** 2 for p, q in zip(a, b)) ** 0.5


def check(colours, min_de=12.0):
    """Return a list of (kind, c1, c2, ΔE) pairs that fall below ``min_de``."""
    bad = []
    for kind in ("normal",) + tuple(MACHADO):
        for c1, c2 in itertools.combinations(colours, 2):
            de = delta_e(c1, c2, kind)
            if de < min_de:
                bad.append((kind, c1, c2, round(de, 1)))
    return bad


PALETTES = {
    "provenance": lambda: list(style.PROV.values()),
    "mechanisms": lambda: list(style.MECH.values()),
    "criterion states": lambda: [style.STATE[k][0] for k in ("met", "largely_met", "partly_met", "not_met")],
}


def report(min_de=12.0):
    lines, ok = [], True
    for name, get in PALETTES.items():
        bad = check(get(), min_de)
        ok = ok and not bad
        worst = min(delta_e(a, b, k) for k in ("normal",) + tuple(MACHADO)
                    for a, b in itertools.combinations(get(), 2))
        lines.append("%-17s %s  (min ΔE = %.1f)" % (name, "OK" if not bad else "FAIL %s" % bad, worst))
    return ok, "\n".join(lines)


if __name__ == "__main__":
    print(report()[1])
