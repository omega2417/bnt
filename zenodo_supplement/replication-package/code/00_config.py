"""Global configuration for the replication package.

Every script reads this file through ``lib.common.CFG``. Edit the values here,
not in the individual scripts. Paths are resolved relative to the package root,
so the package can be moved without editing anything; set the environment
variable ``REPL_ROOT`` to run the code against a different copy of the data
(the smoke test in ``tests/`` does this).
"""
from pathlib import Path
import os

# --------------------------------------------------------------------------
# Paths
# --------------------------------------------------------------------------
ROOT = Path(os.environ.get("REPL_ROOT", Path(__file__).resolve().parents[1]))
DATA = ROOT / "data"
RAW = DATA / "raw"
DERIVED = DATA / "derived"
POLICY = DATA / "policy"
CROSSWALKS = DATA / "crosswalks"
OUTPUT = ROOT / "output"
TABLES = OUTPUT / "tables"
FIGURES = OUTPUT / "figures"
LOGS = OUTPUT / "logs"

# --------------------------------------------------------------------------
# Reproducibility
# --------------------------------------------------------------------------
SEED = 20261025            # single seed; each script derives sub-seeds from it
N_PAIRS_BOOT = 999         # pairs cluster bootstrap draws (reviewer: >= 999)
N_WILD_BOOT = 9999         # wild cluster score bootstrap draws
WILD_WEIGHTS = ("rademacher", "webb")   # both are reported (few treated clusters)
if os.environ.get("REPL_SMOKE"):         # tests/smoke_test.py only - never for results
    N_PAIRS_BOOT, N_WILD_BOOT = 49, 199

# --------------------------------------------------------------------------
# Sample definitions (Sections 4-5 of the article)
# --------------------------------------------------------------------------
YEARS = list(range(2008, 2026))          # panel years
EST_YEARS = list(range(2011, 2026))      # PPML estimation years (needs t-1..t-3)
PRESAMPLE_YEARS = [2008, 2009, 2010]     # pre-sample mean (Blundell et al. 2002)
WB_YEARS = list(range(2006, 2026))       # World Bank snapshot years

# Six origins that ever had access to employer declarations
DECL6 = ["ARM", "BLR", "GEO", "MDA", "RUS", "UKR"]
# Origins whose access changed inside the observation window (Section 5.3)
EVENT_CASES = {
    #  case       iso3   event year  label used in Table 5 / Figure 4
    "MDA_2009": ("MDA", 2009, "Moldova enters (2009)"),
    "GEO_2011": ("GEO", 2011, "Georgia enters (2011; legal access Dec 2010)"),
    "ARM_2014": ("ARM", 2014, "Armenia enters (2014)"),
    "RUS_2022": ("RUS", 2022, "Russia excluded (2022)"),
}
# Alternative calendar year 0 for Georgia (reviewer comment: 2010 vs 2011)
EVENT_ALTERNATIVES = {"GEO_2010": ("GEO", 2010, "Georgia enters (event year 0 = 2010)")}
COMPARISON_MIN_DOCS = 500   # never-eligible origins with >= 500 documents 2008-2025
EVENT_WINDOW = (-4, 5)      # event-study window; endpoints are binned
DID_PRE, DID_POST = 3, 4    # up to 3 pre-event years vs 4 event/post-event years

# --------------------------------------------------------------------------
# Interrupted time series (Section 5.4)
# --------------------------------------------------------------------------
ITS_NW_LAGS_MONTHLY = 6
ITS_NW_LAGS_HALFYEAR = 2
ITS_MAIN_WINDOW = ("2021-01", "2025-11")     # December 2025 excluded
ITS_SEASONAL_START = "2019-01"
ITS_NOTIF_START = "2022-04"
ITS_BREAK_2022 = "2022-03"
ITS_PULSE = "2022-02"
ITS_BREAK_2025 = "2025-06"
ITS_2018_WINDOW = ("2015-01", "2019-12")
ITS_2018_HALFYEAR_WINDOW = (2015, 2021)
# Optional extension to H1 2026 (A9) - only used if the monthly file has the data
ITS_EXTENDED_END = "2026-06"

# Segmented HHI trends (Table 2)
HHI_BREAKS = [2018, 2022]
HHI_NW_LAGS_YEAR = 1
HHI_NW_LAGS_HALFYEAR = 2

# --------------------------------------------------------------------------
# Figures
# --------------------------------------------------------------------------
FIG_DPI = 300
REFORM_LINES_ANNUAL = [2018, 2022, 2025.42]   # June 2025 ~ 2025 + 5/12
