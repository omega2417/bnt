# UST-Fuse Engine (S2)

**Uncertainty-Aware Spatiotemporal Radar Fusion Framework**

*Українська назва: «UST-Fuse Engine — програмна система невизначенісно-орієнтованого
просторово-часового злиття радарних даних»*

Reference software (component **S2**) accompanying the manuscript on
**Uncertainty-Aware Spatiotemporal Radar Fusion (UST-Fuse)**. This is part 2 of
a three-project suite:

| ID | Project | Role |
|----|---------|------|
| S1 | RadarTwin-UAV | generates the synthetic, fully-labelled radar corpus |
| **S2** | **UST-Fuse Engine** (this repository) | the fusion / detection / classification / tracking algorithm |
| S3 | FuseMetrics Lab | experimental analytics, statistics and result tables |

---

## Overview

UST-Fuse Engine is the reference **C++17** implementation of the
uncertainty-aware spatiotemporal radar-fusion method. It ingests a synchronised
stream of synthetic or experimental radar measurements and converts it into a
set of continuously-maintained tracks, each carrying an object class, a
**calibrated** classification probability and **separate estimates of epistemic
and aleatoric uncertainty**.

The pipeline mirrors the manuscript:

1. **Ingestion / normalisation** — angular encoding of azimuth (sin/cos, so the
   ±180° wrap does not create discontinuities), handling of missing values, and
   an integral **measurement-quality index** computed from SNR, residual clutter
   and local observation completeness.
2. **Two-level attention** — **temporal** attention to the most informative
   observation ticks, and **cross-feature** attention over kinematic, spectral,
   trajectory and quality feature groups (gated by measurement quality, so
   unreliable measurements contribute proportionally less).
3. **Classification** — an **ensemble** of models with a **heteroscedastic**
   output layer yielding the mean posterior class probability, predictive
   entropy, **epistemic** uncertainty (ensemble disagreement / mutual
   information) and **aleatoric** uncertainty (from the heteroscedastic head).
   **Temperature scaling** calibrates the predicted probabilities.
4. **Multi-target tracking** — a constant-velocity Kalman filter with
   **probabilistic data association** that augments the standard kinematic
   likelihood with a **semantic compatibility coefficient** between the track's
   accumulated class distribution and the current classifier prediction. The
   semantic influence is automatically **attenuated under high epistemic
   uncertainty**, and the measurement-noise covariance is **adaptively inflated**
   from the measurement quality, so weak or incomplete measurements affect the
   state estimate in proportion to their reliability.

## What it computes

* the integral quality index of each radar observation;
* temporal attention coefficients;
* cross-feature attention weights (kinematic / spectral / trajectory / quality);
* posterior class probabilities;
* epistemic and aleatoric uncertainty;
* calibrated confidence values;
* the effective measurement-noise covariance;
* the kinematic association likelihood;
* the semantic compatibility coefficient;
* normalised association weights;
* updated track coordinates, velocities and covariances;
* track initiation, confirmation and termination.

## Build

Requires only a C++17 compiler and the standard library — **no third-party
dependencies**.

```bash
make            # produces ./ustfuse
# or manually:
g++ -std=c++17 -O2 -o ustfuse src/main.cpp
```

### Run on OnlineGDB

1. Open <https://www.onlinegdb.com/> and set the language to **C++ (g++ 17)**.
2. Paste the contents of [`src/main.cpp`](src/main.cpp) into the editor.
3. Press **Run**. If no input CSV is present, the engine generates a small
   internal demo stream so it runs **standalone**; to score the full S1 corpus,
   upload `radartwin_measurements.csv` into the OnlineGDB file panel first.

## Usage

```bash
./ustfuse [measurements.csv]
# examples
./ustfuse                                 # uses radartwin_measurements.csv, or an internal demo
./ustfuse radartwin_measurements.csv      # explicit S1 corpus
```

## Inputs and outputs

**Input** — `radartwin_measurements.csv` produced by RadarTwin-UAV (S1):

```
scenario_id,tick,time,truth_id,range_m,azimuth_deg,elevation_deg,
radial_vel_mps,snr_db,clutter_db,completeness,micro_doppler,quality
```

**Outputs**

| File | Description |
|------|-------------|
| `ustfuse_tracks.csv` | per-tick confirmed-track state and uncertainty |
| `ustfuse_classifications.csv` | per-measurement classifier output |

`ustfuse_tracks.csv`:
```
scenario_id,tick,time,track_id,pred_class,confirmed,x,y,z,cov_trace,
confidence,entropy,epistemic,aleatoric,p_uav,p_bird,p_other
```

`ustfuse_classifications.csv`:
```
scenario_id,tick,time,truth_id,predicted,confidence,entropy,epistemic,
aleatoric,quality,p_uav,p_bird,p_other
```

`pred_class` / `predicted`: `0 = UAV`, `1 = BIRD`, `2 = OTHER`. Both files are
consumed directly by FuseMetrics Lab (S3).

## Notes on the implementation

The engine is a compact, dependency-free reference model rather than a trained
deep network: the ensemble members are seeded from physically-motivated class
prototypes (micro-Doppler, radial speed and SNR are the dominant discriminators)
and perturbed independently, so their disagreement produces a genuine epistemic
signal. This makes the whole method inspectable and reproducible in a single
translation unit while preserving every algorithmic element described in the
manuscript. The prototypes and calibration temperature are exposed as constants
near the top of `src/main.cpp` for experimentation and ablation.

## Reproducibility

* Randomness (ensemble perturbations, fallback stream) derives from a single
  seed; per-scenario sub-seeds are mixed deterministically.
* The engine is deterministic given the same input and seed.

## Pipeline

```
RadarTwin-UAV (S1)  ──►  UST-Fuse Engine (S2)  ──►  FuseMetrics Lab (S3)
   measurements.csv          tracks.csv               metrics, tables,
   truth.csv                 classifications.csv       figures, statistics
```

## License

MIT — see [LICENSE](LICENSE). If you use this software, please cite it via
[CITATION.cff](CITATION.cff) and the accompanying UST-Fuse manuscript.
