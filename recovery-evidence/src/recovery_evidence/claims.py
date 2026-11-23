"""Claim-to-evidence register.

Every number printed in Tables 5-8 (and the numeric statements of Section 5.3)
is paired with the value recomputed by this package and the file it comes
from.  ``status`` is ``identical`` when the recomputed value, rounded to the
precision printed in the manuscript draft, equals the printed value, and
``differs`` otherwise.  The register is the list of edits needed to make the
manuscript and the released package agree digit for digit.
"""
from __future__ import annotations

import csv
import json
from importlib import resources
from pathlib import Path
from typing import List

POLICIES = ("P0", "P1", "P2", "P3")


def _manuscript() -> dict:
    return json.loads(resources.files("recovery_evidence").joinpath("data/manuscript_values.json").read_text("utf-8"))


def build_register(results_dir: Path) -> List[dict]:
    results_dir = Path(results_dir)
    an = json.loads((results_dir / "tables" / "analysis.json").read_text(encoding="utf-8"))["conditions"]
    ms = _manuscript()
    rows: List[dict] = []

    def add(loc: str, quantity: str, printed: float, value: float, nd: int, source: str, mcse: float = None) -> None:
        same = round(value, nd) == round(printed, nd)
        rows.append({
            "id": f"R{len(rows) + 1:03d}", "location": loc, "quantity": quantity,
            "manuscript_draft": f"{printed:.{nd}f}", "package": f"{value:.{nd}f}",
            "difference": f"{round(value, nd) - round(printed, nd):+.{nd}f}",
            "difference_in_mcse": "" if not mcse else f"{(value - printed) / mcse:+.1f}",
            "status": "identical" if same else "differs", "source": source,
        })

    c0 = an["C0"]
    src = "results/tables/policy_summary.csv"
    for pol, v in ms["table5"].items():
        p = c0["policies"][pol]
        for m in ("FASD", "FUSD", "TOTAL"):
            add("Table 5", f"C0 {pol} {m} mean", v[m][0], p[f"{m}_mean"], 2, src, p[f"{m}_mcse"])
            add("Table 5", f"C0 {pol} {m} MCSE", v[m][1], p[f"{m}_mcse"], 2, src)
        add("Table 5", f"C0 {pol} share of assurances false, %", v["share_false_pct"],
            100 * p["share_assurances_false_mean"], 1, src)
        add("Table 5", f"C0 {pol} mean false-assurance spell, days", v["mean_spell"], p["mean_spell_days"], 2, src)
        add("Table 5", f"C0 {pol} censored spells", v["censored"], p["censored_spells_total"], 0, src)
    src = "results/tables/paired_results.csv"
    names = ("mean", "ci_low", "ci_high", "sd", "median", "mcse")
    for key, v in ms["table6"].items():
        st = c0["contrasts"][key]
        for name, printed in zip(names, v):
            add("Table 6", f"C0 {key} {name}", printed, st[name], 3 if name == "mcse" else 2, src,
                st["mcse"] if name == "mean" else None)
        for name, printed in zip(("share_negative", "share_zero", "share_positive"), v[6:]):
            add("Table 6", f"C0 {key} {name}, %", printed, 100 * st[name], 0, src)
    if "allocation" in c0:
        cell = {(a["policy"], a["component"]): a for a in c0["allocation"]}
        for comp, per_policy in ms["table7"].items():
            for pol, (n, age) in zip(POLICIES, per_policy):
                a = cell[(pol, comp)]
                add("Table 7", f"C0 {pol} checks of {comp} per trajectory", n, a["mean_checks_per_trajectory"], 1,
                    "results/tables/allocation.csv")
                add("Table 7", f"C0 {pol} mean evidence age at check of {comp}", age,
                    a["mean_evidence_age_at_check"], 1, "results/tables/allocation.csv")
        delay = {d["policy"]: d["mean_days_to_next_check"] for d in c0["recheck_delay"]}
        for pol, printed in ms["recheck_delay_c0"].items():
            add("Section 5.3", f"C0 {pol} days from failed check to next check", printed, delay[pol], 2,
                "results/tables/recheck_delay.csv")
    for cname, v in ms["table8"].items():
        if cname not in an:
            continue
        c = an[cname]
        for pol, printed in zip(("P1", "P2", "P3"), v["FASD"]):
            p = c["policies"][pol]
            add("Table 8", f"{cname} {pol} FASD mean", printed, p["FASD_mean"], 2,
                "results/tables/policy_summary.csv", p["FASD_mcse"])
        for key in ("P3-P1:FASD", "P3-P2:FASD", "P3-P1:FUSD", "P3-P1:TOTAL"):
            st = c["contrasts"][key]
            for name, printed in zip(("mean", "ci_low", "ci_high"), v[key]):
                add("Table 8", f"{cname} {key} {name}", printed, st[name], 2,
                    "results/tables/paired_results.csv", st["mcse"] if name == "mean" else None)
    for cname, (lo, hi) in ms["max_spell"].items():
        if cname in an:
            longest = [an[cname]["policies"][p]["max_spell_days"] for p in POLICIES]
            add("Section 5.6", f"{cname} shortest of the four longest spells, days", lo, min(longest), 0,
                "results/tables/policy_summary.csv")
            add("Section 5.6", f"{cname} longest false-assurance spell, days", hi, max(longest), 0,
                "results/tables/policy_summary.csv")
    return rows


def write_register(results_dir: Path) -> dict:
    """Write ``claims_register.csv`` and ``manuscript_alignment.md``; return the counts."""
    results_dir = Path(results_dir)
    rows = build_register(results_dir)
    out = results_dir / "tables"
    with open(out / "claims_register.csv", "w", encoding="utf-8", newline="") as fh:
        wr = csv.DictWriter(fh, list(rows[0]), lineterminator="\n")
        wr.writeheader()
        wr.writerows(rows)
    same = sum(r["status"] == "identical" for r in rows)
    by_loc = {}
    for r in rows:
        tot, ok = by_loc.get(r["location"], (0, 0))
        by_loc[r["location"]] = (tot + 1, ok + (r["status"] == "identical"))
    means = [abs(float(r["difference_in_mcse"])) for r in rows if r["difference_in_mcse"] and r["status"] == "differs"]
    md = ["# Manuscript alignment", "",
          "Generated by `recovery-evidence claims` from `results/tables/analysis.json`.", "",
          f"Of {len(rows)} numbers printed in the manuscript draft, **{same} are reproduced digit for digit** "
          f"and **{len(rows) - same} differ**.", "",
          "| Location | Numbers | Identical | Differ |", "| --- | --- | --- | --- |"]
    md += [f"| {loc} | {tot} | {ok} | {tot - ok} |" for loc, (tot, ok) in by_loc.items()]
    if means:
        md += ["", f"Among the differing means, the largest gap is {max(means):.1f} Monte Carlo standard errors "
                   f"(median {sorted(means)[len(means) // 2]:.1f})."]
    md += ["", "## Numbers to update in the manuscript", "",
           "| ID | Location | Quantity | Draft | Package | Difference |", "| --- | --- | --- | --- | --- | --- |"]
    md += [f"| {r['id']} | {r['location']} | {r['quantity']} | {r['manuscript_draft']} | **{r['package']}** | {r['difference']} |"
           for r in rows if r["status"] == "differs"]
    (out / "manuscript_alignment.md").write_text("\n".join(md) + "\n", encoding="utf-8")
    return {"total": len(rows), "identical": same, "differs": len(rows) - same}
