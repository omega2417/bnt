"""Step 10 - remaining Online Appendix tables (A1-A5, A12-A14).

A6-A11 are written by steps 4-8. This script assembles the descriptive tables and
checks that every appendix table exists. Output: output/tables/appendix_A*.csv
"""
from __future__ import annotations

import platform
import sys
from importlib import metadata
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from lib.common import CFG, get_logger, load_crosswalk, load_panel, load_policy, read_csv, save_table  # noqa: E402,E501

import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

log = get_logger("10_appendix_tables")


def a1():
    inv = read_csv(Path(CFG.RAW) / "mrpips" / "source_inventory.csv", dtype=str)
    cols = ["file", "series", "period", "frequency", "url", "download_date", "use", "revision_note"]
    save_table(inv[[c for c in cols if c in inv]], "appendix_A1", "Source files")


def a2(p):
    a = p.groupby("year")[["permits", "declarations", "seasonal", "notifications"]].sum(min_count=1)
    a["total"] = a.sum(axis=1)
    z = Path(CFG.DERIVED) / "zus_stock.csv"
    if z.exists():
        a = a.join(read_csv(z).set_index("year"))
    save_table(a.reset_index(), "appendix_A2", "Annual documents by channel, 2008-2025")


def a3():
    s = read_csv(Path(CFG.TABLES) / "concentration_series.csv")
    for val, name in (("effective_number", "appendix_A3"), ("hhi", "appendix_A3_hhi")):
        w = s.pivot_table(index="period", columns="measure", values=val).reset_index()
        save_table(w, name, f"Concentration series ({val})")


def a4(p, cw):
    flags = read_csv(Path(CFG.DERIVED) / "regression_sample.csv")
    cov = load_panel(with_covariates=True)
    est = cov[cov.year.isin(CFG.EST_YEARS)]
    tot = p.groupby("iso3")[["permits", "docs_excl_notif", "docs_all"]].sum()
    f = flags.groupby("iso3")[["baseline", "excl_UA_BY", "never_eligible", "comparison70"]].max()
    out = tot.join(f).join(cw.set_index("iso3")[["polish_name", "name_en"]])
    nogr = est.groupby("iso3")["rel_income_l1"].apply(lambda s: s.isna().all())
    reasons = []
    for iso, r in out.iterrows():
        why = []
        if nogr.get(iso, True):
            why.append("no World Bank growth data")
        if r.permits == 0:
            why.append("only zero permits")
        if iso in CFG.DECL6:
            why.append("declaration-access origin (not a comparison origin)")
        elif r.docs_excl_notif < CFG.COMPARISON_MIN_DOCS:
            why.append(f"< {CFG.COMPARISON_MIN_DOCS} documents (not a comparison origin)")
        reasons.append("; ".join(why))
    out["exclusion_reason"] = reasons
    out = out.reset_index().sort_values("docs_all", ascending=False)
    save_table(out, "appendix_A4", "Origins and samples")
    summary = pd.DataFrame([{"sample": k, "origins": int(out[k].fillna(0).sum())}
                            for k in ["baseline", "excl_UA_BY", "never_eligible", "comparison70"]]
                           + [{"sample": "panel", "origins": len(out)}])
    save_table(summary, "appendix_A4_summary")


def a5():
    acts = read_csv(Path(CFG.POLICY) / "legal_acts.csv", dtype=str)
    save_table(acts, "appendix_A5_legal_acts", "Legal acts used for the policy coding")
    pc = load_policy()
    d = pc[pc.iso3.isin(CFG.DECL6)]
    save_table(d, "appendix_A5", "Policy coding for the six declaration origins")


def a12_a13_a14():
    ext = Path(CFG.RAW) / "mrpips_reports" / "report_extracts.csv"
    if ext.exists():
        x = read_csv(ext)
        save_table(x[x.appendix_table == "A12"], "appendix_A12", "Person-based benchmarks")
    v = read_csv(Path(CFG.ROOT) / "codebook" / "variables.csv")
    save_table(v, "appendix_A13", "Variable definitions")
    pk = ["numpy", "pandas", "scipy", "statsmodels", "matplotlib", "openpyxl", "python-docx"]
    rows = [{"item": "Python", "value": platform.python_version()},
            {"item": "Platform", "value": platform.platform()},
            {"item": "Random seed", "value": CFG.SEED},
            {"item": "Pairs bootstrap draws", "value": CFG.N_PAIRS_BOOT},
            {"item": "Wild score bootstrap draws", "value": CFG.N_WILD_BOOT}]
    for k in pk:
        try:
            rows.append({"item": k, "value": metadata.version(k)})
        except metadata.PackageNotFoundError:
            rows.append({"item": k, "value": "not installed"})
    rt = Path(CFG.LOGS) / "runtime.csv"
    if rt.exists():
        for _, r in read_csv(rt).iterrows():
            rows.append({"item": f"runtime {r.script} (s)", "value": round(r.seconds, 1)})
    save_table(pd.DataFrame(rows), "appendix_A14", "Software and runtime")


def check():
    want = [f"appendix_A{i}" for i in range(1, 15)]
    missing = [w for w in want if not list(Path(CFG.TABLES).glob(f"{w}.csv"))
               and not list(Path(CFG.TABLES).glob(f"{w}_*.csv"))]
    if missing:
        log.warning("appendix tables not produced: %s", ", ".join(missing))
    else:
        log.info("all appendix tables A1-A14 present")


def main():
    p = load_panel()
    cw = load_crosswalk()
    a1(); a2(p); a3(); a4(p, cw); a5(); a12_a13_a14(); check()


if __name__ == "__main__":
    main()
