"""One-off helper that generated the first version of
data/crosswalks/citizenship_crosswalk.csv (not part of run_all).

Sources: ISO 3166-1 codes and their Polish translations (pycountry / iso-codes),
UN M49 sub-regions (country_converter). After generation the file is curated by
hand: ``polish_aliases`` must contain every citizenship label that appears in the
MRPiPS tables (01_import_mrpips.py stops and lists unmatched labels), and the
regional coding of Figure 2 is overwritten from the REST Countries snapshot
(09_figures.py) when that snapshot is present.

    pip install pycountry country_converter
    python code/make_crosswalk_template.py
"""
from __future__ import annotations

import gettext
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from lib.common import CFG, write_csv  # noqa: E402

import country_converter as coco  # noqa: E402
import pandas as pd  # noqa: E402
import pycountry  # noqa: E402

FORMER_USSR = {"ARM", "AZE", "BLR", "EST", "GEO", "KAZ", "KGZ", "LTU", "LVA", "MDA", "RUS",
               "TJK", "TKM", "UKR", "UZB"}
CENTRAL_ASIA = {"KAZ", "KGZ", "TJK", "TKM", "UZB"}
# Slavic official language (non-EU states only matter for the panel)
SLAVIC = {"BLR", "RUS", "UKR", "SRB", "MNE", "BIH", "MKD", "BGR", "HRV", "SVN", "CZE", "SVK", "POL"}
CONTIGUOUS_PL = {"BLR", "RUS", "UKR", "LTU", "DEU", "CZE", "SVK"}
EU_EFTA = {"AUT", "BEL", "BGR", "HRV", "CYP", "CZE", "DNK", "EST", "FIN", "FRA", "DEU", "GRC",
           "HUN", "IRL", "ITA", "LVA", "LTU", "LUX", "MLT", "NLD", "POL", "PRT", "ROU", "SVK",
           "SVN", "ESP", "SWE", "ISL", "LIE", "NOR", "CHE"}
# Label variants known to occur in Polish statistics; extend from unmatched_citizenships.csv
ALIASES = {
    "RUS": "Rosja|Federacja Rosyjska", "MDA": "Mołdawia|Republika Mołdawii|Mołdowa",
    "KOR": "Korea Południowa|Republika Korei", "PRK": "Korea Północna",
    "USA": "Stany Zjednoczone|Stany Zjednoczone Ameryki|USA",
    "GBR": "Wielka Brytania|Zjednoczone Królestwo", "VNM": "Wietnam",
    "IRN": "Iran", "SYR": "Syria", "LAO": "Laos", "BOL": "Boliwia", "VEN": "Wenezuela",
    "TZA": "Tanzania", "COD": "Demokratyczna Republika Konga|Kongo (DRK)",
    "COG": "Kongo|Republika Konga", "CIV": "Wybrzeże Kości Słoniowej", "MKD": "Macedonia Północna|Macedonia",
    "CZE": "Czechy", "TWN": "Tajwan", "PSE": "Palestyna", "KGZ": "Kirgistan|Kirgizja",
    "TUR": "Turcja|Türkiye", "CPV": "Republika Zielonego Przylądka", "SWZ": "Eswatini|Suazi",
}


def main():
    pl = gettext.translation("iso3166-1", pycountry.LOCALES_DIR, languages=["pl"])
    cc = coco.CountryConverter().data.set_index("ISO3")
    rows = []
    for c in pycountry.countries:
        iso = c.alpha_3
        en = getattr(c, "common_name", c.name)
        rows.append({
            "iso3": iso, "name_en": en,
            "polish_name": pl.gettext(getattr(c, "common_name", c.name)),
            "polish_aliases": "|".join(x for x in [pl.gettext(c.name), ALIASES.get(iso, "")]
                                       if x and x != pl.gettext(getattr(c, "common_name", c.name))),
            "un_region": cc["continent"].get(iso, ""), "un_subregion": cc["UNregion"].get(iso, ""),
            "central_asia": int(iso in CENTRAL_ASIA), "declaration_group": int(iso in CFG.DECL6),
            "former_ussr": int(iso in FORMER_USSR), "slavic_language": int(iso in SLAVIC),
            "contiguity": int(iso in CONTIGUOUS_PL), "eu_efta": int(iso in EU_EFTA),
            "special": "",
        })
    extra = [("XKX", "Kosovo", "Kosowo", "Europe", "Southern Europe", "Kosovo (not ISO 3166-1)"),
             ("XXS", "Stateless", "Bezpaństwowiec", "", "", "stateless; MRPiPS label to be checked"),
             ("XXU", "Unknown citizenship", "Nieustalone", "", "",
              "unknown citizenship; MRPiPS label to be checked")]
    for iso, en, plname, reg, sub, note in extra:
        rows.append({"iso3": iso, "name_en": en, "polish_name": plname, "polish_aliases": "",
                     "un_region": reg, "un_subregion": sub, "central_asia": 0,
                     "declaration_group": 0, "former_ussr": 0, "slavic_language": 0,
                     "contiguity": 0, "eu_efta": 0, "special": note})
    df = pd.DataFrame(rows).sort_values("iso3")
    df["un_region"] = df["un_region"].replace({"America": "Americas"})
    write_csv(df, Path(CFG.CROSSWALKS) / "citizenship_crosswalk.csv")
    print(len(df), "rows")


if __name__ == "__main__":
    main()
