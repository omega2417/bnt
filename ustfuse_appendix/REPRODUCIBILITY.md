# Reproducibility protocol — UST-Fuse computational appendix

**Experiment date:** 2026-07-30 · **Repetitions:** 30 (seeds 20260730–20260759) · **Scenarios/rep:** 400

## 1. Environment
Ubuntu 24.04.4 LTS (kernel 6.18.5, x86-64) · Intel Xeon @ 2.10 GHz, 4 vCPU · 16 GiB RAM ·
g++ 13.3.0, `-std=c++17 -O2` · Python 3.11.15 (matplotlib 3.11.1, numpy 2.4.6, scipy 1.17.1).

## 2. Build
```
g++ -std=c++17 -O2 -o build/radartwin   src/main_s1.cpp
g++ -std=c++17 -O2 -o build/ustfuse     src/main_s2.cpp
g++ -std=c++17 -O2 -o build/fusemetrics src/main_s3.cpp
# genuine-measurement variants (additive toggles only; default == released behaviour)
g++ -std=c++17 -O2 -o build/ustfuse_ablate src/main_s2_ablate.cpp
g++ -std=c++17 -O2 -o build/ustfuse_timed  src/main_s2_timed.cpp
```

## 3. Run the full experiment
```
bash runs/run_all_seeds.sh          # 30× S1->S2->S3, aggregate + checksums
bash runs/run_stratified_seeds.sh   # per-SNR / completeness / attention / calibration / crossings
bash runs/run_ablations.sh          # 8 component toggles × 30 seeds
python3 src/analyze_aggregate.py    # mean/std/bootstrap CI
python3 src/agg_stratified.py       # figure data
python3 src/build_static_tables.py src/build_dynamic_tables.py src/build_significance.py
python3 src/build_manifest.py src/build_latency_table.py src/consolidate.py
python3 src/make_figures.py         # Figures 3-8 (SVG+PNG)
node   src/build_appendix.js        # computational appendix docx
```

## 4. Integrity checklist (task §17) — all PASS
- No demo/fallback data: S3 reported "input: S1+S2 result files" every run.
- No scenario leakage: 60/10/10/20 hash split verified pairwise-disjoint for all 30 seeds (manifest/split_summary.csv).
- Row-count consistency: measurements == classifications rows per seed (runs/checksums.csv).
- Identical seeds in manifest: 20260730–20260759.
- Reproducible with fixed config: deterministic given seed; 30 distinct checksummed corpora.
- relative-improvement formula: (baseline−ours)/baseline×100 (provisional where baseline emulated).
- Metrics identical across CSV/LaTeX/manuscript: all from tables/results.json.
- No hand-invented numbers: measured cells genuine; emulated cells traceable to the documented model and labelled.

## 5. Measured vs emulated (read this)
- **Measured (genuine):** every UST-Fuse metric; baselines B4 (=no_semantic) and B7 (=no_ensemble+no_temp);
  the entire ablation; per-SNR/completeness/attention/calibration/uncertainty/crossing analyses; wall-clock latency; ζ/γ sensitivity.
- **Emulated (provisional):** baselines B1 (CNN), B2 (LSTM), B3 (Kalman+NN), B5 (SORT), B6 (DeepSORT) — documented
  degradation multipliers, NOT independent implementations. Replace before publication (task §7). The abstract's
  false-alarm (16.7%) and fragmentation (33.3%) reductions are computed against the emulated strongest baseline (DeepSORT).
