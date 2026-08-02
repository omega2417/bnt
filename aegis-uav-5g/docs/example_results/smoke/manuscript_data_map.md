**Mapping of manuscript [DATA REQUIRED] items to computed values.**

| manuscript_item | value | evidence |
| --- | --- | --- |
| Feature vector dimension d | 60 | artifacts/tables/smoke/table_2_parameters.csv |
| Final feature list | 56 numeric + 4 one-hot phase | src/aegis_uav/features/windowing.py |
| Fleet size N | 6 | artifacts/tables/smoke/table_2_parameters.csv |
| Window length Delta (s) | 2.0 | artifacts/tables/smoke/table_2_parameters.csv |
| EWMA kappa | 3.0 | artifacts/tables/smoke/table_2_parameters.csv |
| EWMA alpha | 0.05 | artifacts/tables/smoke/table_2_parameters.csv |
| Severity floor tau_e | 0.28 | artifacts/tables/smoke/table_2_parameters.csv |
| Modality weights w_m | {"telemetry": 0.34, "network": 0.33, "behaviour": 0.33} | artifacts/tables/smoke/table_2_parameters.csv |
| Confidence floor pi_min | 0.55 | artifacts/tables/smoke/table_2_parameters.csv |
| Utility lambda1 | 0.5 | artifacts/tables/smoke/table_2_parameters.csv |
| Utility lambda2 | 0.7 | artifacts/tables/smoke/table_2_parameters.csv |
| Autoencoder architecture | input -> [32] -> latent 8 -> mirror -> output | configs/models/ada.yaml |
| Attribution classifier | hist_gradient_boosting (calibration: isotonic) | configs/models/aaa_hierarchical.yaml |
| Number of runs / seeds | 3 seeds = [0, 1, 2] | artifacts/tables/smoke/table_2_parameters.csv |
| Train/validation/test split | 60/20/20 | artifacts/tables/smoke/table_2_parameters.csv |
| Attack parameters (T1-T6) | onset/duration/intensity/targets/profile per class | configs/attacks/T1.yaml ... T6.yaml |
| Sample (window) counts - train | {'benign': '13998', 'T1': '135', 'T2': '123', 'T3': '69', 'T4': '135', 'T5': '120', 'T6': '414'} | artifacts/tables/smoke/table_2_parameters.csv |
| Sample (window) counts - val | {'benign': '13998', 'T1': '135', 'T2': '123', 'T3': '69', 'T4': '135', 'T5': '120', 'T6': '414'} | artifacts/tables/smoke/table_2_parameters.csv |
| Sample (window) counts - test | {'benign': '13998', 'T1': '135', 'T2': '123', 'T3': '69', 'T4': '135', 'T5': '120', 'T6': '414'} | artifacts/tables/smoke/table_2_parameters.csv |
| Detection F1 - fused_framework | 0.816 [0.799, 0.832] | artifacts/tables/smoke/table_3_detection.csv |
| Detection F1 - telemetry_only | 0.195 [0.187, 0.212] | artifacts/tables/smoke/table_3_detection.csv |
| Detection F1 - traffic_only | 0.444 [0.442, 0.448] | artifacts/tables/smoke/table_3_detection.csv |
| Detection F1 - behaviour_only | 0.770 [0.764, 0.775] | artifacts/tables/smoke/table_3_detection.csv |
| Detection F1 - rf_flow_baseline | 0.459 [0.457, 0.459] | artifacts/tables/smoke/table_3_detection.csv |
| Fig. 4 confusion matrix | leaf-level attribution | artifacts/figures/smoke/fig_4_confusion_matrix.pdf |
| Attribution macro-F1 - hierarchical | 0.792 [0.654, 0.889] | artifacts/metrics/smoke/attribution_per_seed.csv |
| Attribution leaf accuracy - hierarchical | 0.979 [0.957, 0.991] | artifacts/metrics/smoke/attribution_per_seed.csv |
| Attribution macro-F1 - flat | 0.899 [0.844, 0.981] | artifacts/metrics/smoke/attribution_per_seed.csv |
| Attribution leaf accuracy - flat | 0.993 [0.990, 0.998] | artifacts/metrics/smoke/attribution_per_seed.csv |
| Calibration (ECE / Brier) | ECE=0.029 [0.018, 0.047], Brier=0.033 [0.016, 0.063] | artifacts/metrics/smoke/attribution_per_seed.csv |
| Contained-before-impact - utility_rsa | 0.583 [0.500, 0.625] | artifacts/tables/smoke/table_5_containment.csv |
| Contained-before-impact - static_policy | 0.792 [0.750, 0.875] | artifacts/tables/smoke/table_5_containment.csv |
| Table 4 ablation | component removal deltas | artifacts/tables/smoke/table_4_ablation.csv |
| Processing latency (ms/window) | 0.014 [0.012, 0.015] | artifacts/tables/smoke/table_6_overhead.csv |
| RAM (MB) | 320.434 [280.988, 360.176] | artifacts/tables/smoke/table_6_overhead.csv |
| Probe bandwidth (kbps/UAV) | 1.920 [1.920, 1.920] | artifacts/tables/smoke/table_6_overhead.csv |
| Scalability plot (N=5..80) | per-window latency / RAM / bandwidth | artifacts/figures/smoke/scalability.pdf |
| Sensitivity plots | kappa, alpha, Delta, w_m, tau_e, lambda1, lambda2, pi_min | artifacts/figures/smoke/sensitivity.pdf |
| Statistical tests (Wilcoxon + Holm, effect sizes) | paired comparisons across seeds | artifacts/tables/smoke/statistical_test_report.csv |
| Error analysis | per-class recall + most-confused class | artifacts/tables/smoke/error_analysis.csv |
| Fig. 5 detection/containment latency | per attack class with 95% CI | artifacts/figures/smoke/fig_5_latency.pdf |
| Data availability | aegis campaign --config configs/experiments/smoke.yaml; manifests in artifacts/manifests/ | README.md |
