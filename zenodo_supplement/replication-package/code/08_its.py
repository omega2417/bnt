"""Step 8 - interrupted time series (Section 5.4; Table 6; A9; A11).

Panel A (Jan 2021 - Nov 2025): log monthly counts (log(1+y) for seasonal permits)
on a linear trend, calendar-month effects, a February 2022 pulse and level/slope
breaks in March 2022 and June 2025. Panel B (Jan 2015 - Dec 2019): declarations with a
January 2018 break. Half-yearly work permits 2015-2021 with a 2018 break (t in years).
Newey-West standard errors (6 lags monthly, 2 lags half-yearly).

A9 reports every coefficient with its standard error, the absolute post-break slopes
(trend + slope changes) and the calendar-month effects, which are needed to read
the June-November 2025 slopes against the raw series (reviewer comment 14).

Outputs: table6.csv, appendix_A9.csv, appendix_A9_month_effects.csv, appendix_A11.csv
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from lib.common import CFG, get_logger, read_csv, require, save_table, stars  # noqa: E402

import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
import statsmodels.api as sm  # noqa: E402

log = get_logger("08_its")


def month_index(ym: pd.Series) -> np.ndarray:
    d = pd.PeriodIndex(ym, freq="M")
    return np.asarray(d.year * 12 + d.month - 1)


def mi(s: str) -> int:
    return month_index(pd.Series([s]))[0]


def its_model(df, col, start, end, breaks, pulse=None, log1p=False, extra_level=None):
    d = df[(df.ym >= start) & (df.ym <= end)].dropna(subset=[col]).copy()
    t = month_index(d.ym)
    y = np.log1p(d[col]) if log1p else np.log(d[col])
    X = pd.DataFrame({"trend": t - t.min()}, index=d.index)
    for b in breaks:
        X[f"level_{b}"] = (t >= mi(b)).astype(float)
        X[f"slope_{b}"] = np.where(t >= mi(b), t - mi(b), 0)
    if pulse and (d.ym == pulse).any():
        X[f"pulse_{pulse}"] = (d.ym == pulse).astype(float).to_numpy()
    if extra_level and (d.ym >= extra_level).any():
        X[f"level_{extra_level}"] = (t >= mi(extra_level)).astype(float)
    months = pd.get_dummies(pd.PeriodIndex(d.ym, freq="M").month, prefix="month",
                            drop_first=True, dtype=float)
    months.index = d.index
    X = sm.add_constant(pd.concat([X, months], axis=1))
    m = sm.OLS(y.to_numpy(), X).fit(cov_type="HAC", cov_kwds={"maxlags": CFG.ITS_NW_LAGS_MONTHLY})
    return m, len(d)


def pct(b):
    return 100 * (np.exp(b) - 1)


def main():
    nat = read_csv(require(Path(CFG.DERIVED) / "monthly_national.csv"))
    nat["excl_notif"] = nat[["permits", "declarations", "seasonal"]].sum(axis=1, min_count=3)
    nat["all_docs"] = nat["excl_notif"] + nat["notifications"].fillna(0)
    s, e = CFG.ITS_MAIN_WINDOW
    b22, b25 = CFG.ITS_BREAK_2022, CFG.ITS_BREAK_2025
    specs = [
        ("Work permits", "permits", s, e, [b22, b25], False),
        ("Employer declarations", "declarations", s, e, [b22, b25], False),
        ("Seasonal work permits", "seasonal", CFG.ITS_SEASONAL_START, e, [b22, b25], True),
        ("Notifications", "notifications", CFG.ITS_NOTIF_START, e, [b25], False),
        ("All documents excl. notifications", "excl_notif", s, e, [b22, b25], False),
        ("All documents", "all_docs", s, e, [b22, b25], False),
    ]
    rows_t6, rows_a9, rows_me = [], [], []

    def record(panel, label, window, m, n, breaks):
        p = m.params
        rec = {"Panel": panel, "Series and window": f"{label}, {window}", "N": n}
        for b in breaks:
            for kind in ("level", "slope"):
                k = f"{kind}_{b}"
                if k in p:
                    val = pct(p[k]) if kind == "level" else p[k]
                    rec[f"{kind} {b}"] = (f"{val:.0f}%" if kind == "level" else f"{val:.3f}") + stars(m.pvalues[k])
        rows_t6.append(rec)
        for k in p.index:
            if k.startswith("month_"):
                rows_me.append({"series": label, "window": window, "month": int(k.split("_")[1]),
                                "coef": p[k], "se": m.bse[k]})
                continue
            rows_a9.append({"panel": panel, "series": label, "window": window, "term": k,
                            "coef": p[k], "se": m.bse[k], "p": m.pvalues[k],
                            "pct_change": pct(p[k]) if k.startswith(("level", "pulse")) else np.nan,
                            "N": n})
        # absolute slopes after each break
        acc = ["trend"]
        for b in breaks:
            acc.append(f"slope_{b}")
            w = np.zeros(len(p)); idx = [list(p.index).index(a) for a in acc if a in p]
            w[idx] = 1
            v = float(w @ m.cov_params().to_numpy() @ w)
            rows_a9.append({"panel": panel, "series": label, "window": window,
                            "term": f"absolute slope after {b}", "coef": float(w @ p.to_numpy()),
                            "se": np.sqrt(v), "p": np.nan, "pct_change": np.nan, "N": n})

    for label, col, st, en, br, l1p in specs:
        m, n = its_model(nat, col, st, en, br, pulse=CFG.ITS_PULSE, log1p=l1p)
        record("A: 2021-2025", label, f"{st} to {en}", m, n, br)
        # optional extension to H1 2026 with a December 2025 level shift
        if (nat.ym >= CFG.ITS_EXTENDED_END).any() and nat.loc[nat.ym == CFG.ITS_EXTENDED_END, col].notna().all():
            m2, n2 = its_model(nat, col, st, CFG.ITS_EXTENDED_END, br, pulse=CFG.ITS_PULSE,
                               log1p=l1p, extra_level="2025-12")
            record("A (extended to 2026-06)", label, f"{st} to {CFG.ITS_EXTENDED_END}", m2, n2, br)

    s18, e18 = CFG.ITS_2018_WINDOW
    m, n = its_model(nat, "declarations", s18, e18, ["2018-01"])
    record("B: 2015-2019", "Employer declarations", f"{s18} to {e18}", m, n, ["2018-01"])

    # half-yearly permits around 2018
    hy = read_csv(Path(CFG.DERIVED) / "halfyear_permits.csv")
    h = hy.groupby(["year", "half"], as_index=False)["permits"].sum()
    a, b = CFG.ITS_2018_HALFYEAR_WINDOW
    h = h[(h.year >= a) & (h.year <= b)].copy()
    t = h.year + (h.half - 1) / 2
    X = sm.add_constant(pd.DataFrame({"trend": t - t.min(), "level_2018": (t >= 2018).astype(float),
                                      "slope_2018": np.where(t >= 2018, t - 2018, 0),
                                      "second_half": (h.half == 2).astype(float)}))
    mh = sm.OLS(np.log(h.permits.to_numpy()), X).fit(cov_type="HAC",
                                                     cov_kwds={"maxlags": CFG.ITS_NW_LAGS_HALFYEAR})
    record("B: half-yearly", "Work permits (half-yearly, t in years)", f"{a}H1 to {b}H2", mh,
           len(h), ["2018"])

    save_table(pd.DataFrame(rows_t6), "table6", "Interrupted time series of monthly national counts")
    save_table(pd.DataFrame(rows_a9), "appendix_A9", "Interrupted time series with standard errors")
    save_table(pd.DataFrame(rows_me), "appendix_A9_month_effects", "Calendar-month effects")
    appendix_a11()


def appendix_a11():
    """2025 comparisons: issuance by access group (monthly) + report extracts."""
    mo = read_csv(require(Path(CFG.DERIVED) / "monthly_origin.csv"))
    mo["year"] = mo.ym.str[:4].astype(int)
    mo["month"] = mo.ym.str[5:7].astype(int)
    mo["group"] = np.where(mo.iso3.isin(CFG.DECL6), "declaration/notification origins",
                           "origins without declaration or notification access")
    rows = []
    for series in ("permits", "seasonal"):
        d = mo[(mo.series == series) & mo.year.isin([2024, 2025])]
        for per, months in (("January-May", range(1, 6)), ("June-December", range(6, 13))):
            g = d[d.month.isin(months)].groupby(["group", "year"])["value"].sum().unstack()
            for grp, r in g.iterrows():
                rows.append({"block": "issuance by access group", "series": series, "group": grp,
                             "period": per, "value_2024": r.get(2024), "value_2025": r.get(2025),
                             "pct_change": 100 * (r.get(2025) / r.get(2024) - 1)})
    ext = Path(CFG.RAW) / "mrpips_reports" / "report_extracts.csv"
    if ext.exists():
        x = read_csv(ext)
        x = x[x.appendix_table == "A11"]
        for _, r in x.iterrows():
            rows.append({"block": "applications and processing (MRPiPS reports)",
                         "series": r["indicator"], "group": r.get("group"), "period": r["period"],
                         "value_2025": r["value"], "source": f"{r['source']}, p. {r['page']}"})
    save_table(pd.DataFrame(rows), "appendix_A11", "Applications and issuance, 2025")


if __name__ == "__main__":
    main()
