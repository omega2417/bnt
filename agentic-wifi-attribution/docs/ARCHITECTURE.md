# Architecture & Design — Agentic Wi-Fi Spatial Attribution Readiness Platform

This document maps the design prompt (25 modules) onto the reference core in
this repository and specifies the parts that are designed-but-not-executed
here. Assumptions are flagged **[A]**.

---

## 1. Concept

A modular platform for **evidentiary** spatial identification and attribution of
IEEE 802.11 sources in critical-information-infrastructure (CII) environments.
It ingests RSSI / FTM-RTT / WLAN-sensing telemetry, produces a **calibrated
spatial posterior**, quantifies uncertainty, threat context and technological
readiness, and emits a machine-readable evidence record for SOC/SIEM/SOAR.

The reference core proves the *inference and governance loop*:

```
telemetry ─▶ incident window ─▶ per-modality likelihoods ─▶ fused posterior
   ─▶ uncertainty + zones + HPD ─▶ drift / consistency / threat
   ─▶ verification plan ─▶ readiness ─▶ bounded SOC decision
   ─▶ Spatial Attribution Record (hash-anchored) ─▶ governance gate
```

## 2. Users

Analysts (operator view), SOC engineers (analytic/decision view), auditors
(audit view), researchers (research view) — the four explanation levels of
prompt Module 8. Governance/security officers own policy and readiness.

## 3. Data model (core)

Implemented as dataclasses (`awa/site.py`, `awa/config.py`,
`awa/digital_twin/twin.py`, `awa/telemetry/quality.py`):

- **Site** → Zones (`public|controlled|restricted|critical|forbidden`) → Sensors
  / FTM anchors (position, `trust_domain`, `provenance_score`, `health_score`,
  `pmf_enabled`, capability flags for RSSI/FTM/sensing).
- **TelemetrySample** → per-sensor RSSI (dBm), per-anchor RTT (s), sensing
  motion context, `missing_mask`, scenario tag, provenance notes.
- **IncidentWindow** → completeness, channel coverage, freshness, rejected
  measurements, quality components.

Persistent-storage ER model (PostgreSQL/PostGIS/TimescaleDB) is specified in
prompt Module 21; **[A]** not persisted in this core (in-memory only).

## 4. Mathematical models

### 4.1 Radiomap (RSSI)
Log-distance path loss with log-normal shadowing (`radiomap.py`):
`RSSI(d) = P0 − 10 n log10(d/d0) + X`, `X ~ N(0, σ²)`. **[A]** single-slope
model; production uses per-reference-point empirical statistics (means, medians,
quantiles, variance, MAD) — the `RadioMap` object is structured to hold those.

### 4.2 RSSI likelihood (robust)
Student-t (default, dof configurable) or Gaussian, with a contamination floor
so a single wild outlier cannot veto a cell. Per-sensor weights `w_i` fold in
provenance / health.

### 4.3 FTM/RTT
Pseudo-range `d = c·RTT/2`; LOS/NLOS Gaussian mixture with a **positive** NLOS
bias; physically-impossible ranges rejected. Next-best-anchor selection uses an
expected-information-gain proxy (geometry-aware).

### 4.4 WLAN sensing (802.11bf)
A **context** term: a soft radial prior around detected motion, muted below a
provenance floor. Never used as unconditional identity evidence (prompt M6).

### 4.5 Fusion & uncertainty
Log-linear pooling on the grid (see README). Outputs: MAP, posterior mean, full
posterior, HPD region (area + achieved mass), entropy, sharpness, zone
posteriors, spatial mode count (multimodality). Calibration (ECE / HPD
coverage) is computed by aggregating many incidents (Notebook 2).

### 4.6 Consistency, drift, threat
- **Consistency**: HPD-overlap coefficient + MAP Mahalanobis (primary), JSD
  (reported) → `CONSISTENT|UNCERTAIN|CONFLICT`.
- **Drift**: digital-twin residual (RMS dB) vs immutable baseline → z-like
  score; the baseline is **never** auto-rewritten.
- **Threat**: fuses twin residual, consistency and rejected-measurement cues
  into an anomaly score and level; the ground-truth scenario tag is recorded
  for reproducibility but **not** used as a detection oracle.

## 5. Agentic AI (Module 9)

Ten single-responsibility agents over a shared blackboard (`AgentContext`), run
by a deterministic state-machine `Orchestrator`:

```
Observation ▶ Localization ▶ Drift ▶ Consistency ▶ ThreatAssessment
  ▶ Verification ▶ Readiness ▶ SocDecision ▶ Evidence ▶ Governance
```

Agent prohibitions (M9) are enforced by `GovernanceAgent` as a final gate:
no self-changing thresholds, no baseline rewrite, no containment without an
approved policy (containment tiers are downgraded to HUMAN-IN-THE-LOOP),
uncertainty is always surfaced, and every step is written to an append-only
audit trail.

## 6. Digital twin (Module 7)

Forward radio model + synthetic telemetry generator + adversarial/degradation
injectors (rogue AP, relay, selective jamming, RSSI power manipulation, NLOS,
temporal drift, missing modality). The **twin residual** (prediction vs
measurement) is the domain-shift / manipulation detector. Monte-Carlo and
what-if sweeps are demonstrated in Notebook 2.

## 7. Explainable Bayesian localisation (Module 8)

Every result carries: MAP, posterior, HPD, per-zone probability, entropy,
sharpness, mode count, per-sensor and per-modality contributions, missing
modalities, and the verification suggestion that would most reduce uncertainty
(next-best anchor). Four explanation levels are supported by exposing the same
record at increasing detail (operator → analyst → auditor → researcher).

## 8. Readiness (Module 11)

Four dimensions (TRL, CRL, IRL, Operational) on a 1–9 scale, each with typed
evidence items. `assess_profile` applies **non-compensatory gate rules**:

- IRL lagging TRL by > 2 caps/flags the profile;
- IRL cannot compensate for missing operational procedures;
- CRL cannot compensate for an uncalibrated/under-validated model;
- overall evidence completeness < 0.5 reduces trust in every level;
- production readiness requires *all* dimensions ≥ 7, no gate findings, no
  blocking gaps, and evidence completeness ≥ 0.8.

The result is a `ReadinessProfile` (see `schemas/readiness_profile.schema.json`)
with blocking gaps, recommended actions and residual risk — **not** a simple
average.

## 9. Spatial Attribution Record (Module 12)

Deterministic JSON with all fields of M12, validated against
`schemas/sar.schema.json`, closed with a SHA-256 `provenance_hash` over its
canonical form and a demonstration `signature`. **[A]** real deployments sign
with PKI/mTLS and store in tamper-evident (append-only) storage.

## 10. SOC / SIEM / SOAR (Module 13)

Decision tiers `LOG_ONLY(0) … FULL_CONTAINMENT(6)`. The `SocDecisionAgent`
selects a *bounded* tier from anomaly, consistency, critical-zone mass and
evidence completeness; containment always passes through the governance gate.
REST/webhook/STIX/CEF exports are specified but **[A]** not served here.

## 11. Federated learning (Module 10) — designed, not executed **[A]**

Per-site local radiomaps/geometry/policies; only permitted artefacts leave a
site (model params, gradients, aggregated statistics, drift signatures, attack
patterns, calibration summaries). Aggregation: FedAvg / FedProx / personalised,
with secure aggregation, optional differential privacy, Byzantine-robust
aggregation, poisoning detection, update quarantine, signed updates and a
federated model registry. Never transmitted: precise plans, asset coordinates,
raw PCAP, personal identifiers, full trajectories, local keys.

## 12–19. Platform concerns (specified; **[A]** not in the core)

- **API (M20)**: FastAPI OpenAPI contracts for `/telemetry/*`, `/localization/*`,
  `/verification/plan`, `/evidence/*`, `/readiness/*`, `/digital-twin/*`,
  `/federation/round`, `/models/*`, `/soar/action`, `/audit/*`.
- **DB (M21)**: PostgreSQL + PostGIS + TimescaleDB; MinIO/S3 for artefacts.
- **Frontend (M17)**: React + MapLibre + Deck.gl dashboards (4 roles).
- **Security (M16)**: Zero-Trust, RBAC/ABAC, OIDC/OAuth2.1, mTLS/PKI, signed
  telemetry/models, SBOM, SAST/DAST, append-only audit, encryption at rest/in
  transit, pseudonymisation & minimisation.
- **MLOps**: MLflow + DVC, model registry, signed promotions, rollback.
- **Deployment**: Docker/Kubernetes/Helm/Argo CD/Vault/Terraform.

## 20. Testing (Module 22)

`tests/` covers the critical invariants (posterior normalisation, missing =
neutral, degraded ⇒ more uncertainty, robust > Gaussian under outliers, no
readiness without evidence, non-compensatory gates, no unauthorised
containment, no baseline rewrite, tamper-evident SAR, deterministic SAR).
Property-based, load, chaos and full SOC end-to-end tests are specified for the
production system.

## 21. From prototype to production

See [`ROADMAP.md`](ROADMAP.md).
