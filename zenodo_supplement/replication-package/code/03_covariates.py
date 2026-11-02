"""Step 3 - covariates and regression samples (Section 4.2).

Input
    data/derived/panel_origin_year.csv, data/policy/policy_coding.csv
    data/raw/worldbank/wdi_snapshot.csv     iso3, year, indicator, value (long)
    data/raw/geonames/countryInfo.txt, cities15000.txt (or .zip)
    data/crosswalks/citizenship_crosswalk.csv (contiguity, former USSR, Slavic language)
Output
    data/derived/panel_covariates.csv
    data/derived/regression_sample.csv      iso3, year and sample flags

Definitions (codebook/variables.csv has the full list)
    flow_recent   ln(1 + permits + declarations + seasonal permits in t-1..t-3)
    flow_older    ln(1 + the same sum in t-4..t-6)         (NA when t-6 < 2008)
    flow_recent_permits  ln(1 + permits in t-1..t-3)
    rel_income_l1 RY(j,t-1) = ln I(POL,t-1) - ln I(j,t-1), where I is the cumulated
                  index of real GDP-per-capita growth (NY.GDP.PCAP.KD.ZG), base 2006 = 1.
                  Called "relative real income" throughout (reviewer comment 9).
    ppp_gap_l1    ln(PPP GDP pc Poland / PPP GDP pc origin), t-1
    usd_gap_l1    ln(current-USD GDP pc Poland / origin), t-1
    unemp_l1      ILO modelled unemployment rate of the origin, t-1
    ln_pop_l1     ln population of the origin, t-1
    ln_dist       ln great-circle distance Warsaw - origin capital (km), GeoNames
"""
from __future__ import annotations

import io
import sys
import zipfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from lib.common import CFG, get_logger, load_crosswalk, load_panel, load_policy, read_csv, require, write_csv  # noqa: E402,E501

import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

log = get_logger("03_covariates")
WARSAW = (52.22977, 21.01178)
IND = {"NY.GDP.PCAP.KD.ZG": "gdppc_growth", "NY.GDP.PCAP.PP.CD": "gdppc_ppp",
       "NY.GDP.PCAP.CD": "gdppc_usd", "SL.UEM.TOTL.ZS": "unemp", "SP.POP.TOTL": "pop"}


def haversine(lat1, lon1, lat2, lon2):
    r = np.pi / 180
    a = (np.sin((lat2 - lat1) * r / 2) ** 2
         + np.cos(lat1 * r) * np.cos(lat2 * r) * np.sin((lon2 - lon1) * r / 2) ** 2)
    return 2 * 6371.0088 * np.arcsin(np.sqrt(a))


def capitals() -> pd.DataFrame:
    g = Path(CFG.RAW) / "geonames"
    ci = pd.read_csv(require(g / "countryInfo.txt"), sep="\t", comment="#", header=None,
                     keep_default_na=False, dtype=str)
    ci = ci.iloc[:, [0, 1, 5]]
    ci.columns = ["iso2", "iso3", "capital"]
    if (g / "cities15000.txt").exists():
        txt = (g / "cities15000.txt").read_text(encoding="utf-8")
    else:
        with zipfile.ZipFile(require(g / "cities15000.zip")) as z:
            txt = z.read("cities15000.txt").decode("utf-8")
    cities = pd.read_csv(io.StringIO(txt), sep="\t", header=None, keep_default_na=False,
                         dtype=str, quoting=3)
    cities = cities.iloc[:, [1, 2, 4, 5, 7, 8]]
    cities.columns = ["name", "asciiname", "lat", "lon", "fcode", "iso2"]
    cities[["lat", "lon"]] = cities[["lat", "lon"]].astype(float)
    pplc = cities[cities.fcode == "PPLC"].drop_duplicates("iso2")
    out = ci.merge(pplc[["iso2", "lat", "lon"]], on="iso2", how="left")
    miss = out.lat.isna()
    if miss.any():   # fall back to a name match within the country
        byname = cities.drop_duplicates(["iso2", "name"]).set_index(["iso2", "name"])
        for i in out.index[miss]:
            key = (out.at[i, "iso2"], out.at[i, "capital"])
            if key in byname.index:
                out.loc[i, ["lat", "lon"]] = byname.loc[key, ["lat", "lon"]].to_numpy()
    out["dist_km"] = haversine(WARSAW[0], WARSAW[1], out.lat, out.lon)
    return out[["iso3", "capital", "lat", "lon", "dist_km"]]


def wdi() -> pd.DataFrame:
    w = read_csv(require(Path(CFG.RAW) / "worldbank" / "wdi_snapshot.csv",
                         "Run code/download_sources.py --only worldbank."))
    w = w[w.indicator.isin(IND)].assign(var=lambda d: d.indicator.map(IND))
    w = w.pivot_table(index=["iso3", "year"], columns="var", values="value").reset_index()
    # cumulated real-income index, base 2006 = 1; a gap breaks the index (NA afterwards)
    w = w.sort_values(["iso3", "year"])
    def cum(g):
        gr = g.set_index("year")["gdppc_growth"].reindex(CFG.WB_YEARS)
        idx = (1 + gr / 100).copy()
        idx.iloc[0] = 1.0                       # base year
        # numpy cumsum propagates NaN, so a missing growth year breaks the index
        return pd.Series(np.cumsum(np.log(idx.to_numpy(float))), index=CFG.WB_YEARS)
    li = w.groupby("iso3").apply(cum).stack().rename("ln_index").reset_index()
    li.columns = ["iso3", "year", "ln_index"]
    w = w.merge(li, on=["iso3", "year"], how="right")
    pol = w[w.iso3 == "POL"].set_index("year")
    w["rel_income"] = w.year.map(pol["ln_index"]) - w["ln_index"]
    w["ppp_gap"] = np.log(w.year.map(pol["gdppc_ppp"]) / w["gdppc_ppp"])
    w["usd_gap"] = np.log(w.year.map(pol["gdppc_usd"]) / w["gdppc_usd"])
    w["ln_pop"] = np.log(w["pop"])
    keep = ["rel_income", "ppp_gap", "usd_gap", "unemp", "ln_pop"]
    out = w[["iso3", "year"] + keep].copy()
    l1 = out.copy(); l1["year"] += 1
    l2 = out.copy(); l2["year"] += 2
    l1 = l1.rename(columns={k: f"{k}_l1" for k in keep})
    l2 = l2.rename(columns={k: f"{k}_l2" for k in keep})
    return l1.merge(l2, on=["iso3", "year"], how="outer")


def rolling_sum(s: pd.Series, lags: range) -> pd.Series:
    out = sum(s.shift(k) for k in lags)
    return out


def main() -> None:
    p = load_panel().sort_values(["iso3", "year"])
    pc = load_policy()
    cw = load_crosswalk()
    p = p.merge(pc, on=["iso3", "year"], how="left")
    d = p[["permits", "declarations", "seasonal"]].fillna(0).sum(axis=1)
    p["_d"], p["_p"] = d, p["permits"].fillna(0)
    g = p.groupby("iso3", group_keys=False)
    p["flow_recent"] = np.log1p(g["_d"].apply(lambda s: rolling_sum(s, range(1, 4))))
    p["flow_older"] = np.log1p(g["_d"].apply(lambda s: rolling_sum(s, range(4, 7))))
    p["flow_recent_permits"] = np.log1p(g["_p"].apply(lambda s: rolling_sum(s, range(1, 4))))
    p["flow_zero"] = (p["flow_recent"] == 0).astype(float)
    pre = p[p.year.isin(CFG.PRESAMPLE_YEARS)].groupby("iso3")["permits"].mean()
    p["presample_mean_zero"] = p.iso3.map(pre == 0).astype(float)
    p["ln_presample_mean"] = p.iso3.map(np.log(pre.where(pre > 0, 1.0)))
    p["flow_x_access"] = p["flow_recent"] * p["decl_ever"]
    p["flow_x_other"] = p["flow_recent"] * (1 - p["decl_ever"])
    p["flowp_x_access"] = p["flow_recent_permits"] * p["decl_ever"]
    p["flowp_x_other"] = p["flow_recent_permits"] * (1 - p["decl_ever"])

    p = p.merge(wdi(), on=["iso3", "year"], how="left")
    cap = capitals()
    p = p.merge(cap[["iso3", "dist_km"]], on="iso3", how="left")
    p["ln_dist"] = np.log(p["dist_km"])
    p = p.merge(cw[["iso3", "contiguity", "former_ussr", "slavic_language"]], on="iso3", how="left")
    miss_dist = sorted(p.loc[p.ln_dist.isna(), "iso3"].unique())
    if miss_dist:
        log.warning("no capital coordinates for: %s", ", ".join(miss_dist))
    p = p.drop(columns=["_d", "_p"])
    write_csv(p, Path(CFG.DERIVED) / "panel_covariates.csv")

    # ---- sample flags ----------------------------------------------------------
    est = p[p.year.isin(CFG.EST_YEARS)].copy()
    base_vars = ["permits", "flow_recent", "rel_income_l1", "unemp_l1"]
    ok = est[base_vars].notna().all(1)
    nonzero = est[ok].groupby("iso3")["permits"].transform("sum") > 0
    est["baseline"] = 0
    est.loc[nonzero[nonzero].index, "baseline"] = 1
    est["excl_UA_BY"] = (est.baseline == 1) & ~est.iso3.isin(["UKR", "BLR"])
    est["never_eligible"] = (est.baseline == 1) & (est.decl_ever == 0)
    tot = p.groupby("iso3")["docs_excl_notif"].sum()
    comp = set(tot[(tot >= CFG.COMPARISON_MIN_DOCS)].index) - set(CFG.DECL6)
    est["comparison70"] = est.iso3.isin(comp)
    flags = est[["iso3", "year", "baseline", "excl_UA_BY", "never_eligible", "comparison70"]].astype(
        {"baseline": int, "excl_UA_BY": int, "never_eligible": int, "comparison70": int})
    write_csv(flags, Path(CFG.DERIVED) / "regression_sample.csv")
    log.info("baseline origins: %d (article: 148); comparison origins: %d (article: 70)",
             flags[flags.baseline == 1].iso3.nunique(), len(comp))


if __name__ == "__main__":
    main()
