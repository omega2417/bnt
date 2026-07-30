# UST-Fuse Reproducible Software Suite (S1 · S2 · S3)

Reference C++17 software accompanying the manuscript on **Uncertainty-Aware
Spatiotemporal Radar Fusion (UST-Fuse)** for the detection, classification and
multi-target tracking of small unmanned aerial vehicles (UAVs).

The methodology requires a synthetic corpus of radar scenarios, uncertainty
estimation, multi-target tracking, comparison against baseline methods, and the
production of result tables and figures. Accordingly, the suite is organised as
**three interconnected software projects**, each publishable independently on
Zenodo:

| ID | Project | Ukrainian name | Role |
|----|---------|----------------|------|
| **S1** | [**RadarTwin-UAV**](RadarTwin-UAV/) | Генератор синтетичних радарних даних і цифрових двійників | Synthetic radar scenario & digital-twin generator |
| **S2** | [**UST-Fuse Engine**](UST-Fuse-Engine/) | Система невизначенісно-орієнтованого просторово-часового злиття | The UST-Fuse fusion / classification / tracking algorithm |
| **S3** | [**FuseMetrics Lab**](FuseMetrics-Lab/) | Платформа експериментальної аналітики та відтворення результатів | Experimental analytics, statistics & result tables |

```
RadarTwin-UAV (S1)  ──►  UST-Fuse Engine (S2)  ──►  FuseMetrics Lab (S3)
   measurements.csv          tracks.csv               summary / comparison /
   truth.csv                 classifications.csv       ablation / significance
   scenarios.json                                      LaTeX table + SVG figure
```

Every project:

* depends only on the **C++ standard library** (no third-party libraries);
* compiles with `g++ -std=c++17` and **runs on [OnlineGDB](https://www.onlinegdb.com/)**;
* is **deterministic** given a random seed;
* **runs standalone** (each of S2 and S3 generates internal demo data if the
  upstream files are absent) *and* interlocks into the full pipeline.

## Quick start (full pipeline)

```bash
# 1. Generate a synthetic corpus
cd RadarTwin-UAV   && make && ./radartwin 20260730 16 && cd ..

# 2. Run the UST-Fuse engine on that corpus
cd UST-Fuse-Engine && make && cp ../RadarTwin-UAV/radartwin_measurements.csv . \
                    && ./ustfuse radartwin_measurements.csv && cd ..

# 3. Score everything and build the tables/figures
cd FuseMetrics-Lab && make \
   && cp ../RadarTwin-UAV/radartwin_truth.csv . \
   && cp ../UST-Fuse-Engine/ustfuse_*.csv . \
   && ./fusemetrics && cd ..
```

On OnlineGDB, run each project by pasting its `src/main.cpp`, then pass the
generated CSV files between projects using the file panel (see each project's
README).

## Running on OnlineGDB

Each project is a single self-contained `src/main.cpp`. Open OnlineGDB, choose
**C++ (g++ 17)**, paste the file, and press **Run**. Because S2 and S3 fall back
to internally-generated demo data, any project can be demonstrated on its own
without uploading files first.

## Note for the manuscript text

For the article, label the projects **S1 = RadarTwin-UAV**, **S2 = UST-Fuse
Engine**, **S3 = FuseMetrics Lab**. The suite comprises **three software
projects**; any statement in the manuscript referring to *"two software
projects"* (Section 3.10, the *Data Availability Statement*, and the reference
list) should be updated to **"three software projects"** accordingly.

## License

All three projects are released under the MIT License (see each project's
`LICENSE`). If you use this software, please cite it via the project
`CITATION.cff` files and the accompanying UST-Fuse manuscript.

> **Before publishing on Zenodo:** replace the `PLACEHOLDER` author metadata in
> each project's `.zenodo.json` and `CITATION.cff` with the real author name,
> affiliation and ORCID.
