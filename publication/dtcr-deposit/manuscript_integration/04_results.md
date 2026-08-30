# Results — rebuilt from primary data

Replaces §3.1–3.6 and Table 4. Every number is produced by `analysis/statistics.py` and `analysis/calculate_nri.py` from `data/`, and the figures by `analysis/generate_figures.py`. Values below are the current (synthetic) run and update automatically when `data/` is replaced.

## 3.1 Detection latency and recovery time (Figure 5)

Scenario-level detection latency (mean ± SD, s), baseline vs framework, with the paired mean-difference 95% bootstrap CI and effect sizes:

| Scenario | Baseline mean±SD | Framework mean±SD | Reduction % | Diff 95% CI | Hedges g | Cliff δ | p (Holm) |
|---|---|---|---|---|---|---|---|
| S1 | 52.0±18.9 | 9.2±2.5 | 82.3 | [-51.7, -34.9] | 3.12 | 1.00 | 0.0000 |
| S2 | 68.4±27.2 | 7.4±1.5 | 89.2 | [-73.0, -50.1] | 3.11 | 1.00 | 0.0000 |
| S3 | 18.7±8.4 | 5.8±1.2 | 69.0 | [-16.8, -9.3] | 2.11 | 0.99 | 0.0000 |
| S4 | 33.3±8.7 | 11.6±2.8 | 65.2 | [-25.3, -18.1] | 3.29 | 1.00 | 0.0000 |
| pooled | 43.1±25.6 | 8.5±3.0 | 80.3 | [-40.3, -29.2] | 1.89 | 0.96 | 0.0000 |

Recovery time (mean ± SD, s):

| Scenario | Baseline mean±SD | Framework mean±SD | Reduction % | Diff 95% CI | Hedges g | Cliff δ | p (Holm) |
|---|---|---|---|---|---|---|---|
| S1 | 402.0±100.5 | 118.0±16.7 | 70.6 | [-326.6, -242.2] | 3.86 | 1.00 | 0.0000 |
| S2 | 356.0±84.5 | 96.0±26.1 | 73.0 | [-298.2, -227.3] | 4.08 | 1.00 | 0.0000 |
| S3 | 510.9±87.0 | 163.8±29.4 | 67.9 | [-388.1, -309.8] | 5.24 | 1.00 | 0.0000 |
| S4 | 327.0±68.6 | 109.9±23.1 | 66.4 | [-248.4, -191.1] | 4.16 | 1.00 | 0.0000 |
| pooled | 399.0±109.8 | 121.9±35.0 | 69.4 | [-298.5, -256.7] | 3.38 | 1.00 | 0.0000 |

Report individual points, box/violin plots and mean±95% CI as in `figures/figure5_detection_recovery.*`; do not collapse the scenarios into a single aggregate. Latency distributions are right-skewed, so the bootstrap CI is the interval quoted in the text.

## 3.3 Resilience under DoS (Figure 6)

NRI per scenario (mean ± SD), with relative gain and deficit reduction:

| Scenario | Baseline | Framework | Abs. gain | Rel. gain % | Deficit reduction % | Hedges g |
|---|---|---|---|---|---|---|
| S1 | 0.840±0.038 | 0.980±0.003 | 0.140 | 16.7 | 87.6 | -5.06 |
| S2 | 0.911±0.021 | 0.989±0.003 | 0.078 | 8.6 | 87.9 | -5.22 |
| S3 | 0.710±0.046 | 0.930±0.012 | 0.220 | 31.0 | 75.9 | -6.41 |
| S4 | 0.895±0.021 | 0.985±0.003 | 0.090 | 10.1 | 85.4 | -5.80 |

Figure 6 shows the mean availability trajectory with a 95% confidence band and the per-run NRI distribution. Both panels are computed by `calculate_nri.py` from the same `data/availability_traces/`, so Figure 5 and Figure 6 are guaranteed consistent; `make verify` fails otherwise. The NRI window is [t_dis, t_dis + 2·RTO] with RTO = 300 s; t_dis (disruption) and t_det (detection) are distinct.

## 3.2 Integrity verification and overhead

Pooled integrity verification over 18311 challenged telemetry blocks: accuracy 0.9870 (95% CI 0.9853–0.9885), recall 0.9739, precision 0.9655, specificity 0.9906, F1 0.9697, MCC 0.9614, FPR 0.0094. Report per-scenario and per-corruption-level confusion matrices from `results/table_S4_integrity.csv` and Figure 9; the observation unit is one challenged telemetry block. The single aggregate 98.7% is replaced by this breakdown with denominators and Wilson intervals.

Overhead (Eq. 17, relative to baseline consumption), with the cluster-capacity denominator reported separately:

| Metric | Baseline | Framework | Abs. diff | Overhead % (Eq.17) | Share of capacity % |
|---|---|---|---|---|---|
| cpu_pct | 38.5 | 40.6 | 2.08 | 5.40 | 0.297 |
| ram_mb | 2410.0 | 2508.8 | 98.81 | 4.10 | 0.123 |
| network_kbps | 1875.0 | 1935.0 | 60.00 | 3.20 | 0.006 |
| storage_mb_per_h | 96.0 | 101.6 | 5.57 | 5.80 | 0.136 |

Maximum relative overhead 5.80% (< 6% bound). §2.8 uses Eq. (17); §3.2 previously mixed in a share-of-capacity denominator — both are now given explicitly and the text states which it quotes.

## 3.6 Ablation study (Figure 11, new)

See `results/table_S6_ablation.csv`. The B0→B1 step isolates automation from detection; B2→A-variants isolate the digital twin, the dependency graph and what-if simulation. Removing the graph (A1) collapses risk-ranking accuracy; removing what-if (A2) raises the unsafe-action and rollback rates; the full framework minimises unsafe actions and policy violations while maximising recovery success.

