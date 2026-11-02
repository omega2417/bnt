World Bank WDI snapshot (accessed 2026-10-25), CC BY 4.0.
Expected file: `wdi_snapshot.csv` (iso3, year, indicator, value; long format) for
NY.GDP.PCAP.KD.ZG, NY.GDP.PCAP.PP.CD, NY.GDP.PCAP.CD, SL.UEM.TOTL.ZS and SP.POP.TOTL, 2006–2025,
plus the raw API responses (`<indicator>.json`).
`python code/download_sources.py --only worldbank` creates a new snapshot. For the article, use
the 2026-10-25 snapshot: WDI series are revised.
