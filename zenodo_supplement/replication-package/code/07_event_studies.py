"""Step 7 - changes in declaration access (Section 5.3; Figure 4; Table 5; A8).

For each case c (Moldova 2009, Georgia 2011 [alt. 2010], Armenia 2014, Russia 2022):
  sample   = treated origin + comparison origins (never eligible, >= 500 documents);
  outcomes = work permits; all documents excluding notifications.

Event study: PPML with origin and year effects and treated x event-time dummies,
k = -1 omitted, endpoints binned at CFG.EVENT_WINDOW.
DiD summary: treated x post (k = 0..3) using up to three pre-event years
(k = -3..-1) and four event/post-event years; factor = exp(b).

Placebo inference: each comparison origin in turn is assigned the event (the treated
origin is removed from the placebo samples); the share of placebo estimates with
|b| >= |b_treated| is reported both as k/N and as (k+1)/(N+1), together with N
(reviewer comment 11). Placebo percentiles (2.5, 97.5) of the event-study
coefficients are the grey bands in Figure 4.

Outputs: table5.csv, appendix_A8_event_coefficients.csv, appendix_A8_did.csv,
         appendix_A8_placebo_did_draws.csv, event_study_plotdata.csv
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from lib.common import CFG, get_logger, load_crosswalk, load_panel, read_csv, save_table, write_csv  # noqa: E402,E501
from lib.ppml import ppml  # noqa: E402

import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

log = get_logger("07_event_studies")
OUTCOMES = {"permits": "Work permits", "docs_excl_notif": "All documents excl. notifications"}


def event_terms(d: pd.DataFrame, treated: str, e: int):
    kmin, kmax = CFG.EVENT_WINDOW
    k = (d.year - e).clip(kmin, kmax)
    names = []
    for kk in range(kmin, kmax + 1):
        if kk == -1:
            continue
        nm = f"ev_{kk:+d}"
        d[nm] = ((d.iso3 == treated) & (k == kk)).astype(float)
        if d[nm].sum() > 0:
            names.append(nm)
    return d, names


def did(d, treated, e, y):
    w = d[(d.year >= e - CFG.DID_PRE) & (d.year <= e + CFG.DID_POST - 1)].copy()
    w["treat_post"] = ((w.iso3 == treated) & (w.year >= e)).astype(float)
    r = ppml(w, y, ["treat_post"], ["iso3", "year"], "iso3")
    return r.row("treat_post")


def run_case(p, case, iso, e, label, comp, logtag=""):
    out_coef, out_did, out_draws = [], [], []
    base = p[p.iso3.isin(comp | {iso})].copy()
    placebo_base = p[p.iso3.isin(comp)].copy()
    for y, ylab in OUTCOMES.items():
        d, terms = event_terms(base.copy(), iso, e)
        r = ppml(d, y, terms, ["iso3", "year"], "iso3")
        b, se, pv = did(base, iso, e, y)
        # placebos
        pl_did, pl_ev = [], []
        for c in sorted(comp):
            try:
                bb, _, _ = did(placebo_base, c, e, y)
            except Exception:
                bb = np.nan
            pl_did.append(bb)
            try:
                dd, tt = event_terms(placebo_base.copy(), c, e)
                rr = ppml(dd, y, tt, ["iso3", "year"], "iso3")
                pl_ev.append(rr.coef.reindex(terms))
            except Exception:
                pl_ev.append(pd.Series(np.nan, index=terms))
        pl_did = np.array(pl_did, float)
        ok = np.isfinite(pl_did)
        N = int(ok.sum())
        k = int(np.sum(np.abs(pl_did[ok]) >= abs(b)))
        out_did.append({"case": case, "label": label, "outcome": ylab, "event_year": e,
                        "coef": b, "factor": np.exp(b), "pct_change": 100 * (np.exp(b) - 1),
                        "cluster_se": se, "placebo_N": N, "placebo_k": k,
                        "p_k_over_N": k / N if N else np.nan,
                        "p_k1_over_N1": (k + 1) / (N + 1) if N else np.nan,
                        "n_comparison": len(comp)})
        for c, v in zip(sorted(comp), pl_did):
            out_draws.append({"case": case, "outcome": ylab, "placebo_origin": c, "coef": v})
        pe = pd.DataFrame(pl_ev)
        for t in terms:
            col = pe[t] if t in pe else pd.Series(dtype=float)
            out_coef.append({"case": case, "label": label, "outcome": ylab,
                             "event_time": int(t[3:]), "calendar_year": e + int(t[3:]),
                             "coef": r.coef[t], "cluster_se": r.se[t],
                             "placebo_p2_5": np.nanpercentile(col, 2.5) if col.notna().any() else np.nan,
                             "placebo_p97_5": np.nanpercentile(col, 97.5) if col.notna().any() else np.nan,
                             "placebo_N": int(col.notna().sum()),
                             "binned": int(t[3:]) in CFG.EVENT_WINDOW})
        log.info("%s %s: DiD %.3f (factor %.2f), placebo k/N=%d/%d", case, y, b, np.exp(b), k, N)
    return out_coef, out_did, out_draws


def main():
    p = load_panel(with_covariates=False)
    flags = read_csv(Path(CFG.DERIVED) / "regression_sample.csv")
    comp = set(flags.loc[flags.comparison70 == 1, "iso3"])
    log.info("comparison origins: %d (article: 70)", len(comp))
    cw = load_crosswalk()
    post_soviet = set(cw.loc[cw.former_ussr.astype(int) == 1, "iso3"]) & comp

    coefs, dids, draws = [], [], []
    cases = dict(CFG.EVENT_CASES)
    cases.update(CFG.EVENT_ALTERNATIVES)
    for case, (iso, e, label) in cases.items():
        a, b, c = run_case(p, case, iso, e, label, comp)
        coefs += a; dids += b; draws += c
    # Armenia with post-Soviet comparison origins only (Section 6.3.1, "roughly a doubling")
    a, b, c = run_case(p, "ARM_2014_postsoviet", "ARM", 2014,
                       f"Armenia enters (2014), post-Soviet comparison origins (n={len(post_soviet)})",
                       post_soviet)
    coefs += a; dids += b; draws += c

    did_df = pd.DataFrame(dids)
    save_table(did_df, "appendix_A8_did", "DiD summaries with placebo inference")
    save_table(pd.DataFrame(coefs), "appendix_A8_event_coefficients",
               "Event-study coefficients and placebo percentiles")
    write_csv(pd.DataFrame(draws), Path(CFG.TABLES) / "appendix_A8_placebo_did_draws.csv")
    write_csv(pd.DataFrame(coefs), Path(CFG.TABLES) / "event_study_plotdata.csv")

    t5 = []
    for case, (iso, e, label) in CFG.EVENT_CASES.items():
        r = did_df[did_df.case == case].set_index("outcome")
        def eff(o):
            f = r.loc[o, "factor"]
            return f"x{f:.1f}" if f >= 2 else f"{100 * (f - 1):+.0f}%"
        t5.append({"Change": label,
                   "Work permits": eff("Work permits"),
                   "Permutation p, k/N": f"{r.loc['Work permits', 'p_k_over_N']:.2f}",
                   "Permutation p, (k+1)/(N+1)": f"{r.loc['Work permits', 'p_k1_over_N1']:.2f}",
                   "N placebo (permits)": int(r.loc["Work permits", "placebo_N"]),
                   "All documents excl. notifications": eff("All documents excl. notifications"),
                   "Permutation p, k/N ": f"{r.loc['All documents excl. notifications', 'p_k_over_N']:.2f}",
                   "Permutation p, (k+1)/(N+1) ": f"{r.loc['All documents excl. notifications', 'p_k1_over_N1']:.2f}",
                   "N placebo (documents)": int(r.loc["All documents excl. notifications", "placebo_N"])})
    save_table(pd.DataFrame(t5), "table5", "DiD summary of changes in declaration access")


if __name__ == "__main__":
    main()
