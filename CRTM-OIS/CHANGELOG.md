# Changelog

## 1.0.0 — 2026-11-22
First public release accompanying the manuscript submitted to *Systems* (MDPI).

- Exact computational core: seven stages, blocks B0–B8, control unit CU, nine buses, failure codes E1–E4, trace register.
- Experiments of Section 3: reproduction of 15 CRTM reference values, five adequacy states E1–E5, sweep of t,
  Dirichlet weight robustness (ρ = 1, 4), non-compensation control, computational cost.
- Agent layer: block agents on a message bus, digital twin telemetry, data-quality guard, neural nowcast and forecast,
  watchdog with hysteresis, improvement advisor, LLM tool interface (Claude API) and offline analyst.
- Neural components in NumPy: monotone surrogate, telemetry autoencoder, forecaster, goal-weight calibration.
- 15 figures, executed demonstration notebook, 17 automated tests, data export (Data S1).
- Known difference: rule (12) gives 102.5 / 142.5 min for UN.S1.A1 M3/M4 in E2, Table A1 lists 102 / 142;
  the published table is used by default (effect on R below 0.0002).
