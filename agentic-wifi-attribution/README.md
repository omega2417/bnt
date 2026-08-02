# Agentic Wi-Fi Spatial Attribution Readiness Platform — Reference Core

**Reproducible reference implementation** of the core scientific machinery of an
*Agentic Wi-Fi Spatial Attribution Readiness Platform for Critical Information
Infrastructure (CII)*, packaged for **Zenodo** and shipped with **two Google
Colab notebooks**.

> ⚠️ **Scope & ethics.** This is a *research / reference* artefact. All telemetry
> is **synthetic**; it contains **no real coordinates or configurations** of any
> critical information infrastructure. No experimental performance advantage is
> claimed without data (see [Limitations](#limitations)).

---

## What this package implements

The full platform described in the design prompt is large (25 modules, ~18
microservices). This repository is a **dependency-light, fully reproducible
core** (NumPy + SciPy) that implements the parts that carry the science and can
be *run and verified end-to-end*:

| Capability | Prompt module | Where |
|---|---|---|
| Explainable Bayesian localisation (grid posterior) | M8 | `awa/localization/fusion.py` |
| RSSI log-distance radiomap + robust (Student-t) likelihood | M4 | `awa/localization/radiomap.py`, `fusion.py` |
| FTM/RTT pseudo-range with LOS/NLOS mixture | M5 | `awa/localization/fusion.py` |
| IEEE 802.11bf WLAN-sensing *context* term | M6 | `awa/localization/fusion.py` |
| Uncertainty: posterior, HPD, entropy, sharpness, zones, modes | M8, M14 | `awa/localization/metrics.py` |
| Cross-modal consistency (HPD overlap, Mahalanobis, JSD) | M9 | `awa/agents/pipeline.py` |
| Digital twin: forward model, synthetic telemetry, attacks, drift | M7, M15 | `awa/digital_twin/twin.py` |
| Ten-agent event-driven orchestrator | M9 | `awa/agents/` |
| TRL/CRL/IRL/Operational readiness + gate rules | M11 | `awa/readiness/model.py` |
| Spatial Attribution Record (hash-anchored) | M12 | `awa/evidence/sar.py` |
| SOC decision tiers (LOG…FULL CONTAINMENT) | M13 | `awa/agents/context.py` |
| JSON Schemas (SAR, ReadinessProfile) | M25 | `schemas/` |

**Federated learning (M10)** is described in [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md)
and reflected in the readiness/roadmap, but is intentionally *not* executed in
this core (it needs multiple sites and a secure aggregator). This is flagged as
an explicit assumption.

---

## Quick start

### Option A — Google Colab (recommended)

Upload the two notebooks in [`notebooks/`](notebooks/) to
[Google Colab](https://colab.research.google.com/) (File → Upload notebook) and
run top to bottom:

1. **`01_autonomous_demo.ipynb`** — *autonomous*: fetches/creates everything it
   needs (no repository checkout required), defines a minimal self-contained
   version of the pipeline inline, and runs a rogue-AP incident end to end.
2. **`02_computed_visualizations.ipynb`** — *pre-computed*: imports the `awa`
   package and reproduces posterior heatmaps, HPD regions, calibration curves,
   readiness bars and an adversarial-scenario comparison. Ships **with saved
   outputs** so it renders without being re-run.

### Option B — local

```bash
cd agentic-wifi-attribution
python -m pip install -r requirements.txt          # numpy, scipy, matplotlib, jsonschema
python -m pip install -e .                          # optional: install awa

# run the demo
PYTHONPATH=. python examples/demo_rogue_ap.py

# run the tests (21 tests, ~3 s)
python -m pip install pytest
PYTHONPATH=. python -m pytest -q
```

---

## Minimal API

```python
from awa.api import build_environment, run_incident
from awa.digital_twin.twin import Scenario

env = build_environment(seed=1)                       # site + radiomap + twin
ctx = run_incident(env, true_xy=(33.0, 12.0),
                   scenario=Scenario.ROGUE_AP, seed=777)

print(ctx.uncertainty["MAP"])            # MAP coordinate
print(ctx.uncertainty["zone_posterior"]) # probability per security zone
print(ctx.consistency)                    # CONSISTENT / UNCERTAIN / CONFLICT
print(ctx.threat_state)                   # anomaly + indicators
print(ctx.decision)                       # bounded SOC decision tier
print(ctx.sar["provenance_hash"])         # hash-anchored SAR
```

Available scenarios (prompt Module 15): `CLEAN_LOS`, `CLEAN_NLOS`,
`TEMPORAL_DRIFT`, `MISSING_FTM`, `ROGUE_AP`, `RELAY`, `SELECTIVE_JAMMING`,
`RSSI_POWER_MANIPULATION`.

---

## The mathematics (summary)

**Path loss (radiomap).** Mean RSSI at distance *d* from a sensor:

```
RSSI(d) = P0 − 10·n·log10(d/d0) + X,   X ~ N(0, σ²)   [log-normal shadowing]
```

**Fused log-posterior** over grid cells *x* (any missing modality drops out as
a neutral term — never zeros):

```
log p(x | z) = log prior(x)
             + Σ_i w_i · log p_rssi(r_i | x)          [Student-t, robust]
             + Σ_j w_j · log p_ftm(d_j | x)           [LOS/NLOS mixture]
             + log p_sensing(x)                        [802.11bf context]
```

**FTM LOS/NLOS mixture** (NLOS adds a *positive* range bias):

```
p_ftm(d|x) = (1−ε)·N(d; ‖x−a‖, σ_los²) + ε·N(d; ‖x−a‖+b_nlos, σ_nlos²)
```

**HPD region**: smallest set of cells whose posterior mass ≥ α (default 0.95).
**Consistency**: HPD-overlap coefficient + MAP Mahalanobis distance (primary),
Jensen-Shannon divergence (reported). **Digital-twin residual**: RMS dB between
measured RSSI and the twin's prediction — the core domain-shift / manipulation
cue.

Full details and assumptions are in [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md).

---

## Design invariants (verified by tests)

From prompt Module 22, checked in [`tests/`](tests/):

- the posterior is normalised to 1, with no mass outside the grid;
- a **missing** modality is *neutral*, never zero, and never sharpens the posterior;
- degraded mode (jamming) **increases** uncertainty (HPD area);
- robust (Student-t) likelihood beats Gaussian under a wild outlier;
- readiness levels **cannot** be raised without verified evidence;
- gate rules are **non-compensatory** (high TRL cannot mask low IRL, etc.);
- agents **never** auto-execute containment without an approved policy;
- the immutable baseline radiomap is **never** silently rewritten;
- the SAR `provenance_hash` detects any tampering; SARs are deterministic.

```
$ pytest -q
21 passed
```

---

## Repository layout

```
agentic-wifi-attribution/
├── awa/                      # reference core (importable package)
│   ├── config.py             # versioned configuration & constants
│   ├── site.py               # synthetic site, zones, sensors/anchors
│   ├── api.py                # high-level build_environment / run_incident
│   ├── telemetry/            # incident-window assembly + quality scoring
│   ├── localization/         # grid, radiomap, fusion, metrics (HPD, ECE…)
│   ├── digital_twin/         # forward model, synthetic telemetry, attacks
│   ├── agents/               # 10 agents + orchestrator + decision tiers
│   ├── readiness/            # TRL/CRL/IRL/OR model + gate rules
│   └── evidence/             # Spatial Attribution Record + hashing
├── schemas/                  # JSON Schemas: SAR, ReadinessProfile
├── notebooks/                # 01_autonomous_demo, 02_computed_visualizations
├── examples/                 # demo_rogue_ap.py
├── tests/                    # 21 tests (invariants, schema, gates)
├── docs/                     # ARCHITECTURE.md (design & math), ROADMAP.md
├── requirements.txt · pyproject.toml
├── CITATION.cff · .zenodo.json · LICENSE
```

---

## Reproducibility

- Every stochastic step is seeded; `run_incident(..., seed=k)` is deterministic
  regardless of call order (the twin is reseeded per incident).
- Every SAR embeds versioned artefact ids (`model_version`, `radiomap_version`,
  `calibration_version`, `policy_version`, `data_schema_version`) and a
  `provenance_hash` over its canonical JSON.
- Notebook 2 ships with saved outputs; re-running it regenerates identical
  figures and hashes.

## Limitations

- **Synthetic only.** The radiomap is *model-based* (log-distance), not an
  empirical survey; absolute error numbers are not transferable to real sites.
- **No claimed advantage.** Accuracy figures in tests/notebooks are sanity
  bounds on synthetic data, not validated field performance.
- **Not executed here:** federated learning, the frontend, PostGIS/Timescale
  persistence, mTLS/PKI, and the microservice deployment — these are specified
  in the architecture docs and roadmap but out of scope for a single-file-run
  reference core.
- **Relay attacks** with small, uniform delays are only weakly separable from
  benign geometry with this synthetic set-up — a documented, honest limitation.

## Citation & license

See [`CITATION.cff`](CITATION.cff). Released under the [MIT License](LICENSE).
