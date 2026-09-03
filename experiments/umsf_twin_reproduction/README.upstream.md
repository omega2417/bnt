# UMSF cyber-range digital twin - modular reference implementation

Executable companion to
`UMSF_CyberRange_Digital_Twin_Modules_UA.md`. Every element of the range -
each WAN link, access point, managed asset, battery cell, BMS, transfer
switch, EcoFlow station, sensor, detector and response playbook - is a
separate module with the same federate contract.

**Claim boundary.** This is a behavioural surrogate for planning synthetic
experiments. It opens no sockets, emits no attack traffic, and is not a
safety controller. Its numbers describe the model, not the physical range.

## Quick start

```bash
python3 tests/run_tests.py                  # 40 checks, ~4 s
python3 -m umsf_twin validate --config umsf_twin/config/inventory/demo.json
python3 -m umsf_twin run --config umsf_twin/config/inventory/demo.json \
    --output runs --replicates 1 --report
python3 -m umsf_twin verify --config umsf_twin/config/inventory/demo.json
```

No third-party packages are needed; Python 3.10 or newer is sufficient.

## Layout

| Path | Contents |
|---|---|
| `umsf_twin/core/` | parameters with provenance, clock, RNG, bus, federate contract, safety, contracts, orchestrator |
| `umsf_twin/federates/` | network, Wi-Fi, assets, workload, threats, power, telemetry, detection, response, ground truth |
| `umsf_twin/pipelines/` | normalization, features, labeling, data-quality gates, export |
| `umsf_twin/experiment/` | scenario compiler, DoE, Monte Carlo, calibration, metrics, statistics, runner, report |
| `umsf_twin/adapters/` | UniFi, Keenetic, BMS/MQTT and OpenTelemetry mappings (read-only) |
| `umsf_twin/config/` | demo inventory, safety policy, DoE factors, five scenarios |
| `tests/run_tests.py` | unit, property, contract, determinism, safety, integration, calibration, performance |

## Run artifacts

Each run directory contains `telemetry.csv`, `ground_truth.csv`, `alerts.csv`,
`response_audit.json`, `parameters.json`, `scenario.resolved.json`,
`summary.json`, `manifest.json` and, with `--report`, `report.md`. The
manifest carries the config hash, the engine source hash, the runtime
fingerprint, the evidence histogram and every artifact's SHA-256.
