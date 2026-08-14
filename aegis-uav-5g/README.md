# Aegis-UAV-5G

**Reproducible Agentic AI Testbed for Detection, Attribution and Containment of
Cyberattacks in 5G-Enabled UAV Networks**

Aegis-UAV-5G is a modular, fully reproducible research testbed that generates the
complete experimental evidence base for the manuscript *"Agentic Artificial
Intelligence for Autonomous Detection, Attribution, and Containment of
Cyberattacks in 5G-Enabled UAV Networks."* It simulates 5G-enabled UAV missions,
injects six attack classes (T1–T6), runs a five-agent agentic pipeline over a
shared incident blackboard, and produces **every table, figure and statistical
result** for Sections 5–7 — with no hand-entered numbers.

> ⚠️ **Safety.** The attack engine is a *simulation-only* research tool: every
> "attack" is a numeric perturbation of synthetic signals used to train and
> evaluate the defence. It contains no operational instructions for compromising
> real UAVs, and every autonomous containment action passes a safety mask and a
> post-condition check.

## Architecture

```
Mission Scenario Generator
  ├── UAV telemetry simulator
  ├── 5G/FANET traffic simulator
  ├── Behaviour/session event simulator
  └── Attack injector T1–T6
        ▼
  Feature Engineering Layer  ──►  Shared Incident Blackboard
        ▼                              │
   ADA → TCA → AAA → RSA → PEA  (anomaly · correlation · attribution ·
        ▼                        response · enforcement)
  Metrics & Audit Recorder
        ▼
  Statistical Analysis + Tables + Figures
```

- **ADA** — three per-modality autoencoders + adaptive EWMA threshold `θ = μ + κσ`.
- **TCA** — spatio-temporal + topology-aware correlation; fused severity `S(E)=Σ wₘ s̄ₘ`.
- **AAA** — hierarchical calibrated classifier (macro `{GNSS, network, session/behaviour}`
  → leaf `T1–T6`), posterior, and counterfactual origin attribution.
- **RSA** — transparent utility policy `U(r|E)=B(r,â)−λ₁C(r)−λ₂D(r)` with safety
  mask `R_safe` and confidence floor `π_min` (no RL).
- **PEA** — enforces the action on the simulator, verifies the post-condition,
  rolls back / escalates on failure.

See [`docs/ADR-0001-architecture.md`](docs/ADR-0001-architecture.md) and
[`docs/architecture.md`](docs/architecture.md).

## Install

```bash
cd aegis-uav-5g
python -m pip install -e .          # or: pip install -e ".[dev]"
```

Requires Python ≥ 3.11. Core dependencies: NumPy, pandas, scikit-learn, SciPy,
matplotlib, pydantic, PyYAML, PyArrow, psutil. Heavier/optional stacks (PyTorch,
Optuna, MLflow, ns-3 adapters) live behind extras and are **not** needed for the
Level-1 pipeline.

## Exact reproduction commands

Everything below regenerates from configs + seeds only.

```bash
# Fast, fully reproducible smoke campaign (3 seeds) — all tables + figures:
aegis campaign --config configs/experiments/smoke.yaml      # or: make smoke

# Full publication campaign (20 seeds, 20-UAV missions):
aegis campaign --config configs/experiments/paper_v1.yaml   # or: make paper

# Rebuild only the report artifacts from existing metrics:
aegis report --run-group smoke

# Map every manuscript [DATA REQUIRED] item to its computed value + evidence file:
aegis manuscript-map --run-group smoke     # -> artifacts/tables/smoke/manuscript_data_map.{md,json}

# Individual building blocks:
aegis simulate      --config configs/scenarios/base_20_uav.yaml --attack configs/attacks/T1.yaml
aegis build-dataset --config configs/experiments/dataset_v1.yaml
```

Illustrative outputs of the `smoke` campaign are checked in under
[`docs/example_results/`](docs/example_results/) so you can see the generated
tables and the manuscript data map without running anything. For the Zenodo-ready
release procedure see [`docs/DATA_AVAILABILITY.md`](docs/DATA_AVAILABILITY.md).

### Google Colab

[`notebooks/aegis_uav_5g_colab.ipynb`](notebooks/aegis_uav_5g_colab.ipynb) runs
the whole pipeline in the browser — simulate a mission, inject an attack, run the
five-agent pipeline, and render the confusion matrix, detection table and latency
inline; an optional cell runs the full `smoke` campaign. Open it in Colab via
**File → Upload notebook** (or from GitHub if the repo is public).

### Docker (one command, full pipeline)

```bash
docker build -t aegis-uav-5g:latest .
docker run --rm -v "$PWD/artifacts:/app/artifacts" aegis-uav-5g:latest \
  aegis campaign --config configs/experiments/smoke.yaml
```

## Outputs

After a campaign, `artifacts/<kind>/<run-group>/` contains:

| Artifact | File |
|---|---|
| Table 2 — parameters (`d`, `N`, `Δ`, `κ`, `α`, `τ_e`, `w_m`, `π_min`, `λ₁`, `λ₂`, seeds, counts) | `tables/<rg>/table_2_parameters.{csv,tex,md}` |
| Table 3 — detection performance | `tables/<rg>/table_3_detection.*` |
| Table 4 — ablation study | `tables/<rg>/table_4_ablation.*` |
| Table 5 — containment effectiveness | `tables/<rg>/table_5_containment.*` |
| Table 6 — CPU/RAM/bandwidth/latency | `tables/<rg>/table_6_overhead.*` |
| Fig. 4 — confusion matrix | `figures/<rg>/fig_4_confusion_matrix.{svg,pdf,png}` |
| Fig. 5 — detection/containment latency | `figures/<rg>/fig_5_latency.*` |
| Sensitivity / scalability plots | `figures/<rg>/{sensitivity,scalability}.*` |
| Statistical tests (Wilcoxon + Holm, effect sizes) | `tables/<rg>/statistical_test_report.*` |
| Error analysis | `tables/<rg>/error_analysis.*` |
| Manuscript snippets (Sections 5–7) | `tables/<rg>/manuscript_snippets.md` |
| Per-incident explanation objects | `logs/<rg>/incidents/*.json` |
| Run + report manifests (run IDs, seeds, config hash, env) | `manifests/*.json` |

Every figure is built from a machine-readable CSV/Parquet; every table cell is
computed, never typed.

## Reproducibility contract

- Single master seed drives all randomness (`SeededRng` substreams).
- Every run records a **run ID, timestamp, git commit, config hash, environment
  manifest, seed and output directory** (`artifacts/manifests/`).
- Scenario-level 60/20/20 split; the **test split is evaluated once**, after tuning.
- No `test` data is used to choose thresholds or hyperparameters.
- The report manifest links each manuscript claim to its evidence file.

## Experiments (E1–E7)

E1 detection · E2 attribution · E3 response · E4 ablation · E5 sensitivity
(`κ, α, Δ, τ_e, w_m, π_min, λ₁, λ₂`) · E6 scalability (`N = 5…80`) · E7 robustness.

## Two-level simulation

- **Level 1 (this repo):** fully reproducible Python simulation + statistics — a
  clearly-labelled *synthetic evaluation*, sufficient for the current paper.
- **Level 2 (`src/aegis_uav/integrations/`):** optional external-validity
  adapters (PX4/Gazebo, ns-3/5G-LENA, MAVLink, Mininet) — future work.

## Development

```bash
make lint      # ruff
make type      # mypy
make test      # pytest
```

## License & citation

MIT (see [`LICENSE`](LICENSE)). Please cite via [`CITATION.cff`](CITATION.cff).
