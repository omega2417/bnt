# Roadmap: from reference core to production (TRL 9 / IRL 9 / full OR)

The reference core in this repository sits at roughly **TRL 4** (components
validated in a laboratory/simulation environment). The path below mirrors the
12 implementation stages of the design prompt (Module 24) and the readiness
gate rules (Module 11.5).

| Stage | Focus | Exit criteria (evidence) | Readiness effect |
|---|---|---|---|
| 1 | Requirements, domain model, threat model, readiness model | SRS, threat model, gate rules (this repo) | TRL 3→4 |
| 2 | Telemetry ingestion, schemas, sensor registry, PostGIS | Ingest PCAP/MQTT/Kafka/REST; ER model live | IRL 3→4 |
| 3 | RSSI fingerprinting + versioned radiomap | Empirical survey; device/channel-aware calib; rollback | TRL 4→5 |
| 4 | FTM/RTT + geometry (Fisher info, GDOP) | LOS/NLOS validated; deceptive-ranging tests | TRL 5 |
| 5 | WLAN sensing (802.11bf) | CSI ingest; sensing likelihood; privacy minimisation | IRL 4→5 |
| 6 | Bayesian fusion, HPD, calibration | ECE/coverage on real relevant-environment data | TRL 5→6 |
| 7 | Digital twin | Twin-vs-real residual validated; Monte-Carlo | TRL 6 |
| 8 | Agentic orchestration | Event-driven bus; formal agent contracts; SOAR | IRL 5→6 |
| 9 | Federated learning | Multi-site; secure agg; Byzantine-robust; LOSO val. | IRL 6→7 |
| 10 | SOC/SIEM/SOAR + SAR | STIX/CEF export; playbooks; tamper-evident store | IRL 7→8, OR↑ |
| 11 | Readiness assessment subsystem | Evidence-backed TRL/CRL/IRL/OR dashboards | CRL↑ |
| 12 | Adversarial validation, MLOps, deployment, docs | Operational-environment pilot; SLOs; DR; audits | TRL 7→9, OR→high |

## Blocking gates to production

Per Module 11.5, production requires **all** of: TRL/CRL/IRL/OR ≥ 7, evidence
completeness ≥ 0.8, no gate findings, no blocking gaps. In particular:

- an uncalibrated model caps the achievable level regardless of CRL;
- high IRL does not compensate for missing SOC SOPs / playbooks (OR);
- no readiness level may be raised without verified evidence.

## Scaling recommendations

- Move compute-critical inner loops (grid likelihoods, Monte-Carlo) to Rust/C++
  via PyO3/pybind11; vectorise per-incident batches.
- Replace the model-based radiomap with a versioned empirical survey store
  (DVC-tracked), keeping the immutable-baseline + trusted-update discipline.
- Add secure aggregation + differential privacy before any cross-site federation.
- Introduce a message bus (Kafka) and idempotent event processing for the agent
  orchestrator; keep the state-machine semantics.
