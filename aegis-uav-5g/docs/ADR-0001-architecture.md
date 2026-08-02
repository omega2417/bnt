# ADR-0001: High-level architecture of Aegis-UAV-5G

Status: Accepted · Date: 2026-08-02

## Context

The manuscript *"Agentic Artificial Intelligence for Autonomous Detection,
Attribution, and Containment of Cyberattacks in 5G-Enabled UAV Networks"* has a
number of `[DATA REQUIRED]` placeholders (feature dimension `d`; the parameters
`N, Δ, τ_e, κ, α, w_m, π_min, λ₁, λ₂`; model architectures; per-class sample
counts; Tables 3–6; Figs 4–5; statistical tests). This project must produce all
of them **automatically, without hand-entered numbers**, and with full
reproducibility.

## Decision

1. **Two-level simulation strategy.** Level 1 is a fully reproducible,
   discrete-time Python simulator (telemetry + flow-level network +
   behaviour/session events) with a controllable attack injector. Level 2
   (PX4/Gazebo, ns-3/5G-LENA, MAVLink, Mininet) is an optional external
   validation layer exposed through `integrations/` adapters and reported as
   future work. **This repository ships a complete Level 1.**

2. **Modular pipeline, separated concerns:**
   `simulation → attacks → features → agents (ADA/TCA/AAA/RSA/PEA) via a shared
   blackboard → evaluation → reporting`, orchestrated by `experiments`.

3. **Agentic realisation without an LLM core.** The five agents are
   specialised, stateful, deterministic components with explicit input/output
   contracts, per-decision explanation objects, and bounded autonomy (safety
   mask + post-condition verification). An LLM is deliberately *not* on the
   detection/response path — it would harm determinism and reproducibility.

4. **Attribution model.** Hierarchical, calibrated tree-based classifier
   (macro `{GNSS, network, session/behaviour}` → leaf `T1–T6`) as the main
   method; flat classifier, Random-Forest flow classifier and MLP are baselines.

5. **Response selection.** Transparent utility policy
   `U(r|E) = B(r,â) − λ₁·C(r) − λ₂·D(r)` with a safety mask `R_safe` and a
   confidence floor `π_min`; **no reinforcement learning** in v1.

6. **Reproducibility contract.** Every run records a `run_id`, timestamp, git
   commit, config hash, resolved seed, environment manifest and output
   directory. All randomness flows from a single seeded RNG. The test split is
   touched exactly once, after tuning. Every table/figure is generated from
   machine-readable CSV/Parquet — never from hand-entered values.

## Consequences

- The Level-1 MVP runs end-to-end from one command (`make smoke` / `aegis
  campaign`) and emits every manuscript artifact plus a manifest linking each
  claim to its evidence file.
- Heavy/optional dependencies (PyTorch, Optuna, MLflow, ns-3) are isolated
  behind extras and adapters so the core pipeline stays lightweight and
  deterministic.

See `docs/architecture.md` for the module map and data-flow diagram.
