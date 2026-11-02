"""Step 2 - build the harmonised panels and the policy coding.

Part A (policy coding) needs only data/policy/access_spells.csv and the crosswalk
and can be run on its own:  python code/02_harmonise.py --policy-only

Part B (document panels) needs data/derived/mrpips_long.csv from step 1.

Outputs
    data/policy/policy_coding.csv     iso3 x year access shares, group and shock indicators
    data/derived/panel_origin_year.csv
    data/derived/halfyear_permits.csv
    data/derived/monthly_national.csv
    data/derived/monthly_origin.csv   (iso3 x month x series; used for A11 and Figure 5)
    data/derived/declaration_persons.csv
    data/derived/zus_stock.csv

Zero versus NA. A channel that did not yet exist in a year (seasonal permits before
2018, notifications before 2022) is NA for every origin; a channel that existed but
recorded no documents for an origin is 0. ``channel_available_*`` flags make this
explicit. Notifications are open only to Ukrainian citizens, so other origins have 0
from 2022 (the channel exists, the origin is not eligible), which matches the way
cross-channel totals sum the procedures in operation in each year.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from lib.common import CFG, get_logger, read_csv, require, write_csv  # noqa: E402

import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

log = get_logger("02_harmonise")
SERIES = ["permits", "declarations", "seasonal", "notifications"]
FIRST_YEAR = {"permits": 2008, "declarations": 2007, "seasonal": 2018, "notifications": 2022}
FIRST_MONTH = {"permits": "2021-01", "declarations": "2007-01", "seasonal": "2018-01",
               "notifications": "2022-03"}


# --------------------------------------------------------------------------
# Part A - policy coding
# --------------------------------------------------------------------------
def year_share(start: pd.Timestamp, end: pd.Timestamp | None, year: int) -> float:
    """Share of calendar ``year`` inside [start, end); end=None means open-ended."""
    y0, y1 = pd.Timestamp(year, 1, 1), pd.Timestamp(year + 1, 1, 1)
    a = max(start, y0)
    b = min(end, y1) if end is not None else y1
    return max((b - a).days, 0) / (y1 - y0).days


def policy_coding() -> pd.DataFrame:
    spells = read_csv(require(Path(CFG.POLICY) / "access_spells.csv"), dtype=str)
    cw = read_csv(Path(CFG.CROSSWALKS) / "citizenship_crosswalk.csv", dtype=str)
    origins = sorted(cw["iso3"].dropna().unique())
    years = CFG.YEARS
    pc = pd.MultiIndex.from_product([origins, years], names=["iso3", "year"]).to_frame(index=False)
    for right, col in (("declarations", "decl_access_share"), ("eu_visa_free", "eu_visa_free_share")):
        pc[col] = 0.0
        for _, s in spells[spells.right == right].iterrows():
            st = pd.Timestamp(s["start"])
            en = pd.Timestamp(s["end"]) if pd.notna(s.get("end")) else None
            m = pc.iso3 == s["iso3"]
            pc.loc[m, col] += pc.loc[m, "year"].map(lambda y: year_share(st, en, y))
        pc[col] = pc[col].clip(0, 1).round(6)
    d6 = pc.iso3.isin(CFG.DECL6)
    pc["decl_ever"] = d6.astype(int)
    pc["decl_group_2018"] = (d6 & (pc.year >= 2018)).astype(int)
    pc["decl_group_2022"] = (d6 & (pc.year >= 2022)).astype(int)
    pc["shock_ua2014"] = ((pc.iso3 == "UKR") & (pc.year >= 2014)).astype(int)
    pc["shock_ua2022"] = ((pc.iso3 == "UKR") & (pc.year >= 2022)).astype(int)
    pc["shock_by2021"] = ((pc.iso3 == "BLR") & (pc.year >= 2021)).astype(int)
    pc["shock_ru2022"] = ((pc.iso3 == "RUS") & (pc.year >= 2022)).astype(int)
    write_csv(pc, Path(CFG.POLICY) / "policy_coding.csv")
    log.info("policy_coding.csv: %d origins x %d years", len(origins), len(years))
    return pc


# --------------------------------------------------------------------------
# Part B - document panels
# --------------------------------------------------------------------------
def annual_from_long(long: pd.DataFrame) -> pd.DataFrame:
    """Annual counts per origin and series. Priority: annual tables, then the sum of
    half-years, then the sum of months (only complete years are summed)."""
    out = []
    for (series, year), g in long[long.series.isin(SERIES)].groupby(["series", "year"]):
        for freq, need in (("annual", 1), ("halfyear", 2), ("monthly", 12)):
            h = g[g.frequency == freq]
            if h.empty:
                continue
            per = {"annual": None, "halfyear": "half", "monthly": "month"}[freq]
            if per and h[per].nunique() < need:
                log.warning("%s %s: only %d/%d %s periods; not used for annual totals",
                            series, year, h[per].nunique(), need, freq)
                continue
            a = h.groupby("iso3", as_index=False)["value"].sum()
            a["series"], a["year"], a["source_frequency"] = series, int(year), freq
            out.append(a)
            break
    return pd.concat(out, ignore_index=True)


def main(policy_only: bool) -> None:
    pc = policy_coding()
    if policy_only:
        return
    long = read_csv(require(Path(CFG.DERIVED) / "mrpips_long.csv", "Run 01_import_mrpips.py."))
    long["year"] = long["year"].astype(int)
    cw = read_csv(Path(CFG.CROSSWALKS) / "citizenship_crosswalk.csv", dtype=str)

    # ---- origin x year panel -------------------------------------------------
    ann = annual_from_long(long)
    wide = ann.pivot_table(index=["iso3", "year"], columns="series", values="value",
                           aggfunc="sum").reset_index()
    origins = sorted(set(ann.iso3))
    frame = pd.MultiIndex.from_product([origins, CFG.YEARS], names=["iso3", "year"]).to_frame(index=False)
    panel = frame.merge(wide, on=["iso3", "year"], how="left")
    for s in SERIES:
        if s not in panel:
            panel[s] = np.nan
        avail = panel.year >= FIRST_YEAR[s]
        panel[f"channel_available_{s}"] = avail.astype(int)
        panel.loc[avail, s] = panel.loc[avail, s].fillna(0)      # existed, nothing recorded
        panel.loc[~avail, s] = np.nan                             # structurally unavailable
    panel["docs_excl_notif"] = panel[["permits", "declarations", "seasonal"]].sum(axis=1, min_count=1)
    panel["docs_all"] = panel[SERIES].sum(axis=1, min_count=1)
    panel = panel.merge(cw[["iso3", "polish_name"]], on="iso3", how="left")
    cols = ["iso3", "polish_name", "year", *SERIES, "docs_excl_notif", "docs_all",
            *[f"channel_available_{s}" for s in SERIES]]
    write_csv(panel[cols].sort_values(["iso3", "year"]), Path(CFG.DERIVED) / "panel_origin_year.csv")
    log.info("panel_origin_year.csv: %d origins, %d rows", panel.iso3.nunique(), len(panel))
    if panel.iso3.nunique() != 164:
        log.warning("the article reports 164 origins; this panel has %d", panel.iso3.nunique())

    # ---- half-yearly permits -------------------------------------------------
    hy = long[(long.series == "permits") & (long.frequency == "halfyear")]
    hy = hy.groupby(["iso3", "year", "half"], as_index=False)["value"].sum()
    hy = hy.rename(columns={"value": "permits"})
    hy["half"] = hy["half"].astype(int)
    write_csv(hy.sort_values(["year", "half", "iso3"]), Path(CFG.DERIVED) / "halfyear_permits.csv")
    n_hy = hy[["year", "half"]].drop_duplicates().shape[0]
    log.info("halfyear_permits.csv: %d half-years (article: 36)", n_hy)

    # ---- monthly series --------------------------------------------------------
    mo = long[long.frequency == "monthly"].copy()
    mo["ym"] = mo.year.astype(str) + "-" + mo.month.astype(int).map("{:02d}".format)
    mo_o = mo.groupby(["iso3", "ym", "series"], as_index=False)["value"].sum()
    write_csv(mo_o, Path(CFG.DERIVED) / "monthly_origin.csv")
    nat = mo_o.pivot_table(index="ym", columns="series", values="value", aggfunc="sum").reset_index()
    for s in SERIES:
        if s not in nat:
            nat[s] = np.nan
        nat.loc[nat.ym < FIRST_MONTH[s], s] = np.nan
    write_csv(nat[["ym", *SERIES]].sort_values("ym"), Path(CFG.DERIVED) / "monthly_national.csv")

    # ---- declarations: documents and persons ---------------------------------
    dp = long[long.series == "declaration_persons"]
    if not dp.empty:
        dp = dp.groupby(["year", "iso3"], as_index=False)["value"].sum().rename(columns={"value": "persons"})
        dd = panel[["year", "iso3", "declarations"]]
        dp = dp.merge(dd, on=["year", "iso3"], how="left")[["year", "iso3", "declarations", "persons"]]
        write_csv(dp, Path(CFG.DERIVED) / "declaration_persons.csv")
        r = dp.groupby("year")[["declarations", "persons"]].sum()
        for y, row in r.iterrows():
            log.info("declarations per person %d: %.3f", y, row.declarations / row.persons)

    # ---- ZUS stock (copied from the report extracts) --------------------------
    zus = Path(CFG.RAW) / "mrpips_reports" / "zus_stock.csv"
    if zus.exists():
        z = read_csv(zus)
        write_csv(z[["year", "insured_foreigners", "insured_ukrainians"]], Path(CFG.DERIVED) / "zus_stock.csv")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--policy-only", action="store_true")
    main(ap.parse_args().policy_only)
