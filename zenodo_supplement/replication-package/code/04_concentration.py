"""Step 4 - concentration of origins (Section 5.1, Table 2, Figure 3, A3, A10).

HHI = sum of squared origin shares; 1/HHI = effective number of origins.

Outputs
    output/tables/concentration_series.csv     (data of Figure 3 and Online Appendix A3)
    output/tables/table2.csv                   segmented trends, Newey-West s.e.
    output/tables/appendix_A10.csv             duration-weighted HHI and HHI of holders
    output/tables/descriptives_composition.csv numbers quoted in Section 6.1

Time in the half-yearly regression is measured in years (2008.0, 2008.5, ...), so
all coefficients in Table 2 are per year (reviewer comment 18).
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from lib.common import CFG, fmt_coef, get_logger, load_panel, read_csv, save_table  # noqa: E402

import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
import statsmodels.api as sm  # noqa: E402

log = get_logger("04_concentration")


def hhi(counts: pd.Series) -> float:
    c = counts.fillna(0).clip(lower=0)
    tot = c.sum()
    return float(((c / tot) ** 2).sum()) if tot > 0 else np.nan


def annual_series(p: pd.DataFrame, persons: pd.DataFrame | None) -> pd.DataFrame:
    measures = {"permits": ["permits"], "declarations": ["declarations"],
                "seasonal": ["seasonal"], "notifications": ["notifications"],
                "excl_notifications": ["permits", "declarations", "seasonal"],
                "all_documents": ["permits", "declarations", "seasonal", "notifications"]}
    rows = []
    for y, g in p.groupby("year"):
        for m, cols in measures.items():
            sub = g[cols]
            if sub.isna().all().all():
                continue
            s = sub.sum(axis=1, min_count=1)
            rows.append({"measure": m, "period": str(y), "t": float(y), "hhi": hhi(s),
                         "documents": s.sum()})
        if persons is not None and y in set(persons.year):
            pp = persons[persons.year == y].set_index("iso3")["persons"]
            gg = g.set_index("iso3")
            s = gg[["permits", "seasonal"]].sum(axis=1, min_count=1).add(pp, fill_value=0)
            rows.append({"measure": "excl_notifications_decl_persons", "period": str(y),
                         "t": float(y), "hhi": hhi(s), "documents": s.sum()})
    out = pd.DataFrame(rows)
    out["effective_number"] = 1 / out["hhi"]
    return out


def halfyear_series() -> pd.DataFrame:
    hy = read_csv(Path(CFG.DERIVED) / "halfyear_permits.csv")
    rows = []
    for (y, h), g in hy.groupby(["year", "half"]):
        rows.append({"measure": "permits_halfyear", "period": f"{y}H{h}", "t": y + (h - 1) / 2,
                     "hhi": hhi(g["permits"]), "documents": g["permits"].sum()})
    out = pd.DataFrame(rows)
    out["effective_number"] = 1 / out["hhi"]
    return out


def segmented(df: pd.DataFrame, lags: int) -> tuple[pd.DataFrame, float, int]:
    t = df["t"].to_numpy()
    X = {"trend": t - t.min()}
    for k in CFG.HHI_BREAKS:
        X[f"level_{k}"] = (t >= k).astype(float)
        X[f"slope_{k}"] = np.where(t >= k, t - k, 0.0)
    X = sm.add_constant(pd.DataFrame(X))
    m = sm.OLS(df["hhi"].to_numpy(), X).fit(cov_type="HAC", cov_kwds={"maxlags": lags})
    res = pd.DataFrame({"coef": m.params, "se": m.bse, "p": m.pvalues})
    return res, m.rsquared, int(m.nobs)


def duration_weighted(p: pd.DataFrame) -> pd.DataFrame:
    dur = read_csv(Path(CFG.POLICY) / "document_duration.csv")
    rows = []
    for y, g in p.groupby("year"):
        w = {}
        for ch in ["permits", "declarations", "seasonal", "notifications"]:
            r = dur[(dur.channel == ch) & (dur.year_from <= y) & (dur.year_to >= y)]
            w[ch] = float(r["max_months"].iloc[0]) if len(r) else np.nan
        for label, chans in (("excl_notifications", ["permits", "declarations", "seasonal"]),
                             ("all_documents", ["permits", "declarations", "seasonal", "notifications"])):
            chans = [c for c in chans if g[c].notna().any() and np.isfinite(w[c])]
            s = sum(g[c].fillna(0) * w[c] for c in chans)
            rows.append({"measure": f"{label}_document_months", "year": y,
                         "hhi": hhi(s), "effective_number": 1 / hhi(s)})
    out = pd.DataFrame(rows)
    hold = Path(CFG.RAW) / "mrpips_reports" / "holders_by_citizenship_2025.csv"
    if hold.exists():
        h = read_csv(hold)
        v = hhi(h["holders"])
        out = pd.concat([out, pd.DataFrame([{"measure": "holders_current_documents_31dec2025",
                                              "year": 2025, "hhi": v, "effective_number": 1 / v}])])
    else:
        log.warning("holders_by_citizenship_2025.csv not found - holder HHI not computed (A10)")
    return out


def descriptives(p: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for y, g in p.groupby("year"):
        ua = g[g.iso3 == "UKR"]
        rows.append({
            "year": y,
            "documents_all": g.docs_all.sum(),
            "ukr_share_permits": float(ua.permits.sum() / g.permits.sum()),
            "ukr_share_all_documents": float(ua.docs_all.sum() / g.docs_all.sum()),
            "origins_ge_1000_permits": int((g.permits >= 1000).sum()),
            "declaration_share_of_documents": float(g.declarations.sum() / g.docs_all.sum()),
            "notification_share_of_documents": float(g.notifications.fillna(0).sum() / g.docs_all.sum()),
            "documents_never_eligible": float(g.loc[~g.iso3.isin(CFG.DECL6), "docs_all"].sum()),
            "documents_decl6": float(g.loc[g.iso3.isin(CFG.DECL6), "docs_all"].sum()),
            "permits_decl6": float(g.loc[g.iso3.isin(CFG.DECL6), "permits"].sum()),
        })
    return pd.DataFrame(rows)


def main() -> None:
    p = load_panel()
    pf = Path(CFG.DERIVED) / "declaration_persons.csv"
    persons = read_csv(pf) if pf.exists() else None
    ann = annual_series(p, persons)
    hy = halfyear_series()
    series = pd.concat([hy, ann], ignore_index=True)
    save_table(series, "concentration_series")

    cols = {}
    spec = [("Work permits, half-years", hy, CFG.HHI_NW_LAGS_HALFYEAR),
            ("All documents excl. notifications, years",
             ann[ann.measure == "excl_notifications"], CFG.HHI_NW_LAGS_YEAR),
            ("All documents, years", ann[ann.measure == "all_documents"], CFG.HHI_NW_LAGS_YEAR)]
    labels = {"trend": "Trend before 2018 (per year)", "level_2018": "Level change 2018",
              "slope_2018": "Slope change 2018", "level_2022": "Level change 2022",
              "slope_2022": "Slope change 2022"}
    long_rows = []
    for name, d, lags in spec:
        res, r2, n = segmented(d.sort_values("t"), lags)
        cols[name] = [fmt_coef(*res.loc[k, ["coef", "se", "p"]]) for k in labels] + [n, f"{r2:.2f}"]
        for k in labels:
            long_rows.append({"column": name, "term": k, **res.loc[k].to_dict()})
    t2 = pd.DataFrame(cols, index=list(labels.values()) + ["Observations", "R2"]).reset_index()
    t2 = t2.rename(columns={"index": ""})
    save_table(t2, "table2", "Segmented trends in the concentration of origins (HHI)")
    save_table(pd.DataFrame(long_rows), "table2_long")

    save_table(duration_weighted(p), "appendix_A10")
    save_table(descriptives(p), "descriptives_composition")
    log.info("concentration done")


if __name__ == "__main__":
    main()
