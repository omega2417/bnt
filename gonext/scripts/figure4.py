#!/usr/bin/env python3
"""Figure 4: measurements of generated code (medians of ten runs, error
bars = interquartile range): (a) construction time per value, (b) match
time per value, (c) memory per value (R1 split into slice part and hatched
heap part), (d) named/default arguments vs. two idiomatic emulations.

Reads results/bench_summary.csv (run analyze_bench.py first) and writes
figures/figure4.pdf and figures/figure4.png.
"""
import csv
import os

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BLUE, ORANGE, GREEN, LIGHT = "#2f6fd6", "#ec6a37", "#1fae7a", "#a3c4f0"
REPS = [("R1 interface", "R1_interface", BLUE),
        ("R2 flat struct", "R2_flat", ORANGE),
        ("R3 compact struct", "R3_compact", GREEN)]


def load():
    S = {}
    with open(os.path.join(ROOT, "results", "bench_summary.csv")) as f:
        for r in csv.DictReader(f):
            S[(r["benchmark"], r["metric"])] = tuple(float(r[k]) for k in ("median", "q25", "q75"))
    return S


def bars(ax, labels, stats, colors, unit, title, xlabel, extra=None):
    y = np.arange(len(labels))
    med = np.array([s[0] for s in stats])
    err = np.array([[s[0] - s[1] for s in stats], [s[2] - s[0] for s in stats]])
    ax.barh(y, med, color=colors, height=0.55)
    ax.errorbar(med, y, xerr=err, fmt="none", ecolor="#333333", capsize=3, lw=1)
    xmax = max(s[2] for s in stats)
    for i, s in enumerate(stats):
        lab = f"{s[0]:.1f} {unit}"
        if extra and extra[i]:
            lab += "\n" + extra[i]
        ax.text(s[2] + 0.02 * xmax, i, lab, va="center", fontsize=8)
    ax.set_yticks(y, labels)
    ax.invert_yaxis()
    ax.set_xlim(0, xmax * 1.35)
    ax.set_title(title)
    ax.set_xlabel(xlabel)
    ax.spines[["top", "right"]].set_visible(False)


def main():
    S = load()
    plt.rcParams.update({"font.size": 9, "font.family": "serif", "hatch.color": BLUE})
    fig, axs = plt.subplots(2, 2, figsize=(10, 6.2))
    labels = [r[0] for r in REPS]
    colors = [r[2] for r in REPS]

    bars(axs[0, 0], labels, [S[(f"BenchmarkConstruct/{k}", "ns/value")] for _, k, _ in REPS],
         colors, "ns", "(a) Building variant values", "Construction time per value (ns)")
    bars(axs[0, 1], labels, [S[(f"BenchmarkMatch/{k}", "ns/value")] for _, k, _ in REPS],
         colors, "ns", "(b) Exhaustive match over variants", "Match time per value (ns)")

    ax = axs[1, 0]
    y = np.arange(len(REPS))
    sl = np.array([S[(f"BenchmarkMemory/{k}", "B/value-slice")][0] for _, k, _ in REPS])
    hp = np.array([S[(f"BenchmarkMemory/{k}", "B/value-heap")][0] for _, k, _ in REPS])
    ax.barh(y, sl, color=colors, height=0.55)
    ax.barh(y, hp, left=sl, color="white", edgecolor=colors, hatch="////", height=0.55, lw=1)
    for i in range(len(REPS)):
        lab = f"{sl[i]:.0f} B in slice"
        if hp[i] > 0.05:
            lab = f"{sl[i]:.0f} B in slice + {hp[i]:.1f} B on heap"
        ax.text(sl[i] + hp[i] + 2, i, lab, va="center", fontsize=8)
    ax.set_yticks(y, labels)
    ax.invert_yaxis()
    ax.set_xlim(0, max(sl + hp) * 1.45)
    ax.set_title("(c) Footprint per variant value")
    ax.set_xlabel("Memory per value (bytes)")
    ax.spines[["top", "right"]].set_visible(False)

    na = [("GoNext lowering\n(positional call)", "GoNext_positional", BLUE),
          ("Config struct\n(idiomatic Go)", "Config_struct", LIGHT),
          ("Functional options\n(idiomatic Go)", "Functional_options", LIGHT)]
    extra = []
    for _, k, _ in na:
        a = S[(f"BenchmarkNamedArgs/{k}", "allocs/op")][0]
        extra.append(f"{a:.0f} alloc./call" if a > 0 else "")
    bars(axs[1, 1], [n[0] for n in na], [S[(f"BenchmarkNamedArgs/{k}", "ns/op")] for _, k, _ in na],
         [n[2] for n in na], "ns", "(d) Named and default arguments", "Time per call (ns)",
         extra=extra)

    fig.tight_layout()
    out = os.path.join(ROOT, "figures")
    os.makedirs(out, exist_ok=True)
    fig.savefig(os.path.join(out, "figure4.pdf"))
    fig.savefig(os.path.join(out, "figure4.png"), dpi=200)
    print("wrote figures/figure4.pdf, figures/figure4.png")


if __name__ == "__main__":
    main()
