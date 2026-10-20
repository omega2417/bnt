#!/usr/bin/env python3
"""Statistics of the micro-experiments (Section 3.4, Table 6; Section 3.5,
Table 7).

Inputs:  results/raw/bench.txt (go test -bench output, -count=10)
         results/raw/pointervis.csv (mode,trial,finalized,nodes)
Outputs: results/bench_summary.csv  median and IQR of every benchmark/metric
         results/table6.csv, results/table6.md
         results/table7.csv, results/table7.md

The median and the 25th/75th percentiles use numpy's default (linear)
interpolation.
"""
import csv
import os
import re
import sys
from collections import defaultdict

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RAW = os.path.join(ROOT, "results", "raw")
RES = os.path.join(ROOT, "results")
N_VALUES = 65536  # Experiment 1 workload size

LINE = re.compile(r"^(Benchmark\S+?)(?:-\d+)?\s+(\d+)\s+(.*)$")


def parse_bench(path):
    """Return {(package, benchmark): {unit: [values...]}}."""
    data = defaultdict(lambda: defaultdict(list))
    pkg = ""
    with open(path) as f:
        for line in f:
            line = line.rstrip("\n")
            if line.startswith("pkg: "):
                pkg = line[5:].strip().rsplit("/", 1)[-1]
                continue
            m = LINE.match(line)
            if not m:
                continue
            name, rest = m.group(1), m.group(3).split()
            for v, u in zip(rest[0::2], rest[1::2]):
                data[(pkg, name)][u].append(float(v))
    return data


def stats(xs):
    a = np.asarray(xs, dtype=float)
    return (float(np.median(a)), float(np.percentile(a, 25)),
            float(np.percentile(a, 75)), len(a))


def summarize(data):
    rows = []
    for (pkg, name), units in sorted(data.items()):
        for unit, xs in units.items():
            med, q25, q75, n = stats(xs)
            rows.append({"package": pkg, "benchmark": name, "metric": unit,
                         "median": med, "q25": q25, "q75": q75, "n": n,
                         "min": min(xs), "max": max(xs)})
    return rows


def fmt(x, nd=1):
    return f"{x:.{nd}f}"


def num(x):
    """Compact number: integers without decimals."""
    return f"{x:.0f}" if abs(x - round(x)) < 1e-9 else f"{x:.2f}"


def table6(S):
    def g(name, unit):
        k = (name, unit)
        if k not in S:
            sys.exit(f"missing benchmark {name} [{unit}] in bench.txt")
        return S[k]

    rows = []

    def add(label, name, tunit, scale, shown_unit, allocs, memory, nd=1):
        med, q25, q75 = (v * scale for v in g(name, tunit)[:3])
        rows.append({
            "benchmark": label,
            "time_median": round(med, 4), "time_q25": round(q25, 4),
            "time_q75": round(q75, 4), "time_unit": shown_unit,
            "time": f"{fmt(med, nd)} [{fmt(q25, nd)}–{fmt(q75, nd)}] {shown_unit}",
            "allocations": allocs, "memory": memory,
        })

    reps = [("R1 interface", "R1_interface"), ("R2 flat struct", "R2_flat"),
            ("R3 compact struct", "R3_compact")]
    for label, key in reps:
        allocs_v = g(f"BenchmarkMemory/{key}", "allocs/value")[0]
        slice_b = g(f"BenchmarkMemory/{key}", "B/value-slice")[0]
        heap_b = g(f"BenchmarkMemory/{key}", "B/value-heap")[0]
        mem = f"{num(slice_b)} B" + (f" + {heap_b:.1f} B heap" if heap_b > 0.05 else "")
        alloc_s = f"{allocs_v:.0f} per value" if allocs_v > 0.05 else "0"
        add(f"Enum construction, {label}", f"BenchmarkConstruct/{key}", "ns/value", 1,
            "ns/value", alloc_s, mem)
    for label, key in reps:
        a = g(f"BenchmarkMatch/{key}", "allocs/op")[0]
        add(f"Exhaustive match, {label.split()[0]}", f"BenchmarkMatch/{key}", "ns/value", 1,
            "ns/value", num(a), "–")
    for label, key in [("GoNext lowering", "GoNext_positional"),
                       ("configuration struct", "Config_struct"),
                       ("functional options", "Functional_options")]:
        n = f"BenchmarkNamedArgs/{key}"
        add(f"Named/default call, {label}", n, "ns/op", 1, "ns/call",
            num(g(n, "allocs/op")[0]), f"{num(g(n, 'B/op')[0])} B")

    def kib(b):
        return f"{b / 1024:.0f} KiB" if b >= 1024 else f"{num(b)} B"

    for label, n in [("Generic method + lambda (4096 elements)",
                      "BenchmarkMap/GoNext_generic_method"),
                     ("Hand-written loop (4096 elements)", "BenchmarkMap/Handwritten_loop")]:
        add(label, n, "ns/op", 1e-3, "µs", num(g(n, "allocs/op")[0]), kib(g(n, "B/op")[0]), nd=2)
    for label, n in [("Extension method sum (4096 elements)",
                      "BenchmarkSum/GoNext_extension_method"),
                     ("Hand-written sum (4096 elements)", "BenchmarkSum/Handwritten_sum")]:
        add(label, n, "ns/op", 1e-3, "µs", num(g(n, "allocs/op")[0]), kib(g(n, "B/op")[0]), nd=3)
    return rows


def table7(path):
    by = defaultdict(list)
    nodes = {}
    with open(path) as f:
        for r in csv.DictReader(f):
            by[r["mode"]].append(int(r["finalized"]))
            nodes[r["mode"]] = int(r["nodes"])
    labels = {"unsafe_pointer": ("unsafe.Pointer slot (R3)", "Yes"),
              "interface": ("Interface value (R1)", "Yes"),
              "uintptr": ("uintptr word", "No")}
    rows = []
    for mode in ["unsafe_pointer", "interface", "uintptr"]:
        xs = by[mode]
        rows.append({"storage": labels[mode][0], "mode": mode, "gc_visible": labels[mode][1],
                     "trials": len(xs), "nodes_per_trial": nodes[mode],
                     "reclaimed_median": float(np.median(xs)),
                     "reclaimed_min": min(xs), "reclaimed_max": max(xs),
                     "range": f"{min(xs):,}–{max(xs):,}"})
    return rows


def write_csv(path, rows):
    with open(path, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)


def main():
    data = parse_bench(os.path.join(RAW, "bench.txt"))
    if not data:
        sys.exit("no benchmark lines found in results/raw/bench.txt")
    summary = summarize(data)
    write_csv(os.path.join(RES, "bench_summary.csv"), summary)
    S = {(r["benchmark"], r["metric"]): (r["median"], r["q25"], r["q75"]) for r in summary}

    t6 = table6(S)
    write_csv(os.path.join(RES, "table6.csv"), t6)
    with open(os.path.join(RES, "table6.md"), "w") as f:
        f.write("Table 6. Generated-code measurements: median [interquartile range] "
                f"of {summary[0]['n']} runs.\n\n")
        f.write("| Benchmark | Time | Allocations | Memory |\n|---|---|---|---|\n")
        for r in t6:
            f.write(f"| {r['benchmark']} | {r['time']} | {r['allocations']} | {r['memory']} |\n")

    t7 = table7(os.path.join(RAW, "pointervis.csv"))
    write_csv(os.path.join(RES, "table7.csv"), t7)
    with open(os.path.join(RES, "table7.md"), "w") as f:
        f.write(f"Table 7. Objects reclaimed while still referenced by live enum values "
                f"({t7[0]['trials']} trials × {t7[0]['nodes_per_trial']:,} objects).\n\n")
        f.write("| Storage of the pointer payload | GC-visible | Reclaimed per trial (median) "
                "| Range |\n|---|---|---|---|\n")
        for r in t7:
            f.write(f"| {r['storage']} | {r['gc_visible']} | {r['reclaimed_median']:,.0f} "
                    f"| {r['range']} |\n")

    print(open(os.path.join(RES, "table6.md")).read())
    print(open(os.path.join(RES, "table7.md")).read())


if __name__ == "__main__":
    main()
