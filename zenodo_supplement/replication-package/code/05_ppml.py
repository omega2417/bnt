"""Step 5 - PPML gravity models (Section 5.2; Tables 3-4; Online Appendix A7).

Outputs
    output/tables/table3.csv, table4.csv, appendix_A7.csv, appendix_A7_leave_one_out.csv
    output/tables/ppml_estimates_long.csv   every coefficient of every model (machine-readable)
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from lib.common import CFG, fmt_coef, get_logger, load_panel, save_table  # noqa: E402
from lib.ppml import lincom, ppml  # noqa: E402

import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
import statsmodels.api as sm  # noqa: E402

log = get_logger("05_ppml")

POLICY = ["decl_access_share", "eu_visa_free_share", "decl_group_2018", "decl_group_2022"]
SHOCKS = ["shock_ua2014", "shock_ua2022", "shock_by2021", "shock_ru2022"]
FE_X = ["flow_recent", "rel_income_l1", "unemp_l1", *POLICY, *SHOCKS]
POOLED_X = ["flow_recent", "ppp_gap_l1", "unemp_l1", "ln_dist", "contiguity", "former_ussr",
            "slavic_language", "ln_pop_l1", "decl_access_share", "eu_visa_free_share"]
LABELS = {
    "flow_recent": "ln recent flow (t-1 to t-3)",
    "flow_x_access": "x origins with declaration access",
    "flow_x_other": "x other origins",
    "rel_income_l1": "Relative real income (RY, t-1)",
    "ppp_gap_l1": "ln PPP income gap",
    "unemp_l1": "Origin unemployment rate",
    "ln_dist": "ln distance", "contiguity": "Contiguity", "former_ussr": "Former USSR",
    "slavic_language": "Slavic language", "ln_pop_l1": "ln population",
    "decl_access_share": "Declaration access", "eu_visa_free_share": "EU visa freedom",
    "decl_group_2018": "Declaration origins x 2018+", "decl_group_2022": "Declaration origins x 2022+",
    "shock_ua2014": "Ukraine 2014+", "shock_ua2022": "Ukraine 2022+",
    "shock_by2021": "Belarus 2021+", "shock_ru2022": "Russia 2022+",
}

LONG: list[dict] = []


def est(name, df, y, x, fe=("iso3", "year")):
    r = ppml(df, y, x, list(fe), cluster="iso3")
    if not r.converged:
        log.warning("%s did not converge", name)
    if r.dropped_vars:
        log.info("%s: collinear regressors dropped: %s", name, r.dropped_vars)
    for v in x:
        b, se, p = r.row(v)
        LONG.append({"model": name, "term": v, "coef": b, "se": se, "p": p, "nobs": r.nobs,
                     "origins": r.n_clusters, "pseudo_r2": r.pseudo_r2})
    log.info("%-40s N=%d origins=%d", name, r.nobs, r.n_clusters)
    return r


def table3(p):
    m = {
        "(1) Pooled, permits": est("T3c1", p, "permits", POOLED_X, fe=("year",)),
        "(2) Permits": est("T3c2", p, "permits", FE_X),
        "(3) Permits": est("T3c3", p, "permits",
                           ["flow_x_access", "flow_x_other"] + FE_X[1:]),
        "(4) All documents excl. notifications": est("T3c4", p, "docs_excl_notif", FE_X),
        "(5) Permits, excl. UA and BY": est(
            "T3c5", p[~p.iso3.isin(["UKR", "BLR"])], "permits",
            [v for v in FE_X if v not in ("shock_ua2014", "shock_ua2022", "shock_by2021")]),
        "(6) Permits, never-eligible origins": est(
            "T3c6", p[p.decl_ever == 0], "permits", ["flow_recent", "rel_income_l1", "unemp_l1"]),
    }
    rows = []
    for v, lab in LABELS.items():
        rows.append([lab] + [fmt_coef(*r.row(v)) if v in r.coef.index else "" for r in m.values()])
    rows.append(["Origin effects", "no", "yes", "yes", "yes", "yes", "yes"])
    rows.append(["Year effects"] + ["yes"] * 6)
    rows.append(["Observations"] + [f"{r.nobs:,}" for r in m.values()])
    rows.append(["Origins"] + [str(r.n_clusters) for r in m.values()])
    rows.append(["Pseudo R2"] + [f"{r.pseudo_r2:.3f}" for r in m.values()])
    t3 = pd.DataFrame(rows, columns=[""] + list(m))
    save_table(t3, "table3", "PPML gravity estimates, 2011-2025")
    return m


def ols_fe(df, y, x):
    d = df[[y, *x, "iso3", "year"]].dropna()
    X = pd.get_dummies(d[["iso3", "year"]].astype(str), drop_first=True, dtype=float)
    X = sm.add_constant(pd.concat([d[x], X], axis=1))
    r = sm.OLS(d[y], X).fit(cov_type="cluster", cov_kwds={"groups": pd.factorize(d.iso3)[0]})
    return r, len(d)


def table4(p):
    rows = []

    def add(label, r, flow="flow_recent", older="flow_older", inc="rel_income_l1"):
        rows.append([label,
                     fmt_coef(*r.row(flow)) if flow in r.coef.index else "",
                     fmt_coef(*r.row(older)) if older in r.coef.index else "",
                     fmt_coef(*r.row(inc)) if inc in r.coef.index else "",
                     f"{r.nobs:,}"])

    base_rest = FE_X[1:]
    add("Baseline (Table 3, column 2)", est("T4_base", p, "permits", FE_X))
    add("Older flow only", est("T4_older", p, "permits", ["flow_older"] + base_rest))
    add("Recent and older flows", est("T4_both", p, "permits", ["flow_recent", "flow_older"] + base_rest))
    add("Pre-sample mean, no origin effects (all-zero origins retained)",
        est("T4_presample", p, "permits", FE_X + ["ln_presample_mean", "presample_mean_zero"],
            fe=("year",)))
    r = est("T4_permits_flow", p, "permits", ["flow_recent_permits"] + base_rest)
    add("Flow built from permits only", r, flow="flow_recent_permits")
    add("Indicator for zero flow", est("T4_zero", p, "permits", FE_X + ["flow_zero"]))
    add("Excluding 2020-2021", est("T4_no2021", p[~p.year.isin([2020, 2021])], "permits", FE_X))
    add("2011-2024 only", est("T4_to2024", p[p.year <= 2024], "permits", FE_X))
    x2 = ["flow_recent", "rel_income_l2", "unemp_l2", *POLICY, *SHOCKS]
    add("Covariates lagged two years", est("T4_lag2", p, "permits", x2), inc="rel_income_l2")
    xu = ["flow_recent", "usd_gap_l1", "unemp_l1", *POLICY, *SHOCKS]
    add("Income gap in current US$ (log)", est("T4_usd", p, "permits", xu), inc="usd_gap_l1")
    q = p.assign(lny=np.log1p(p.permits))
    o, n = ols_fe(q, "lny", FE_X)
    rows.append(["OLS, log(1+permits)", fmt_coef(o.params["flow_recent"], o.bse["flow_recent"],
                                                 o.pvalues["flow_recent"]), "",
                 fmt_coef(o.params["rel_income_l1"], o.bse["rel_income_l1"],
                          o.pvalues["rel_income_l1"]), f"{n:,}"])
    add("Outcome: all documents incl. notifications", est("T4_alldocs", p, "docs_all", FE_X))
    loo = leave_one_out(p, FE_X, "flow_recent", "T4_loo")
    rows.append(["Leave one of the 20 largest origins out (range)",
                 f"{loo.coef.min():.2f} to {loo.coef.max():.2f}", "", "", ""])
    t4 = pd.DataFrame(rows, columns=["Specification", "Recent flow (t-1 to t-3)",
                                     "Older flow (t-4 to t-6)", "Relative real income",
                                     "Observations"])
    save_table(t4, "table4", "Robustness of the persistence elasticity and relative real income")
    return loo


def leave_one_out(p, x, var, tag, n=20):
    tot = p.groupby("iso3")["docs_excl_notif"].sum().sort_values(ascending=False)
    rows = []
    for iso in tot.index[:n]:
        r = est(f"{tag}_{iso}", p[p.iso3 != iso], "permits", x)
        b, se, pv = r.row(var)
        rows.append({"origin_left_out": iso, "coef": b, "se": se, "p": pv, "nobs": r.nobs})
    return pd.DataFrame(rows)


def group_row(label, r, a="flow_x_access", o="flow_x_other"):
    d, dse, dp = lincom(r, {a: 1, o: -1})
    return {"Specification": label,
            "Declaration-access origins": fmt_coef(*r.row(a)),
            "Other origins": fmt_coef(*r.row(o)),
            "Difference (analytic cluster s.e.)": fmt_coef(d, dse, dp),
            "Observations": f"{r.nobs:,}", "Origins": r.n_clusters}


def appendix_a7(p, loo):
    g = ["flow_x_access", "flow_x_other"]
    rest = FE_X[1:]
    no_reform = [v for v in rest if v not in ("decl_group_2018", "decl_group_2022")]
    rows = [
        group_row("Baseline (Table 3, column 3)", est("A7_base", p, "permits", g + rest)),
        group_row("Lagged counts from permits only",
                  est("A7_permits_flow", p, "permits", ["flowp_x_access", "flowp_x_other"] + rest),
                  "flowp_x_access", "flowp_x_other"),
        group_row("Excluding Ukraine",
                  est("A7_noUKR", p[p.iso3 != "UKR"], "permits",
                      g + [v for v in rest if not v.startswith("shock_ua")])),
        group_row("Without reform indicators, 2011-2024",
                  est("A7_noreform_2024", p[p.year <= 2024], "permits", g + no_reform)),
        group_row("Without reform indicators, 2011-2025",
                  est("A7_noreform_2025", p, "permits", g + no_reform)),
        group_row("With reform indicators, 2011-2024",
                  est("A7_reform_2024", p[p.year <= 2024], "permits", g + rest)),
    ]
    save_table(pd.DataFrame(rows), "appendix_A7", "Additional persistence estimates by access group")
    save_table(loo, "appendix_A7_leave_one_out", "Leave-one-out estimates, 20 largest origins")


def main():
    p = load_panel(with_covariates=True)
    p = p[p.year.isin(CFG.EST_YEARS)].copy()
    table3(p)
    loo = table4(p)
    appendix_a7(p, loo)
    save_table(pd.DataFrame(LONG), "ppml_estimates_long")


if __name__ == "__main__":
    main()
