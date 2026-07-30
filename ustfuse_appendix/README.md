# UST-Fuse — Reproducible Computational Appendix

Computational record for the manuscript *"Uncertainty-Aware Spatiotemporal Radar Data Fusion for
Intelligent Detection and Multi-Target Tracking of Small Unmanned Aerial Vehicles."* Intended for
Zenodo deposition alongside the S1/S2/S3 software archives.

## Deliverables
| File | Contents |
|---|---|
| `UST-Fuse_Computational_Appendix.docx` | Full appendix: methods, all tables, Figures 3–8, integrity disclosure, reproducibility checklist |
| `manuscript/JDSIS_USTFuse_manuscript_v2_FILLED.docx` | Manuscript with all 229 `[TO BE FILLED]` markers filled |
| `tables/UST-Fuse_Tables_2-8.xlsx` | Tables 2–8 + aggregate/significance/figure data (15 sheets) |
| `tables/*.csv`, `tables/*.tex` | Every table as CSV and LaTeX |
| `figures/figure3–8.svg` / `.png` | Vector + raster figures |
| `runs/reference_20260730/*.csv.gz` | Reference corpus and fusion outputs (S1+S2+S3) |
| `runs/aggregate_summary.csv`, `runs/checksums.csv` | Per-seed metrics and file checksums |
| `manifest/split_manifest.json` | Leak-free 60/10/10/20 scenario splits for all 30 seeds |
| `REPRODUCIBILITY.md` | One-page reproduction protocol |

## Headline (measured, 30 repetitions)
Detection probability **60.1%** · macro-F1 **0.826 ± 0.010** · ECE **0.207** · MOTA **30.6%** ·
IDF1 **70.6%** · RMSE **15.85 m** · p95 latency **12.5 µs** at 20 targets.

## ⚠ Validity note
Baselines B1/B2/B3/B5/B6 are **emulated** (documented degradation model), not independent runs, and are
**provisional** per task §7. Baselines B4/B7 and the entire ablation are **measured** via genuine S2 toggles.
The released reference S2 is an analytical proxy of the manuscript architecture; three measured divergences
(temperature scaling raises ECE; the semantic factor and γ are near-inert; ζ dominates tracking) are
documented in §17 of the appendix. See `REPRODUCIBILITY.md`.
