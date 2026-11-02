"""Step 1 - read the MRPiPS statistical tables and unify citizenship names.

Input
    data/raw/mrpips/source_inventory.csv   one row per source spreadsheet
    data/raw/mrpips/table_map.csv          how to read each sheet (layout, columns)
    data/raw/mrpips/*.xls[x]               the spreadsheets themselves
    data/crosswalks/citizenship_crosswalk.csv
Output
    data/derived/mrpips_long.csv           file, series, frequency, year, half, month,
                                           polish_name, iso3, value
    output/logs/unmatched_citizenships.csv labels that could not be matched (must be empty)

Layouts supported in table_map.csv (column ``layout``):
    long         one citizenship column and one value column
    wide_months  one citizenship column and 12 month columns (``value_cols`` = 12 refs)
    wide_halves  one citizenship column and 2 half-year columns
Columns are referenced either by Excel letter (``B``) or by header text.
Only inventory rows with ``use == 1`` are read, so superseded tables (e.g. the
original 2021 tables replaced by the revision published in 2025) are kept for
provenance but not used.
"""
from __future__ import annotations

import re
import sys
import unicodedata
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from lib.common import CFG, get_logger, read_csv, require, write_csv  # noqa: E402

import pandas as pd  # noqa: E402

log = get_logger("01_import_mrpips")
RAW = Path(CFG.RAW) / "mrpips"
TOTAL_LABELS = {"ogolem", "razem", "suma", "total", "ogolem cudzoziemcy", "w tym"}


def norm(label) -> str:
    """Normalise a citizenship label: lower case, no diacritics, no footnote marks."""
    s = str(label).strip().lower()
    s = re.sub(r"[\*¹²³⁰-⁹]+|\(\d+\)|\s\d+\)$", "", s)
    s = unicodedata.normalize("NFKD", s.replace("ł", "l"))
    s = "".join(c for c in s if not unicodedata.combining(c))
    return re.sub(r"\s+", " ", s).strip(" .,:;")


def col_index(ref: str, header: list[str]) -> int:
    ref = str(ref).strip()
    if re.fullmatch(r"[A-Z]{1,2}", ref):
        n = 0
        for ch in ref:
            n = n * 26 + ord(ch) - 64
        return n - 1
    hn = [norm(h) for h in header]
    if norm(ref) in hn:
        return hn.index(norm(ref))
    raise KeyError(f"column '{ref}' not found in header {header}")


def read_sheet(spec: pd.Series) -> pd.DataFrame:
    path = require(RAW / spec["file"])
    sheet = spec["sheet"] if pd.notna(spec.get("sheet")) else 0
    try:
        sheet = int(sheet)
    except (TypeError, ValueError):
        pass
    raw = pd.read_excel(path, sheet_name=sheet, header=None, dtype=object)
    hr = int(spec["header_row"]) - 1               # 1-based in table_map
    header = [str(h) for h in raw.iloc[hr].tolist()]
    body = raw.iloc[hr + 1:]
    ci = col_index(spec["citizenship_col"], header)
    refs = [r.strip() for r in str(spec["value_cols"]).split("|")]
    vis = [col_index(r, header) for r in refs]
    out = []
    for _, row in body.iterrows():
        lab = row.iloc[ci]
        if pd.isna(lab) or norm(lab) in TOTAL_LABELS or norm(lab) == "":
            continue
        for k, vi in enumerate(vis):
            v = row.iloc[vi]
            if isinstance(v, str):
                v = v.replace(" ", "").replace(" ", "").replace(",", ".")
                v = {"-": 0, "–": 0, "x": None, "": None}.get(v, v)
            rec = {"polish_name": str(lab).strip(), "value": pd.to_numeric(v, errors="coerce")}
            if spec["layout"] == "wide_months":
                rec["month"] = k + 1
            elif spec["layout"] == "wide_halves":
                rec["half"] = k + 1
            out.append(rec)
    df = pd.DataFrame(out)
    for c in ("year", "half", "month"):
        if c not in df and pd.notna(spec.get(c)):
            df[c] = int(spec[c])
    df["file"], df["series"], df["frequency"] = spec["file"], spec["series"], spec["frequency"]
    return df


def main() -> None:
    inv = read_csv(require(RAW / "source_inventory.csv"), dtype=str)
    tmap = read_csv(require(RAW / "table_map.csv",
                            "Describe the layout of each spreadsheet in table_map.csv."), dtype=str)
    use = set(inv.loc[inv["use"].astype(str) == "1", "file"])
    tmap = tmap[tmap["file"].isin(use)]
    log.info("reading %d sheet specifications from %d files", len(tmap), tmap.file.nunique())
    parts = [read_sheet(s) for _, s in tmap.iterrows()]
    long = pd.concat(parts, ignore_index=True)

    cw = read_csv(Path(CFG.CROSSWALKS) / "citizenship_crosswalk.csv", dtype=str)
    lookup = {}
    for _, r in cw.iterrows():
        for lab in [r["polish_name"]] + str(r.get("polish_aliases") or "").split("|"):
            if lab and lab != "nan":
                lookup[norm(lab)] = r["iso3"]
    long["iso3"] = long["polish_name"].map(lambda s: lookup.get(norm(s)))
    um = (long[long.iso3.isna()].groupby("polish_name").agg(files=("file", "nunique"),
                                                            total=("value", "sum")).reset_index())
    write_csv(um, Path(CFG.LOGS) / "unmatched_citizenships.csv")
    if len(um):
        log.error("%d citizenship labels are not in the crosswalk; add them to "
                  "polish_aliases (see output/logs/unmatched_citizenships.csv)", len(um))
        raise SystemExit(1)
    cols = ["file", "series", "frequency", "year", "half", "month", "polish_name", "iso3", "value"]
    for c in cols:
        if c not in long:
            long[c] = pd.NA
    write_csv(long[cols], Path(CFG.DERIVED) / "mrpips_long.csv")
    log.info("wrote %d rows", len(long))


if __name__ == "__main__":
    main()
