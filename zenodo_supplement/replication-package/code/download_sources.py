"""Download (or verify) the public source files.

Usage
    python code/download_sources.py            # download what is missing
    python code/download_sources.py --verify   # only check SHA-256 against the inventory

MRPiPS tables: the script reads ``data/raw/mrpips/source_inventory.csv`` and
downloads every row whose ``url`` is filled and whose file is missing. If the
inventory has no URLs yet, ``--discover`` lists the spreadsheet links found on the
portal page so that the inventory can be completed (the portal layout changes
over time, so links are not hard-coded).

World Bank, GeoNames and REST Countries snapshots are written to their folders.
Downloaded snapshots are dated; the analysis always uses the files in data/raw,
never a live API call, so later revisions of the sources do not change results.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import re
import sys
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from lib.common import CFG, get_logger, read_csv, sha256, write_csv  # noqa: E402

import pandas as pd  # noqa: E402

log = get_logger("download_sources")
PORTAL = "https://psz.praca.gov.pl/rynek-pracy/statystyki-i-analizy/zatrudnianie-cudzoziemcow-w-polsce"
WB_INDICATORS = ["NY.GDP.PCAP.KD.ZG", "NY.GDP.PCAP.PP.CD", "NY.GDP.PCAP.CD",
                 "SL.UEM.TOTL.ZS", "SP.POP.TOTL"]
GEONAMES = ["countryInfo.txt", "cities15000.zip"]
UA = {"User-Agent": "replication-package/1.0 (academic research)"}


def fetch(url: str, dest: Path) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=120) as r, open(dest, "wb") as f:
        f.write(r.read())
    log.info("downloaded %s -> %s", url, dest)


def discover() -> None:
    req = urllib.request.Request(PORTAL, headers=UA)
    html = urllib.request.urlopen(req, timeout=120).read().decode("utf-8", "replace")
    links = sorted(set(re.findall(r'href="([^"]+\.(?:xlsx?|ods|csv)[^"]*)"', html, re.I)))
    for link in links:
        print(link if link.startswith("http") else "https://psz.praca.gov.pl" + link)
    log.info("%d spreadsheet links found on the portal page", len(links))


def mrpips(verify_only: bool) -> None:
    inv_path = Path(CFG.RAW) / "mrpips" / "source_inventory.csv"
    inv = read_csv(inv_path, dtype=str)
    changed = False
    for i, row in inv.iterrows():
        f = Path(CFG.RAW) / "mrpips" / str(row["file"])
        if not f.exists():
            if verify_only or pd.isna(row.get("url")):
                log.warning("missing: %s", f.name)
                continue
            fetch(row["url"], f)
            inv.loc[i, "download_date"] = dt.date.today().isoformat()
        h = sha256(f)
        if pd.isna(row.get("sha256")):
            inv.loc[i, "sha256"] = h
            changed = True
        elif row["sha256"] != h:
            log.error("CHECKSUM MISMATCH %s (inventory %s, file %s) - the source may have "
                      "been revised; record it in revision_note", f.name, row["sha256"], h)
    if changed and not verify_only:
        write_csv(inv, inv_path)


def worldbank() -> None:
    out = Path(CFG.RAW) / "worldbank"
    rows = []
    y0, y1 = CFG.WB_YEARS[0], CFG.WB_YEARS[-1]
    for ind in WB_INDICATORS:
        url = (f"https://api.worldbank.org/v2/country/all/indicator/{ind}"
               f"?format=json&per_page=20000&date={y0}:{y1}")
        req = urllib.request.Request(url, headers=UA)
        payload = json.loads(urllib.request.urlopen(req, timeout=300).read())
        (out / f"{ind}.json").write_text(json.dumps(payload), encoding="utf-8")
        for r in payload[1] or []:
            rows.append({"iso3": r["countryiso3code"], "year": int(r["date"]),
                         "indicator": ind, "value": r["value"]})
    df = pd.DataFrame(rows)
    df = df[df.iso3.str.len() == 3]
    write_csv(df, out / "wdi_snapshot.csv")
    (out / "SNAPSHOT_DATE.txt").write_text(dt.date.today().isoformat() + "\n")


def geonames() -> None:
    out = Path(CFG.RAW) / "geonames"
    for f in GEONAMES:
        if not (out / f).exists():
            fetch(f"https://download.geonames.org/export/dump/{f}", out / f)
    (out / "SNAPSHOT_DATE.txt").write_text(dt.date.today().isoformat() + "\n")


def restcountries() -> None:
    out = Path(CFG.RAW) / "restcountries"
    fetch("https://restcountries.com/v3.1/all?fields=cca3,name,region,subregion",
          out / "restcountries_all.json")
    (out / "SNAPSHOT_DATE.txt").write_text(dt.date.today().isoformat() + "\n")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--verify", action="store_true")
    ap.add_argument("--discover", action="store_true")
    ap.add_argument("--only", choices=["mrpips", "worldbank", "geonames", "restcountries"])
    a = ap.parse_args()
    if a.discover:
        discover()
        sys.exit(0)
    steps = {"mrpips": lambda: mrpips(a.verify), "worldbank": worldbank,
             "geonames": geonames, "restcountries": restcountries}
    for name, fn in steps.items():
        if a.only and name != a.only:
            continue
        if a.verify and name != "mrpips":
            continue
        try:
            fn()
        except Exception as e:  # keep going; report at the end
            log.error("%s failed: %s", name, e)
