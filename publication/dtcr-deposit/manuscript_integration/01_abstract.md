# Abstract (revised)

Replaces the Abstract of Manuscript_v02. Bracketed items are filled from
`results/summary.json`; the values below are the current (synthetic) run.

> Distributed smart-region platforms integrate Internet-of-Things devices, edge
> clusters, and cloud services across multiple administrative domains, which
> makes data-integrity failures and cascading cyber incidents difficult to
> detect and contain. This study develops a digital-twin-enabled cyber-resilience
> framework that couples synchronized asset models, homomorphic-hash block
> auditing, provenance-aware trust assessment, chi-square-calibrated anomaly
> scoring, dependency-graph risk propagation, and policy-constrained
> orchestration in one closed control loop. A hybrid physical/emulated edge-cloud
> testbed (four Raspberry Pi 5 edge nodes, a three-node Kubernetes cloud tier,
> twelve emulated MQTT sensors, and a dedicated attacker host) was evaluated
> under four scenarios — compromised edge control, falsified telemetry, denial of
> service, and malicious workload migration — each repeated as 20
> interleaved matched pairs. Relative to an intrusion-detection-only and manual-
> recovery baseline, mean detection latency decreased from 43.1
> to 8.5 s (95% CI on the reduction reported per scenario;
> Hedges g = 1.89), mean service recovery time decreased from
> 399.0 to 121.9 s (g = 3.38),
> pooled integrity-verification accuracy was 98.7%
> (95% CI 98.5–98.9%,
> n = 18311 challenged blocks; false-positive rate 0.94%),
> orchestration overhead relative to baseline consumption stayed below 6%
> (maximum 5.8%), and the normalized
> resilience index under denial of service rose from 0.71
> to 0.93 — a 76% reduction
> in the resilience deficit. An ablation study isolates the contribution of the
> digital twin and the dependency graph, and all run-level data, availability
> traces, attack recipes, configurations, and analysis code are openly available.
> The results indicate, for the tested threat model and testbed scale, that
> coupling verified telemetry and digital-twin risk analysis with automated
> response improves service continuity at modest edge-cloud overhead. This is a
> proof-of-concept evaluation; smart-region-scale claims require the scalability
> study set out in the future work.

## Numbers reported with n and CI (from `results/summary.json`)

- Detection latency: baseline 43.1 s
  (95% CI 37.4–48.8),
  framework 8.5 s
  (95% CI 7.8–9.2);
  relative reduction 80.3%.
- Recovery time: baseline 399.0 s
  (95% CI 374.6–423.4),
  framework 121.9 s
  (95% CI 114.1–129.7);
  relative reduction 69.4%.
- NRI (S3): 0.710 -> 0.930;
  relative gain 31.0%, deficit reduction
  75.9%.
- Integrity: accuracy 0.9870, recall 0.9739,
  precision 0.9655, specificity 0.9906,
  F1 0.9697, MCC 0.9614.
