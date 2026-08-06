# Architecture

The twin is a small, dependency-light Python package (`numpy`, `scipy`,
`matplotlib`, `pandas`, `pyyaml`) organised as a linear data-flow pipeline.

## Data flow

```
ScenarioConfig + RangeConfig  ──►  DigitalTwin.run()  ──►  RawMission (immutable)
        │                                                        │
   RNGHub(seed)                                     Reference / USTFuse fusion
        │                                                        │
   deterministic per-stream RNG                     MultiTargetTracker → [Track]
                                                                 │
                                     metrics: detection · tracking · calibration
                                                                 │
                                     ExperimentResult ──► viz · report · manifest
```

## Key design decisions

**Immutable RAW.** `DigitalTwin.run()` produces one `RawMission`. *Both* fusion
modes consume that same object, so Reference vs UST-Fuse is a genuine paired
comparison on identical inputs — the scientific requirement from the proposal.

**Everything in a local ENU frame (metres, seconds).** Small training range, so
a flat East-North-Up frame keeps the mathematics transparent (`geometry.py`).

**Heterogeneous sensors, one Cartesian tracker.** Each sensor emits a position
estimate plus a 3×3 ENU covariance. A ranging radar gives a compact covariance;
a bearing-only camera/RF/acoustic sensor gives a *needle-shaped* covariance
elongated along the line of sight (`geometry.spherical_measurement_covariance`).
A single constant-velocity Kalman filter then fuses them correctly: the radar
fixes range, the accurate bearings sharpen cross-range.

**Track-initiation policy.** Only range-providing sensors may *initiate* a
track; bearing-only sensors may only *update* existing tracks. A single bearing
cannot localise a 3-D point, and this policy removes along-line-of-sight ghost
tracks. Confirmation is likewise *range-supported* (M-of-N radar hits), so
bearing clutter cannot manufacture false tracks.

**Track management.** Birth suppression (no new track next to an existing one)
and velocity-consistent merging bound the number of simultaneous tracks and
suppress spurious ID switches.

**Reproducibility first.** `RNGHub` derives independent, named RNG streams from
one master seed. `provenance.Manifest` records a seed-independent config hash, a
seed-dependent experiment id, package versions and environment. Same seed +
same config ⇒ identical RAW and identical figures.

## Module map

| Module | Responsibility |
| --- | --- |
| `config.py` | dataclasses: `SensorConfig`, `RangeConfig`, `ScenarioConfig`, `ExperimentConfig`; `default_range()` |
| `rng.py` | reproducible named RNG streams |
| `geometry.py` | ENU ↔ spherical, covariance propagation |
| `trajectories.py` | analytic UAV trajectory generators |
| `sensors/` | `Sensor` base + radar / EO-IR / RF-SDR / acoustic |
| `clock.py` | clock offset/drift estimation & correction (ЛР-1) |
| `network.py` | latency, jitter, packet loss |
| `faults.py` | fault injection & red-team spoofing (ЛР-5) |
| `domain.py` | weather profiles & domain randomisation (ЛР-6) |
| `twin.py` | world orchestrator → `RawMission` |
| `fusion/` | `ReferenceFusion`, `USTFuse`, frame builder |
| `tracking/` | `KalmanCV`, association (GNN/JPDA-lite), `MultiTargetTracker` |
| `metrics/` | detection, tracking (RMSE/OSPA/MOTA/ID), calibration, paired stats |
| `experiment.py` | `run_experiment` → `ExperimentResult` |
| `campaign.py` | multi-mission paired analysis |
| `scenarios.py` | 12-scenario library |
| `provenance.py` | manifest, checksums, versions |
| `viz/` | 16 plot functions + dashboard + figure pack |
| `report.py` | bilingual field-trial Markdown/HTML reports |
| `cli.py` | command-line interface |
