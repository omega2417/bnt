# Methodology

This document maps each modelling and evaluation choice to the requirements of
the UST-Fuse scientific-technical proposal.

## 1. Sensor & detection model (ЛР-2)

Each sensor samples the ground truth at its scan rate and applies:

- **Range-dependent detection probability** via an SNR falloff
  (`~40·log10(R)` for the active radar, `~22·log10(R)` for passive sensors),
  logistically mapped to Pd and anchored to `pd_ref` at `ref_range`.
- **Gaussian measurement noise** in (range, azimuth, elevation).
- **Poisson clutter / false alarms** at `false_alarm_rate` per scan.
- **Weather / domain scaling** of Pd, noise and clutter (ЛР-6).

Bearing-only sensors (EO-IR, RF-SDR, acoustic) place their pseudo-measurement at
a nominal range with a covariance so elongated along the line of sight that they
constrain **only** cross-range — their true physical value.

## 2. Time synchronisation (ЛР-1)

Every sensor has a clock model: constant offset + linear drift (ppm) + per-stamp
jitter. `clock.estimate_clock` recovers offset and drift by least squares
(`t_stamp − t_true` vs `t_true`), emulating an RTK-GNSS/PPS calibration session.
The Full UST-Fuse pipeline applies the correction and bins on the common
timeline; the Reference pipeline does not — the ЛР-1/ЛР-3 comparison quantifies
the cost of that omission.

## 3. Fusion & tracking (ЛР-3, ЛР-4)

A constant-velocity Kalman filter (state `[x,y,z,vx,vy,vz]`) is updated
sequentially by each in-gate detection with its native covariance. Association
uses χ²-gated global-nearest-neighbour (Hungarian); the Full UST-Fuse pipeline
adds JPDA-lite soft weights for robustness at trajectory crossings. Track
lifecycle is M-of-N confirmation → deletion after consecutive misses, with birth
suppression and velocity-consistent merging.

## 4. Metrics

- **Detection:** empirical Pd, clutter-per-scan, ROC (SNR threshold sweep).
- **Tracking:** position RMSE, OSPA (order-2, cutoff-c), MOTA/MOTP, ID switches,
  fragmentation, false/missed tracks, track completeness — computed on a common
  time grid with per-frame Hungarian assignment. Only *confirmed* tracks are
  scored, as on a real field trial.
- **Calibration (ЛР-7):** the tracker's existence probability is scored against
  whether each track state matched a truth — ECE, Brier, reliability diagram,
  selective risk-coverage.
- **Paired statistics (ЛР-3, section 5.1):** for the Reference-vs-UST-Fuse
  comparison the campaign reports the mean difference, a bootstrap 95 % CI,
  Cohen's d effect size, a paired t-test / Wilcoxon, and an approximate power
  analysis. **Effect size and CI are always reported — never a bare p-value.**

## 5. Domain randomisation & replay (ЛР-6, section 9)

`domain.randomize_scenario` turns one base scenario into a family of
related-but-different missions by perturbing weather, clutter, noise and Pd
scaling while preserving the scientific structure — realising "один реальний
політ → десятки варіантів" and the ≥10 replay/variant reuse KPI.

## 6. Reproducibility & provenance (ЛР-8, ЛР-10)

One master seed drives independent named RNG streams. The `Manifest` records the
experiment id, seed, seed-independent config hash, package versions and
environment, so any figure traces back to the RAW data that produced it and any
run reproduces bit-for-bit from the manifest.

## 7. Safety (section 12)

No active RF emission/jamming is modelled — the SDR is passive-only. Synthetic
data are labelled as synthetic. The twin is the measurement/metric/report
substrate; any LLM layer that generates scenarios, SOPs or report drafts on top
of it operates through a constrained, logged, human-approved interface.

## Interpreting the results honestly

The comparison is designed to reveal **trade-offs**. On a radar-dropout mission,
Full UST-Fuse improves **track completeness** and **calibration (ECE)** and adds
a **classification** capability the radar-only baseline cannot provide; the
radar-only baseline can be cleaner on pure localisation in easy conditions.
Reporting these trade-offs with effect sizes and confidence intervals — rather
than engineering a single dominant number — is the scientific contribution.
