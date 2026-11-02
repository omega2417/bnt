"""Step 6 - inference for the group difference in persistence (Online Appendix A6).

Model: Table 3, column 3, re-parameterised as
    flow_recent (common slope) + flow_x_access (difference: access minus other origins)
so that the difference is a single coefficient.

Reported (reviewer comment 10):
  * analytic cluster-robust interval (normal approximation);
  * pairs cluster bootstrap, CFG.N_PAIRS_BOOT (>= 999) draws, percentile interval;
    draws without any declaration-access origin are not identified and are counted;
  * wild cluster score bootstrap (Kline and Santos 2012), null imposed,
    CFG.N_WILD_BOOT draws, Rademacher and Webb weights; p-value of H0: difference = 0
    and a confidence set obtained by test inversion.
Only six clusters ever have access, so all intervals should be read as approximate.

Output: output/tables/appendix_A6.csv, appendix_A6_bootstrap_draws.csv,
        appendix_A6_inversion_grid.csv
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from lib.common import CFG, get_logger, load_panel, rng, save_table, write_csv  # noqa: E402
from lib.ppml import pairs_cluster_bootstrap, ppml, wild_score_ci, wild_score_test  # noqa: E402

import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

log = get_logger("06_bootstrap")
X_REST = ["rel_income_l1", "unemp_l1", "decl_access_share", "eu_visa_free_share",
          "decl_group_2018", "decl_group_2022", "shock_ua2014", "shock_ua2022",
          "shock_by2021", "shock_ru2022"]
X = ["flow_recent", "flow_x_access"] + X_REST
FE = ["iso3", "year"]


def main():
    p = load_panel(with_covariates=True)
    p = p[p.year.isin(CFG.EST_YEARS)].copy()
    r = ppml(p, "permits", X, FE, "iso3")
    d, se = r.coef["flow_x_access"], r.se["flow_x_access"]
    rows = [{"method": "Point estimate (access minus other)", "estimate": d, "lower": np.nan,
             "upper": np.nan, "p_value": r.pval["flow_x_access"], "draws": np.nan,
             "note": f"N={r.nobs}, origins={r.n_clusters}"},
            {"method": "Analytic cluster-robust 95% interval", "estimate": d,
             "lower": d - 1.96 * se, "upper": d + 1.96 * se,
             "p_value": r.pval["flow_x_access"], "draws": np.nan, "note": "G/(G-1) correction"}]

    log.info("pairs cluster bootstrap, %d draws", CFG.N_PAIRS_BOOT)
    draws = pairs_cluster_bootstrap(p, "permits", X, FE, "iso3",
                                    lambda res: res.coef["flow_x_access"],
                                    CFG.N_PAIRS_BOOT, rng(6), log)
    ok = np.isfinite(draws)
    write_csv(pd.DataFrame({"draw": np.arange(1, len(draws) + 1), "difference": draws}),
              Path(CFG.TABLES) / "appendix_A6_bootstrap_draws.csv")
    lo, hi = np.percentile(draws[ok], [2.5, 97.5])
    rows.append({"method": "Pairs cluster bootstrap, percentile 95% interval", "estimate": d,
                 "lower": lo, "upper": hi,
                 "p_value": float(np.mean(np.abs(draws[ok] - d) >= abs(d))),
                 "draws": int(ok.sum()),
                 "note": f"{int((~ok).sum())} of {len(draws)} draws not identified"})

    grid = np.round(np.linspace(d - 6 * se, d + 6 * se, 121), 6)
    inv = []
    for k, w in enumerate(CFG.WILD_WEIGHTS):
        pv, t = wild_score_test(p, "permits", X, FE, "iso3", "flow_x_access", 0.0,
                                CFG.N_WILD_BOOT, rng(60 + k), w)
        lo, hi, open_end, g = wild_score_ci(p, "permits", X, FE, "iso3", "flow_x_access", grid,
                                            CFG.N_WILD_BOOT, CFG.SEED + 60 + k, w)
        g["weights"] = w
        inv.append(g)
        rows.append({"method": f"Wild cluster score bootstrap ({w}), test inversion",
                     "estimate": d, "lower": lo, "upper": hi, "p_value": pv,
                     "draws": CFG.N_WILD_BOOT,
                     "note": "null imposed; p for H0: difference = 0"
                             + ("; interval reaches the grid limit" if open_end else "")})
        log.info("wild score (%s): p=%.4f, CI=[%.3f, %.3f]", w, pv, lo, hi)
    save_table(pd.DataFrame(rows), "appendix_A6", "Group difference in persistence")
    write_csv(pd.concat(inv), Path(CFG.TABLES) / "appendix_A6_inversion_grid.csv")


if __name__ == "__main__":
    main()
