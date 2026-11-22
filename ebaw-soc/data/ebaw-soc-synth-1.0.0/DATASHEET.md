# Datasheet: EBAW-SOC-Synth 1.0.0

Synthetic agentic response episodes with evidence-bound action warrants. The structure follows
*Datasheets for Datasets* (Gebru et al., 2021).

> **All records are synthetic.** They are produced by the discrete-event model of the article
> *Evidence-Bound Action Warrants for Agentic Security Operations* (submitted to Inventions, MDPI, 2026)
> and realize the dataset **proposed** in its Section 6.1 (record schema of Table 7, scenario catalog of
> Table 8). They are not measurements of a real security operations center, contain no personal data
> and must not be presented as cyber-range or production data.

## 1. Motivation

* **Purpose.** Admission control for autonomous security actions cannot be evaluated with alert-level
  intrusion datasets. Such an evaluation needs, for every action an agent proposes, the evidence and its
  timing, the ledger confirmation state, the policy state, the gateway verdict and the execution outcome.
  This dataset fixes that schema and the tooling ahead of the cyber-range campaign of Section 6.3. It
  makes it possible to fit calibration maps, select thresholds and budgets, and benchmark admission
  policies reproducibly.
* **Creator.** Dmytro Prokopovych-Tkachenko, Department of Cybersecurity and Information Technologies,
  University of Customs and Finance, Dnipro, Ukraine (ORCID 0000-0002-6590-3898).
* **Funding.** None declared.

## 2. Composition

| Scenario | Name | Techniques | Perturbation | Episodes | Proposals | Adversarial |
|---|---|---|---|---:|---:|---:|
| D1 | Credential compromise and lateral movement | T1078, T1110, T1021 | none (baseline) | 150 | 900 | 14 |
| D2 | Ransomware precursor | T1059, T1490, T1486 | telemetry backlog (stale evidence) | 150 | 900 | 14 |
| D3 | Command and control with exfiltration | T1071, T1041 | ledger delays 5–60 s, validator outage | 120 | 720 | 9 |
| D4 | Phishing with a malicious attachment | T1566, T1204 | policy changes during the response | 120 | 720 | 9 |
| D5 | Benign administrative look-alikes | T1047, T1053 | evidence retraction | 150 | 900 | 15 |
| D6 | Indirect prompt injection | AML.T0051.001 | injected and hallucinated proposals | 100 | 600 | 352 |
| D7 | Tampering with SIEM records | T1565.001, T1070 | forged records without a ledger anchor | 60 | 360 | 189 |
| D8 | Alert storm | T1595, T1046 | fourfold and eightfold surges | 50 | 1200 | 13 |
| | **Total** | | | **900** | **6300** | **615** |

Genuine proposals: 5685 (3757 concern malicious and 1928 benign activity). Adversarial proposals: 217
hallucinated, 198 injected, 200 tampered. Episodes: 517 malicious incidents, 276 benign incidents and 107
attacks on the agent.

### Tables (CSV, UTF-8, `.` decimal separator, empty cell = not applicable / never)

| File | Rows | Key | Content (Table 7 entity) |
|---|---:|---|---|
| `episodes.csv` | 900 | episode_id | episode, scenario, ATT&CK/ATLAS techniques, phase boundaries, label, split |
| `observations.csv` | 5885 | evidence_id | observation: asset, t_obs, t_ingest, sensor, OCSF class, score, raw and record digests, sensor signature, anchor |
| `ledger_anchors.csv` | 5783 | tx_id | ledger anchor: H(e), t_submit, t_final, confirmed-state visibility latency L_c, acceptance at 5 validators, retraction |
| `proposals.csv` | 6300 | proposal_id | agent proposal: α, x, evidence references, claimed ĉ, t_p, redacted rationale, context digest, injection marker, ground truth |
| `policy_snapshots.csv` | 10340 | (partition, version) | policy partition versions, permit/deny, thresholds, Φ_α, D_α |
| `gateway_verdicts.csv` | 6300 | proposal_id | full-contract (EB) verdict: P1–P5, failure sets, g(s), regime, t_chk, t_iss, t_exp, nonce, signed warrant token |
| `executions.csv` | 3486 | proposal_id | execution under EB: enforcement point, mode, t_disp, t_x, t_done, check-to-act window, unsafe, violation, deadline met |
| `analyst_actions.csv` | 638 | proposal_id | escalation under EB: time, urgency, handling time, decision, correctness |
| `policy_outcomes.csv` | 37800 | (proposal_id, policy) | benchmark: outcome of every proposal under AD, CO, RO, GN, EB and ET |

The field dictionary with types and descriptions is in `datapackage.json` (Frictionless Data Package).
Times are seconds since the start of the shift (`shift_id`). Shifts last 8 h, or 4 h in D8.

### Ground truth

Ground truth follows from the scenario design, exactly as for the planned cyber-range dataset. It covers
the proposal kind (genuine, hallucinated, injected, tampered), whether a genuine proposal concerns
malicious activity (`y_malicious`), the time the target state drifts (`t_drift`), the time evidence is
retracted (`ledger_anchors.t_retract`) and the policy timeline (`policy_snapshots`). An execution is
unsafe if the target is benign, adversarially chosen, retracted, forbidden by the current policy or has
drifted at the execution instant.

### Integrity

* `raw_digest`: SHA-256 of the canonical raw event. `record_digest` = H(e) over ⟨raw, asset, t_obs, s, src⟩.
* `sensor_signature`: Ed25519 signature of the sensor over `raw_digest`. Public keys are in `keys.json`.
* Tampered records (`offchain_tampered = True`) carry a forged score, so their `record_digest` never matches
  the digest anchored on the ledger. Some have no anchor at all.
* `warrant_token`: compact Ed25519-signed warrant (Table 3 claims), verifiable with the gateway key in `keys.json`.
* `manifest.json`: SHA-256 of every CSV, their Merkle root and the gateway signature over the root. In a
  deployment this root would be anchored on the ledger.
* Validator outage (D3, every second shift): one validator does not respond (`accept_v*` empty). The read
  quorum of four is then formed by the remaining validators.

## 3. Collection (generation) process

Proposals are generated by `ebaw.sim.generate` with synchronized common random numbers (seed
`20260000 + 1000·k + shift` for scenario Dk). They are replayed under the six policies with `ebaw.sim.run`
and exported by `ebaw.dataset.build`. The scenario perturbations are listed in `manifest.json → catalog`.
Every model assumption is the one stated in Section 4.1 of the article. Generation is deterministic: the
same software produces byte-identical files and the same Merkle root.

## 4. Preprocessing, splits and labeling

Proposals of one shift are grouped into episodes. Malicious incidents, benign incidents and attacks on the
agent form separate streams. Each stream receives a share of the episodes proportional to its size and is
cut into consecutive groups. Splits are made at episode level and in time within each scenario: the first
60% of episodes for fitting the calibration map (`train`), the next 20% for selecting thresholds (`val`) and
the last 20% for testing (`test`). This avoids temporal and episode leakage.

## 5. Uses

* **Intended.** Benchmark tasks T1 (calibration), T2 (thresholds) and T3 (admission policies), implemented
  in `ebaw.benchmark` and the Colab notebook. Other intended uses are development and testing of gateway,
  ledger-adapter and enforcement-point implementations against a fixed schema, teaching, and planning the
  cyber-range experiments (sample sizes, Eq. 22).
* **Not intended.** Training detectors on the scores, which are draws from Beta distributions and not
  features of real telemetry. Estimating the performance of real SOCs or LLM agents. Any claim about real
  attack prevalence.

## 6. Distribution and maintenance

Distributed on Zenodo together with the ebaw-soc 2.0.0 software under CC BY 4.0 (software MIT). It can be
regenerated with `python -m ebaw dataset --out <dir>`. Version 2.0 is planned to replace the simulated
latency, calibration and analyst parameters with values measured on the SOC cyber range of the University
of Customs and Finance (Section 6.3).
