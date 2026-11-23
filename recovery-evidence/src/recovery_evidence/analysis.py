"""Independent analysis of the primary logs (Sections 4.4-4.6, 5).

This module deliberately imports **nothing** from the simulator, the generator,
the policies or the topology.  It reads ``verdicts.csv.gz`` and
``checks.csv.gz``, recomputes every outcome from the rows, and compares the
result with the evaluator's ``trace_summary.csv``.  A test asserts the import
boundary (``tests/test_analysis.py``).

Outputs (``results/tables``): ``integrity_report.txt``, ``policy_summary.csv``,
``paired_results.csv``, ``paired_differences.csv``, ``allocation.csv``,
``recheck_delay.csv`` and Markdown renderings of Tables 5-8.
"""
from __future__ import annotations

import csv
import gzip
import json
from collections import defaultdict
from pathlib import Path
from typing import Dict, List, Sequence, Tuple

import numpy as np

ANALYSIS_SEED = 20261124
N_BOOT = 10_000
POLICIES = ("P0", "P1", "P2", "P3")
CONTRASTS = (("P3", "P1"), ("P3", "P2"), ("P2", "P1"), ("P1", "P0"))
METRICS = ("FASD", "FUSD", "TOTAL")
METRIC_LABEL = {"FASD": "False assurance", "FUSD": "False rejection", "TOTAL": "Total"}
COUNT_FIELDS = ("service_days", "false_assured", "false_rejected", "correct", "assured_days",
                "unready_days", "spells", "censored_spells", "max_spell")
MINUS = "−"


# ---------------------------------------------------------------------------
# Reading and recomputing
# ---------------------------------------------------------------------------
def _condition_dirs(logs: Path) -> List[Path]:
    return sorted((d for d in logs.iterdir() if d.is_dir() and (d / "trace_summary.csv").exists()),
                  key=lambda d: int(d.name[1:]))


def recompute_from_verdicts(path: Path) -> Tuple[Dict[Tuple[int, str], Dict[str, int]], List[str]]:
    """Recompute per-trajectory outcome counts from the verdict rows.

    Returns the counts and a list of integrity problems (empty when clean).
    Checks: unique key (replicate, policy, day, service); identical reference
    labels across the policies of a replicate.
    """
    problems: List[str] = []
    cells: Dict[Tuple[int, str, str], List[Tuple[int, int, int]]] = defaultdict(list)
    with gzip.open(path, "rt", encoding="utf-8", newline="") as fh:
        reader = csv.reader(fh)
        header = next(reader)
        if header != ["replicate", "policy", "day", "service", "verdict", "reference"]:
            raise ValueError(f"{path}: unexpected header {header}")
        for rep, pol, day, svc, vh, y in reader:
            cells[(int(rep), pol, svc)].append((int(day), int(vh), int(y)))
    counts: Dict[Tuple[int, str], Dict[str, int]] = defaultdict(lambda: dict.fromkeys(COUNT_FIELDS, 0))
    labels: Dict[Tuple[int, str], Dict[str, Tuple[int, ...]]] = defaultdict(dict)
    for (rep, pol, svc), rows in cells.items():
        days = [d for d, _, _ in rows]
        if len(set(days)) != len(days):
            problems.append(f"duplicate key in replicate {rep}, {pol}, {svc}")
        rows.sort()
        c = counts[(rep, pol)]
        run = 0
        for _, vh, y in rows:
            c["service_days"] += 1
            c["assured_days"] += vh
            c["unready_days"] += 1 - y
            if vh == 1 and y == 0:
                c["false_assured"] += 1
                run += 1
                continue
            if vh == 0 and y == 1:
                c["false_rejected"] += 1
            else:
                c["correct"] += 1
            if run:
                c["spells"] += 1
                c["max_spell"] = max(c["max_spell"], run)
                run = 0
        if run:
            c["spells"] += 1
            c["censored_spells"] += 1
            c["max_spell"] = max(c["max_spell"], run)
        labels[(rep, svc)][pol] = tuple(y for _, _, y in rows)
    for (rep, svc), per_policy in labels.items():
        if len(set(per_policy.values())) != 1:
            problems.append(f"reference labels differ across policies: replicate {rep}, {svc}")
    return counts, problems


def read_trace_summary(path: Path) -> Dict[Tuple[int, str], Dict[str, str]]:
    with open(path, encoding="utf-8", newline="") as fh:
        return {(int(r["replicate"]), r["policy"]): r for r in csv.DictReader(fh)}


def load_condition(cdir: Path, parameters: dict) -> Tuple[dict, List[str]]:
    """Per-policy replicate arrays for one condition, plus the integrity lines."""
    name = cdir.name
    par = parameters[name]
    lines: List[str] = []
    summary = read_trace_summary(cdir / "trace_summary.csv")
    vpath = cdir / "verdicts.csv.gz"
    if vpath.exists():
        counts, problems = recompute_from_verdicts(vpath)
        ok = not problems
        if set(counts) != set(summary):
            ok = False
            problems.append("verdict log and trace summary cover different (replicate, policy) keys")
        mism = 0
        for key, c in counts.items():
            row = summary.get(key)
            if row is None:
                continue
            if any(int(row[f]) != c[f] for f in COUNT_FIELDS):
                mism += 1
            fasd = 100.0 * c["false_assured"] / c["service_days"]
            fusd = 100.0 * c["false_rejected"] / c["service_days"]
            if f"{fasd:.6f}" != row["FASD"] or f"{fusd:.6f}" != row["FUSD"]:
                mism += 1
        expected = par["n_services"] * par["T"]
        wrong_n = sum(1 for c in counts.values() if c["service_days"] != expected)
        ok = ok and mism == 0 and wrong_n == 0
        lines.append(f"{name}: verdict rows recomputed for {len(counts)} trajectories x policies; "
                     f"mismatches with trace_summary.csv: {mism}; trajectories without "
                     f"{expected} service-days: {wrong_n}; key/label problems: {len(problems)} "
                     f"-> {'AGREE' if ok else 'DISAGREE'}")
        lines.extend(f"   ! {p}" for p in problems[:10])
        source = {k: {f: v[f] for f in COUNT_FIELDS} for k, v in counts.items()}
    else:
        lines.append(f"{name}: verdicts.csv.gz not present; using trace_summary.csv only -> NOT RE-VERIFIED")
        source = {k: {f: int(v[f]) for f in COUNT_FIELDS} for k, v in summary.items()}
    reps = sorted({k[0] for k in source})
    data = {"replicates": reps, "checks": {}}
    for pol in POLICIES:
        data[pol] = {f: np.array([source[(r, pol)][f] for r in reps], dtype=float) for f in COUNT_FIELDS}
        data["checks"][pol] = np.array([int(summary[(r, pol)]["checks"]) for r in reps], dtype=float)
    return data, lines


def metric(d: dict, name: str) -> np.ndarray:
    """Per-replicate value of an outcome measure (service-days per 100)."""
    n = d["service_days"]
    if name == "FASD":
        return 100.0 * d["false_assured"] / n
    if name == "FUSD":
        return 100.0 * d["false_rejected"] / n
    if name == "TOTAL":
        return 100.0 * (d["false_assured"] + d["false_rejected"]) / n
    raise KeyError(name)


def ratio(num: np.ndarray, den: np.ndarray) -> np.ndarray:
    """Per-replicate ratio; NA (nan) where the denominator is zero."""
    with np.errstate(divide="ignore", invalid="ignore"):
        return np.where(den > 0, num / den, np.nan)


# ---------------------------------------------------------------------------
# Statistics
# ---------------------------------------------------------------------------
def bootstrap_indices(n: int, n_boot: int = N_BOOT, seed: int = ANALYSIS_SEED) -> np.ndarray:
    """Resampled replicate identifiers; one fixed matrix serves every contrast."""
    return np.random.default_rng(seed).integers(0, n, size=(n_boot, n))


def paired_stats(diff: np.ndarray, idx: np.ndarray) -> dict:
    """Mean, 95% percentile bootstrap interval, SD, median, MCSE and sign shares."""
    n = len(diff)
    boot = diff[idx].mean(axis=1)
    lo, hi = np.percentile(boot, [2.5, 97.5])
    sd = float(diff.std(ddof=1)) if n > 1 else 0.0
    return {
        "n": n, "mean": float(diff.mean()), "ci_low": float(lo), "ci_high": float(hi),
        "sd": sd, "median": float(np.median(diff)), "mcse": sd / np.sqrt(n),
        "share_negative": float((diff < 0).mean()), "share_zero": float((diff == 0).mean()),
        "share_positive": float((diff > 0).mean()),
    }


def mean_mcse(x: np.ndarray) -> Tuple[float, float]:
    x = x[~np.isnan(x)]
    return float(x.mean()), (float(x.std(ddof=1)) / np.sqrt(len(x)) if len(x) > 1 else 0.0)


# ---------------------------------------------------------------------------
# Check-log analyses (allocation, re-check delay)
# ---------------------------------------------------------------------------
def analyse_checks(path: Path, n_replicates: int):
    """Table 7 (allocation) and the exploratory re-check delay of Section 5.3."""
    n_checks: Dict[Tuple[str, str], int] = defaultdict(int)
    age_sum: Dict[Tuple[str, str], int] = defaultdict(int)
    last_fail: Dict[Tuple[str, str, str], int] = {}
    delay_sum: Dict[str, int] = defaultdict(int)
    delay_n: Dict[str, int] = defaultdict(int)
    with gzip.open(path, "rt", encoding="utf-8", newline="") as fh:
        reader = csv.DictReader(fh)
        for row in reader:
            pol, comp, day = row["policy"], row["component"], int(row["day"])
            n_checks[(pol, comp)] += 1
            age_sum[(pol, comp)] += int(row["evidence_age"])
            key = (row["replicate"], pol, comp)
            if key in last_fail:
                delay_sum[pol] += day - last_fail.pop(key)
                delay_n[pol] += 1
            if row["result"] == "0":
                last_fail[key] = day
    alloc = [
        {"policy": pol, "component": comp, "mean_checks_per_trajectory": n / n_replicates,
         "mean_evidence_age_at_check": age_sum[(pol, comp)] / n}
        for (pol, comp), n in sorted(n_checks.items())
    ]
    delay = [
        {"policy": pol, "failed_checks_followed_by_recheck": delay_n[pol],
         "mean_days_to_next_check": delay_sum[pol] / delay_n[pol] if delay_n[pol] else float("nan")}
        for pol in POLICIES
    ]
    return alloc, delay


# ---------------------------------------------------------------------------
# Tables
# ---------------------------------------------------------------------------
def _f(x: float, nd: int = 2) -> str:
    s = f"{x:.{nd}f}"
    if float(s) == 0.0:
        s = s.lstrip("-")
    return s.replace("-", MINUS)


def _ci(st: dict, nd: int = 2) -> str:
    return f"{_f(st['mean'], nd)} [{_f(st['ci_low'], nd)}, {_f(st['ci_high'], nd)}]"


def _pct(x: float) -> str:
    return f"{100 * x:.0f}%"


def _write_csv(path: Path, rows: List[dict]) -> None:
    with open(path, "w", encoding="utf-8", newline="") as fh:
        wr = csv.DictWriter(fh, list(rows[0]), lineterminator="\n")
        wr.writeheader()
        for row in rows:
            wr.writerow({k: (f"{v:.6f}" if isinstance(v, float) else v) for k, v in row.items()})


def _md(header: Sequence[str], rows: Sequence[Sequence[str]], title: str) -> str:
    out = [title, "", "| " + " | ".join(header) + " |", "|" + "|".join(" --- " for _ in header) + "|"]
    out += ["| " + " | ".join(r) + " |" for r in rows]
    return "\n".join(out) + "\n"


def analyse(results_dir: Path, quiet: bool = False) -> dict:
    """Run the full analysis; returns a dictionary also saved as ``analysis.json``."""
    results_dir = Path(results_dir)
    logs, tables = results_dir / "logs", results_dir / "tables"
    tables.mkdir(parents=True, exist_ok=True)
    resolved = json.loads((results_dir / "parameters.json").read_text(encoding="utf-8"))
    labels = {c["name"]: c["label"] for c in resolved["conditions"]}
    # number of services comes from the verdict rows themselves; T from the configuration
    parameters = {c["name"]: {"T": c["T"], "n_services": 3, "b": c["b"]} for c in resolved["conditions"]}

    integrity: List[str] = ["Independent re-computation of the evaluator's outcome counts", ""]
    policy_rows: List[dict] = []
    paired_rows: List[dict] = []
    diff_rows: List[dict] = []
    alloc_rows: List[dict] = []
    delay_rows: List[dict] = []
    out: dict = {"conditions": {}}

    for cdir in _condition_dirs(logs):
        name = cdir.name
        data, lines = load_condition(cdir, parameters)
        integrity.extend(lines)
        R = len(data["replicates"])
        idx = bootstrap_indices(R)
        cres: dict = {"label": labels[name], "R": R, "policies": {}, "contrasts": {}}
        for pol in POLICIES:
            d = data[pol]
            row = {"condition": name, "policy": pol, "replicates": R}
            for m in METRICS:
                row[f"{m}_mean"], row[f"{m}_mcse"] = mean_mcse(metric(d, m))
            share_false = ratio(d["false_assured"], d["assured_days"])
            share_missed = ratio(d["false_assured"], d["unready_days"])
            row["share_assurances_false_mean"] = mean_mcse(share_false)[0]
            row["share_assurances_false_NA"] = int(np.isnan(share_false).sum())
            row["share_unready_falsely_assured_mean"] = mean_mcse(share_missed)[0]
            row["share_unready_falsely_assured_NA"] = int(np.isnan(share_missed).sum())
            spells = d["spells"].sum()
            row["spells_total"] = int(spells)
            row["mean_spell_days"] = float(d["false_assured"].sum() / spells) if spells else float("nan")
            row["censored_spells_total"] = int(d["censored_spells"].sum())
            row["max_spell_days"] = int(d["max_spell"].max())
            row["checks_per_trajectory"] = float(data["checks"][pol].mean())
            # pooled FASD recomputed from the confusion-matrix sums (must equal the mean: equal denominators)
            row["FASD_pooled"] = float(100.0 * d["false_assured"].sum() / d["service_days"].sum())
            policy_rows.append(row)
            cres["policies"][pol] = row
        pooled_ok = all(abs(r["FASD_pooled"] - r["FASD_mean"]) < 1e-9 for r in policy_rows[-len(POLICIES):])
        integrity.append(f"{name}: pooled FASD from confusion-matrix sums equals mean of trajectory FASD: "
                         f"{'AGREE' if pooled_ok else 'DISAGREE'}")
        for hi, lo in CONTRASTS:
            for m in METRICS:
                diff = metric(data[hi], m) - metric(data[lo], m)
                st = paired_stats(diff, idx)
                paired_rows.append({"condition": name, "contrast": f"{hi}-{lo}", "metric": m, **st})
                cres["contrasts"][f"{hi}-{lo}:{m}"] = st
        for i, r in enumerate(data["replicates"]):
            row = {"condition": name, "replicate": r}
            for pol in POLICIES:
                for m in METRICS:
                    row[f"{m}_{pol}"] = float(metric(data[pol], m)[i])
            diff_rows.append(row)
        cpath = cdir / "checks.csv.gz"
        if cpath.exists():
            alloc, delay = analyse_checks(cpath, R)
            alloc_rows += [{"condition": name, **a} for a in alloc]
            delay_rows += [{"condition": name, **d} for d in delay]
            cres["allocation"], cres["recheck_delay"] = alloc, delay
        out["conditions"][name] = cres
        if not quiet:
            print(f"  analysed {name}")

    verdict = "ALL COMPARISONS AGREED" if not any("DISAGREE" in l for l in integrity) else "DISAGREEMENT FOUND"
    not_verified = sum("NOT RE-VERIFIED" in l for l in integrity)
    integrity += ["", f"Result: {verdict} ({len(out['conditions'])} conditions; "
                      f"{not_verified} without a verdict log)"]
    (tables / "integrity_report.txt").write_text("\n".join(integrity) + "\n", encoding="utf-8")
    out["integrity"] = {"verdict": verdict, "conditions_without_verdict_log": not_verified}

    _write_csv(tables / "policy_summary.csv", policy_rows)
    _write_csv(tables / "paired_results.csv", paired_rows)
    _write_csv(tables / "paired_differences.csv", diff_rows)
    if alloc_rows:
        _write_csv(tables / "allocation.csv", alloc_rows)
        _write_csv(tables / "recheck_delay.csv", delay_rows)
    _render_tables(out, tables)
    (tables / "analysis.json").write_text(json.dumps(out, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    return out


def _render_tables(out: dict, tables: Path) -> None:
    conds = out["conditions"]
    if "C0" in conds:
        c0 = conds["C0"]
        rows = []
        for pol in POLICIES:
            p = c0["policies"][pol]
            rows.append([pol, f"{p['FASD_mean']:.2f} ± {p['FASD_mcse']:.2f}",
                         f"{p['FUSD_mean']:.2f} ± {p['FUSD_mcse']:.2f}",
                         f"{p['TOTAL_mean']:.2f} ± {p['TOTAL_mcse']:.2f}",
                         f"{100 * p['share_assurances_false_mean']:.1f}%",
                         f"{p['mean_spell_days']:.2f}", str(p["censored_spells_total"]),
                         f"{p['checks_per_trajectory']:.0f}"])
        (tables / "table5_primary.md").write_text(_md(
            ["Policy", "False assurance (FASD)", "False rejection (FUSD)", "Total error",
             "Share of assurances that were false", "Mean false-assurance spell (days)",
             "Censored spells", "Checks per trajectory"], rows,
            f"Table 5. Primary configuration C0 (R = {c0['R']} paired trajectories). Rates are "
            "service-days per 100 observed service-days (mean ± Monte Carlo SE)."), encoding="utf-8")
        rows = []
        for hi, lo in CONTRASTS:
            for m in METRICS:
                st = c0["contrasts"][f"{hi}-{lo}:{m}"]
                rows.append([f"{hi} {MINUS} {lo}", METRIC_LABEL[m], _ci(st), f"{st['sd']:.2f}",
                             _f(st["median"]), f"{st['mcse']:.3f}",
                             f"{_pct(st['share_negative'])} / {_pct(st['share_zero'])} / {_pct(st['share_positive'])}"])
        (tables / "table6_contrasts.md").write_text(_md(
            ["Contrast", "Outcome", "Mean [95% CI]", "SD", "Median", "MCSE", "Negative / zero / positive"],
            rows, "Table 6. Paired contrasts in C0: mean difference [95% percentile bootstrap interval, "
                  "10,000 resamples of whole trajectories]."), encoding="utf-8")
        if "allocation" in c0:
            cell = {(a["policy"], a["component"]): a for a in c0["allocation"]}
            comps = sorted({a["component"] for a in c0["allocation"]})
            rows = [[c] + [f"{cell[(p, c)]['mean_checks_per_trajectory']:.1f} "
                           f"({cell[(p, c)]['mean_evidence_age_at_check']:.1f})" for p in POLICIES]
                    for c in comps]
            (tables / "table7_allocation.md").write_text(_md(
                ["Component", *POLICIES], rows,
                "Table 7. Allocation of checks in C0: mean checks per trajectory by component "
                "(mean evidence age at the time of the check, days)."), encoding="utf-8")
    rows = []
    for name, c in conds.items():
        p = c["policies"]
        k = c["contrasts"]
        rows.append([f"{name} {c['label']}",
                     " / ".join(f"{p[q]['FASD_mean']:.2f}" for q in ("P1", "P2", "P3")),
                     _ci(k["P3-P1:FASD"]), _ci(k["P3-P2:FASD"]), _ci(k["P3-P1:FUSD"]), _ci(k["P3-P1:TOTAL"])])
    (tables / "table8_conditions.md").write_text(_md(
        ["Condition", "FASD P1 / P2 / P3", f"FASD P3 {MINUS} P1", f"FASD P3 {MINUS} P2",
         f"FUSD P3 {MINUS} P1", f"Total P3 {MINUS} P1"], rows,
        "Table 8. All conditions. Comparator rates and paired differences, service-days per 100; "
        "95% percentile bootstrap intervals."), encoding="utf-8")
