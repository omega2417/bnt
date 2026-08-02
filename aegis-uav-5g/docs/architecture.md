# Architecture and module map

## Data flow

```
configs/*.yaml
   │  (pydantic schemas.py, loaded via config.py)
   ▼
simulation/            scenario_engine → {telemetry,network,behaviour}_simulator + mobility
   │  raw per-(uav,step) signals (pandas long frame)
   ▼
attacks/attack_engine  T1–T6 perturbations + ground-truth labels
   │
   ▼
features/              windowing (vectorised) → pipeline (fit scaler on train benign only)
   │  per-(uav,window) feature matrix, d ≈ 60
   ▼
agents/                ADA → TCA → AAA → RSA → PEA   (blackboard/ stores incidents)
   │
   ▼
evaluation/            metrics.py + statistics.py
   │
   ▼
experiments/           dataset.py, pipeline.py (run_core / TrainedContext), campaign.py
   │  metrics CSVs in artifacts/metrics/<run-group>/
   ▼
reporting/             report.py + formats.py → tables/, figures/, snippets, manifest
```

## Package layout

| Module | Responsibility |
|---|---|
| `config.py` | YAML loading, config hashing, run/environment manifests |
| `schemas.py` | pydantic contracts for every config + the `Incident` blackboard record |
| `rng.py` | single-seed randomness with named, reproducible substreams |
| `simulation/` | discrete-time mission, telemetry/network/behaviour signal generators |
| `attacks/` | simulation-only injection of T1–T6 with ground-truth labels |
| `features/` | windowing, derived + cross-vehicle features, leakage-free standardisation |
| `agents/` | ADA, TCA, AAA, RSA, PEA (each with I/O contract, logging, explanation) |
| `blackboard/` | shared incident store |
| `baselines/` | Random-Forest flow detector (B3); B1/B2/B4 via agent flags |
| `evaluation/` | detection/attribution/response/overhead metrics + statistical protocol |
| `experiments/` | dataset build, core pipeline, campaign orchestration (E1–E7) |
| `reporting/` | tables (CSV/TeX/MD), figures (SVG/PDF/PNG), stats, snippets, manifest |
| `integrations/` | Level-2 external-validity adapters (stubs / future work) |

## Performance notes

- Windowing uses `numpy` sliding-window views (vectorised) — a full smoke
  dataset builds in well under a second.
- `TrainedContext` trains the models once per (seed, override); the sensitivity
  sweep re-evaluates only the affected downstream stage (EWMA/TCA/RSA/weights),
  so most sweep points cost seconds, not a full retrain.

## Manuscript symbol mapping

| Symbol | Meaning | Where set |
|---|---|---|
| `d` | feature dimension | computed by `features/pipeline.py`, written to `parameters.csv` |
| `N` | fleet size | `configs/scenarios/*.yaml` |
| `Δ` | window length | `ada.window_length_s` |
| `κ, α` | EWMA sensitivity / adaptation | `ada.kappa`, `ada.alpha` |
| `τ_e` | severity floor | `tca.severity_floor` |
| `w_m` | modality weights | `tca.modality_weights` |
| `π_min` | confidence floor | `rsa.pi_min` |
| `λ₁, λ₂` | utility trade-offs | `rsa.lambda1`, `rsa.lambda2` |
