"""Smoke test with SYNTHETIC data - checks that the pipeline runs end to end.

The numbers produced by this test are random and have NO relation to the article.
Everything is written to a temporary directory; the package's own data/ and
output/ folders are not touched.

    python tests/smoke_test.py            # quick: 49 pairs / 199 wild draws
    python tests/smoke_test.py --keep     # keep the temporary directory
"""
from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

import numpy as np
import pandas as pd

PKG = Path(__file__).resolve().parents[1]


def make(root: Path, seed=1):
    r = np.random.default_rng(seed)
    for d in ["data/raw/mrpips", "data/raw/worldbank", "data/raw/geonames", "data/raw/mrpips_reports",
              "data/crosswalks", "data/policy", "data/derived", "codebook"]:
        (root / d).mkdir(parents=True, exist_ok=True)
    for f in ["data/crosswalks/citizenship_crosswalk.csv", "data/policy/access_spells.csv",
              "data/policy/legal_acts.csv", "data/policy/document_duration.csv",
              "data/raw/mrpips_reports/report_extracts.csv", "data/raw/mrpips_reports/zus_stock.csv",
              "codebook/variables.csv"]:
        shutil.copy(PKG / f, root / f)
    cw = pd.read_csv(root / "data/crosswalks/citizenship_crosswalk.csv", keep_default_na=False)
    decl6 = ["ARM", "BLR", "GEO", "MDA", "RUS", "UKR"]
    pool = cw[(cw.eu_efta == 0) & (cw.special == "") & (cw.iso3 != "POL") & ~cw.iso3.isin(decl6)]
    others = pool.sample(158, random_state=seed)
    origins = pd.concat([cw[cw.iso3.isin(decl6)], others])
    alpha = dict(zip(origins.iso3, r.normal(4, 2, len(origins))))
    for o in decl6:
        alpha[o] = 8
    alpha["UKR"] = 11
    months = range(1, 13)
    inv, tmap = [], []

    def sheet(name, series, freq, year, df, layout, value_cols, half=None):
        p = root / "data/raw/mrpips" / name
        with pd.ExcelWriter(p) as w:
            pd.DataFrame([["Synthetic table - not real data"]]).to_excel(w, header=False, index=False)
            df.to_excel(w, startrow=2, index=False)
        inv.append({"file": name, "url": "NA", "series": series, "period": str(year), "frequency": freq,
                    "download_date": "NA", "sha256": "NA", "use": 1, "revision_note": "synthetic"})
        tmap.append({"file": name, "sheet": 0, "series": series, "frequency": freq, "year": year,
                     "half": half if half else "NA", "header_row": 3, "citizenship_col": "Obywatelstwo",
                     "layout": layout, "value_cols": value_cols})

    for y in range(2008, 2026):
        lam = {o: np.exp(alpha[o] + 0.08 * (y - 2008) + (1.5 if o not in decl6 and y >= 2022 else 0))
               for o in origins.iso3}
        pm = {o: r.poisson(lam[o] * 0.3) for o in lam}
        names = origins.set_index("iso3").polish_name
        tab = pd.DataFrame({"Obywatelstwo": [names[o] for o in lam], "Liczba": [pm[o] for o in lam]})
        tab = pd.concat([tab, pd.DataFrame({"Obywatelstwo": ["Ogółem"], "Liczba": [tab.Liczba.sum()]})])
        sheet(f"permits_{y}.xlsx", "permits", "annual", y, tab, "long", "Liczba")
        h1 = {o: int(pm[o] * r.uniform(0.4, 0.6)) for o in pm}
        th = pd.DataFrame({"Obywatelstwo": [names[o] for o in pm], "I półrocze": [h1[o] for o in pm],
                           "II półrocze": [pm[o] - h1[o] for o in pm]})
        sheet(f"permits_halfyear_{y}.xlsx", "permits", "halfyear", y, th, "wide_halves",
              "I półrocze|II półrocze")
        if y >= 2021:
            tm = pd.DataFrame({"Obywatelstwo": [names[o] for o in pm]})
            for m in months:
                tm[f"m{m}"] = [r.poisson(max(pm[o], 1) / 12) for o in pm]
            sheet(f"permits_monthly_{y}.xlsx", "permits", "monthly", y, tm, "wide_months",
                  "|".join(f"m{m}" for m in months))
        acc = [o for o in decl6 if not (o == "RUS" and y >= 2023) and not (o == "MDA" and y < 2009)
               and not (o == "GEO" and y < 2011) and not (o == "ARM" and y < 2014)]
        td = pd.DataFrame({"Obywatelstwo": [names[o] for o in acc]})
        for m in months:
            td[f"m{m}"] = [r.poisson(np.exp(alpha[o] + 1) / 12 * (0.5 if y >= 2022 else 1)) for o in acc]
        sheet(f"declarations_{y}.xlsx", "declarations", "monthly", y, td, "wide_months",
              "|".join(f"m{m}" for m in months))
        if y >= 2019:
            tp = pd.DataFrame({"Obywatelstwo": [names[o] for o in acc],
                               "Osoby": (td.iloc[:, 1:].sum(1) / 1.4).round().astype(int)})
            sheet(f"declaration_persons_{y}.xlsx", "declaration_persons", "annual", y, tp, "long", "Osoby")
        if y >= 2018:
            ts = pd.DataFrame({"Obywatelstwo": [names[o] for o in lam]})
            for m in months:
                season = 3 if 4 <= m <= 9 else 0.3
                ts[f"m{m}"] = [r.poisson(lam[o] * 0.05 * season / 12) for o in lam]
            sheet(f"seasonal_{y}.xlsx", "seasonal", "monthly", y, ts, "wide_months",
                  "|".join(f"m{m}" for m in months))
        if y >= 2022:
            tn = pd.DataFrame({"Obywatelstwo": ["Ukraina"]})
            for m in months:
                tn[f"m{m}"] = [0 if (y == 2022 and m < 3) else r.poisson(90000)]
            sheet(f"notifications_{y}.xlsx", "notifications", "monthly", y, tn, "wide_months",
                  "|".join(f"m{m}" for m in months))
    pd.DataFrame(inv).to_csv(root / "data/raw/mrpips/source_inventory.csv", index=False)
    pd.DataFrame(tmap).to_csv(root / "data/raw/mrpips/table_map.csv", index=False)

    # World Bank snapshot (synthetic)
    rows = []
    for o in list(origins.iso3) + ["POL"]:
        lvl = r.uniform(500, 40000)
        for y in range(2006, 2026):
            rows += [{"iso3": o, "year": y, "indicator": "NY.GDP.PCAP.KD.ZG", "value": r.normal(2, 3)},
                     {"iso3": o, "year": y, "indicator": "NY.GDP.PCAP.PP.CD", "value": lvl * 1.5},
                     {"iso3": o, "year": y, "indicator": "NY.GDP.PCAP.CD", "value": lvl},
                     {"iso3": o, "year": y, "indicator": "SL.UEM.TOTL.ZS", "value": r.uniform(2, 20)},
                     {"iso3": o, "year": y, "indicator": "SP.POP.TOTL", "value": r.uniform(1e5, 1e8)}]
    wb = pd.DataFrame(rows)
    wb = wb[~((wb.iso3 == origins.iso3.iloc[-1]) & (wb.indicator == "NY.GDP.PCAP.KD.ZG"))]
    wb.to_csv(root / "data/raw/worldbank/wdi_snapshot.csv", index=False)
    # GeoNames (synthetic, same column layout)
    iso2 = {o: f"{chr(65 + i // 26)}{chr(65 + i % 26)}" for i, o in enumerate(origins.iso3)}
    ci = ["\t".join([iso2[o], o, "000", "", o, f"Cap{o}"] + [""] * 13) for o in origins.iso3]
    (root / "data/raw/geonames/countryInfo.txt").write_text("#header\n" + "\n".join(ci) + "\n")
    ct = ["\t".join(["1", f"Cap{o}", f"Cap{o}", "", str(r.uniform(-40, 60)), str(r.uniform(-100, 140)),
                     "P", "PPLC", iso2[o]] + [""] * 10) for o in origins.iso3]
    (root / "data/raw/geonames/cities15000.txt").write_text("\n".join(ct) + "\n")
    zus = pd.DataFrame({"year": range(2008, 2026), "insured_foreigners": np.linspace(8e4, 1.29e6, 18).round(),
                        "insured_ukrainians": np.linspace(4e4, 8.57e5, 18).round()})
    zus.to_csv(root / "data/raw/mrpips_reports/zus_stock.csv", index=False)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--keep", action="store_true")
    a = ap.parse_args()
    tmp = Path(tempfile.mkdtemp(prefix="repl_smoke_"))
    make(tmp)
    env = dict(os.environ, REPL_ROOT=str(tmp), REPL_SMOKE="1")
    r = subprocess.run([sys.executable, str(PKG / "code/run_all.py")], env=env)
    print("temporary root:", tmp)
    tables = sorted(p.name for p in (tmp / "output/tables").glob("*.csv"))
    figs = sorted(p.name for p in (tmp / "output/figures").glob("*"))
    print(len(tables), "tables;", len(figs), "figure files")
    if not a.keep:
        shutil.rmtree(tmp, ignore_errors=True)
    sys.exit(r.returncode)


if __name__ == "__main__":
    main()
