# RadarTwin-UAV (S1)

**Synthetic Radar Scenario and Digital Twin Generator for small-UAV detection**

*Українська назва: «RadarTwin-UAV — програмний комплекс генерації синтетичних
радарних даних і цифрових двійників сценаріїв виявлення БпЛА»*

Reference software (component **S1**) accompanying the manuscript on
**Uncertainty-Aware Spatiotemporal Radar Fusion (UST-Fuse)**. This is part 1 of
a three-project suite:

| ID | Project | Role |
|----|---------|------|
| **S1** | **RadarTwin-UAV** (this repository) | generates the synthetic, fully-labelled radar corpus |
| S2 | UST-Fuse Engine | the fusion / detection / classification / tracking algorithm |
| S3 | FuseMetrics Lab | experimental analytics, statistics and result tables |

---

## Overview

RadarTwin-UAV is a self-contained **C++17** digital twin of a monitored volume
of airspace. Within it, the program models the motion of small UAVs, birds and
other aerial objects, the operation of a radar sensor, clutter, missed
observations and measurement errors, and it produces a **reproducible,
fully-labelled** corpus for developing and testing detection, classification and
multi-target tracking methods.

It generates **individual, simultaneous, sequential and combined** multi-target
scenarios. For every object it samples speed, altitude, approach direction,
manoeuvre type, initial coordinates, effective radar cross-section (RCS) and
dwell time. At the sensor level it models range, azimuth, elevation, radial
velocity, signal intensity, signal-to-noise ratio (SNR), residual clutter,
observation completeness and micro-Doppler characteristics.

For every observation tick the program emits exact ground truth (target id,
class, coordinates, velocity vector, existence flag and the measurement-to-truth
correspondence), which lets downstream tools compute detection probability,
false-alarm rate, coordinate error, missed observations, track fragmentation and
identity switches.

## What it computes

* object coordinates and velocities at each time step;
* radial velocity relative to the radar;
* range, azimuth and elevation errors;
* SNR and clutter level;
* observation completeness;
* probability of a missed measurement;
* the intensity of a Poisson stream of false alarms;
* spectral / micro-Doppler descriptors;
* reference trajectories and the target–measurement correspondence.

## Build

Requires only a C++17 compiler and the standard library — **no third-party
dependencies**.

```bash
make            # produces ./radartwin
# or manually:
g++ -std=c++17 -O2 -o radartwin src/main.cpp
```

### Run on OnlineGDB

1. Open <https://www.onlinegdb.com/> and set the language to **C++ (g++ 17)**.
2. Paste the contents of [`src/main.cpp`](src/main.cpp) into the editor.
3. Press **Run**. The console prints a summary; the CSV/JSON files are written to
   the OnlineGDB working directory and can be downloaded from the file panel.

## Usage

```bash
./radartwin [seed] [num_scenarios]
# examples
./radartwin                 # seed=20260730, 8 scenarios (defaults)
./radartwin 12345 16        # custom seed, 16 scenarios
```

## Outputs

| File | Description |
|------|-------------|
| `radartwin_measurements.csv` | sensor-level detections, **including false alarms** (`truth_id = -1`) |
| `radartwin_truth.csv` | per-tick ground-truth object states |
| `radartwin_scenarios.json` | scenario configuration, random seed and run metadata |

### `radartwin_measurements.csv`

```
scenario_id,tick,time,truth_id,range_m,azimuth_deg,elevation_deg,
radial_vel_mps,snr_db,clutter_db,completeness,micro_doppler,quality
```

`truth_id = -1` marks a clutter / false-alarm detection. `quality` is the
integral measurement-quality index in `[0, 1]` combining SNR, residual clutter
and completeness — it is consumed directly by S2.

### `radartwin_truth.csv`

```
scenario_id,tick,time,truth_id,class,x,y,z,vx,vy,vz,exists
```

`class`: `0 = UAV`, `1 = BIRD`, `2 = OTHER`. Coordinates are in a local
East-North-Up (ENU) frame with the sensor at the origin.

## Reproducibility

* All randomness derives from a single seed (`std::mt19937_64`); the same seed
  reproduces the corpus bit-for-bit.
* The seed and scenario configuration are recorded in
  `radartwin_scenarios.json`.
* Output formats are plain CSV/JSON so the corpus can be archived on Zenodo and
  re-used as an open research dataset. (Parquet export can be added downstream;
  the schema is Parquet-ready.)

## Pipeline

```
RadarTwin-UAV (S1)  ──►  UST-Fuse Engine (S2)  ──►  FuseMetrics Lab (S3)
   measurements.csv          tracks.csv               metrics, tables,
   truth.csv                 classifications.csv       figures, statistics
```

## License

MIT — see [LICENSE](LICENSE). If you use this software, please cite it via
[CITATION.cff](CITATION.cff) and the accompanying UST-Fuse manuscript.
