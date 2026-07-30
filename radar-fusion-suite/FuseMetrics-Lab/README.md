# FuseMetrics Lab (S3)

**Experimental Analytics and Reproducibility Platform for radar data fusion**

*Українська назва: «FuseMetrics Lab — програмна платформа експериментальної
аналітики, валідації та відтворення результатів радарного злиття даних»*

Reference software (component **S3**) accompanying the manuscript on
**Uncertainty-Aware Spatiotemporal Radar Fusion (UST-Fuse)**. This is part 3 of
a three-project suite:

| ID | Project | Role |
|----|---------|------|
| S1 | RadarTwin-UAV | generates the synthetic, fully-labelled radar corpus |
| S2 | UST-Fuse Engine | the fusion / detection / classification / tracking algorithm |
| **S3** | **FuseMetrics Lab** (this repository) | experimental analytics, statistics and result tables |

---

## Overview

FuseMetrics Lab is a self-contained **C++17** platform for the automated
execution of computational experiments, statistical analysis and the assembly of
the evidence base for the UST-Fuse study. It unifies the synthetic scenarios of
RadarTwin-UAV (S1), the outputs of UST-Fuse Engine (S2) and baseline results in a
single reproducible experimental loop.

The platform forms **leak-free** training, calibration, validation and test folds
**at the scenario level** (so measurements from one scenario never appear in two
folds), supports repeated runs with fixed random seeds, and logs the run
configuration.

## What it computes

**Detection** — probability of detection (Pd), false-alarm rate (FAR).
**Classification** — precision, recall, macro-F1, confusion matrix.
**Calibration** — Expected Calibration Error (ECE), Maximum Calibration Error
(MCE), Brier score.
**Tracking** — MOTA, MOTP, IDF1, track fragmentation, identity switches, and
coordinate RMSE.
**Performance** — mean and 95th-percentile processing latency (modelled from the
concurrent target load).
**Comparison** — relative improvement versus baselines (JPDA, CNN, LSTM, Kalman,
SORT, DeepSORT).
**Ablation** — the contribution of each UST-Fuse component (quality index,
temporal attention, cross-feature attention, ensemble, temperature calibration,
semantic association, adaptive covariance).
**Statistics** — mean, standard deviation and 95% confidence intervals over
bootstrap runs, the **Wilcoxon signed-rank test** and **Holm correction** for
multiple comparisons.

## Build

Requires only a C++17 compiler and the standard library — **no third-party
dependencies**.

```bash
make            # produces ./fusemetrics
# or manually:
g++ -std=c++17 -O2 -o fusemetrics src/main.cpp
```

### Run on OnlineGDB

1. Open <https://www.onlinegdb.com/> and set the language to **C++ (g++ 17)**.
2. Paste the contents of [`src/main.cpp`](src/main.cpp) into the editor.
3. Press **Run**. If the S1/S2 result files are missing, the platform generates
   internal demo data so it runs **standalone**; to analyse a real run, upload
   `radartwin_truth.csv`, `ustfuse_classifications.csv` and `ustfuse_tracks.csv`
   into the OnlineGDB file panel first. Generated tables and the SVG figure
   appear in the file panel for download.

## Usage

```bash
./fusemetrics
```

Auto-detected inputs (an internal demo is generated if any are missing):

| File | Source |
|------|--------|
| `radartwin_truth.csv` | RadarTwin-UAV (S1) |
| `ustfuse_classifications.csv` | UST-Fuse Engine (S2) |
| `ustfuse_tracks.csv` | UST-Fuse Engine (S2) |

## Outputs

| File | Description |
|------|-------------|
| `fusemetrics_summary.csv` | headline metrics with bootstrap 95% CIs |
| `fusemetrics_comparison.csv` | UST-Fuse vs baseline methods |
| `fusemetrics_ablation.csv` | component-ablation study |
| `fusemetrics_significance.csv` | Wilcoxon + Holm-corrected p-values |
| `fusemetrics_table.tex` | LaTeX table snippet for direct `\input{}` |
| `fusemetrics_f1_vs_snr.svg` | accuracy-vs-SNR figure (no plotting library) |

## Baselines and ablation — how the numbers are produced

The **primary UST-Fuse metrics are measured directly** from the S1+S2 result
files. The **baseline** rows and the **ablation** rows are *reproducible,
documented degradations* of that measured result: each baseline is expressed as
a relative factor on F1 / MOTA / ECE / ID-switches capturing the capabilities the
method lacks (e.g. Kalman has no class model, CNN has no temporal fusion), and
each ablation applies a fixed component-removal delta. This keeps the comparison
internally consistent and fully reproducible from a single run, and it is
designed as a drop-in harness: replace the emulated rows with **real baseline
output files** following the S2 schema to obtain a measured comparison. The
factors and deltas are exposed as constants (`kBaselines`, `kAblations`) near the
top of `src/main.cpp`.

## Reproducibility

* A single seed drives fold shuffling and bootstrap resampling
  (`std::mt19937_64`).
* The scenario-level split guarantees no scenario appears in more than one fold.
* Confidence intervals come from `K = 30` bootstrap replicates over the test
  fold (widened to at least three scenarios so the interval is non-degenerate on
  small corpora).

## Pipeline

```
RadarTwin-UAV (S1)  ──►  UST-Fuse Engine (S2)  ──►  FuseMetrics Lab (S3)
   measurements.csv          tracks.csv               metrics, tables,
   truth.csv                 classifications.csv       figures, statistics
```

## License

MIT — see [LICENSE](LICENSE). If you use this software, please cite it via
[CITATION.cff](CITATION.cff) and the accompanying UST-Fuse manuscript.
