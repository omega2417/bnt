# Threat model

Answers review items §3.3 and §10: an explicit per-scenario threat matrix, the
trusted computing base, and the cryptographic detail the integrity claim rests
on.

## 1. Trust boundaries and trusted computing base

**Trusted (assumed not compromised):**

* the verifier's HSM, which holds the audit signing key and seeds the challenge
  RNG;
* the append-only evidence log's anchoring service;
* the hash function and the homomorphic tag scheme;
* the clock-synchronisation source, within the stated tolerance.

**Semi-trusted (may fail, must be detected):** edge nodes, the MQTT broker,
replica hosts, the digital-twin core, the policy engine, the orchestrator.

**Untrusted:** IoT sensors, all network paths, workload images, any cross-domain
peer.

**Explicitly out of scope for this evaluation:** compromise of the digital twin,
the policy engine or the orchestrator itself; a global adversary compromising
every replica and validator simultaneously; supply-chain compromise of the
container images; insider misuse of the verifier's key material. Section 4.3 of
the manuscript states these as limitations rather than as solved problems.

## 2. Per-scenario threat matrix

| | **S1 compromised edge** | **S2 falsified telemetry** | **S3 denial of service** | **S4 malicious migration** |
|---|---|---|---|---|
| **Protected asset** | edge control service on `edge-02` | regional telemetry stream and its replicas | civil-service API on `edge-01` | workload `analytics-core` and its placement |
| **Security property** | authorisation integrity | data integrity + provenance authenticity | availability | placement policy compliance |
| **Entry point** | leaked service-account token | authenticated but compromised sensor + on-path injection | exposed service port | orchestration API |
| **Attacker privilege** | valid token, no host root | sensor identity, on-path position | unauthenticated network | authenticated operator with a lower clearance |
| **Trusted components** | HSM, evidence log | HSM, hash + tag scheme, evidence log | monitoring pipeline | policy engine, label lattice |
| **Attack success criterion** | an unauthorised control command is executed and persists > 30 s | a falsified value is consumed by an analytics decision | availability of the civil-service API below 0.95 for > 60 s | the workload runs on a node whose label or trust does not admit it |
| **Detection signal** | policy violation, trust decay, anomalous control-rate feature | failed hash challenge, provenance mismatch, sequence anomaly | IDS signature + availability decline | admission check on Eq. (13) |
| **Response** | revoke token, isolate identity, restore validated configuration | quarantine records, retrieve validated replica, lower source trust | rate limit, isolate target, migrate dependants, restore | deny placement, revoke credentials, reschedule on an admissible node |
| **Known limitation** | detects use of a stolen token, not its theft | see §4 below: semantic falsification is **not** covered by the hash | rate limiting is reactive; upstream capacity is not modelled | assumes the label lattice and the domain map are correct |

## 3. Integrity and provenance protocol

| Item | Value |
|---|---|
| Block hash | BLAKE2b-256 over 4 KiB blocks |
| Homomorphic tag | multiplicative tag over the prime-order group of Curve25519 |
| Proof format | `(block_index, tag, aggregate_hash, nonce, verifier_signature)` |
| Challenge nonce | 128 bit |
| Challenge RNG | HMAC-DRBG(SHA-256), seeded per audit round from the verifier's HSM |
| Audit cadence | 30 s; `r = 59` blocks per round (see Eq. 5 and `framework_parameters.yaml`) |
| Transport | MQTT over TLS 1.3 with mutual authentication; client certificates per sensor |
| Key provisioning | per-device certificate issued at enrolment, 90-day validity |
| Key rotation | scheduled every 30 days; forced on any trust score below 0.4 |
| Revocation | CRL distributed to brokers and enforced at connect and at re-authentication |
| Timestamp tolerance | ±2 s; records outside it are rejected before the trust update |
| Replay window | 60 s sliding window keyed on `(source_id, sequence)` |
| Provenance binding | each processing stage signs `H(previous_stage_signature ‖ payload_hash)`, so the chain cannot be reordered or truncated undetectably |
| Replica topology | 3 replicas per stream, 2 independent validators, quorum 2-of-3 |
| Evidence log | hash-chained, signed per entry, anchored hourly to an external append-only service |

**Behaviour when a semi-trusted component is compromised.** A compromised twin
yields stale or wrong what-if predictions; the synchronisation gate of Eq. (1)
and the post-action recovery validation bound the damage but do not eliminate
it. A compromised policy engine can admit an inadmissible placement; only the
independent evidence log would reveal it after the fact. A compromised
orchestrator can enforce an unsafe action; the rollback path triggers on failed
recovery validation. None of these three cases is evaluated experimentally, and
the manuscript says so.

## 4. What the integrity layer does **not** prove

This is the sharpest limitation in the paper and it must be stated in the text,
not only here.

A homomorphic hash proves that a block is **unmodified since it was created**.
It proves nothing about whether the value the sensor created was **true**. A
compromised but correctly authenticated sensor that publishes a plausible false
reading produces a perfectly valid proof.

S2 therefore decomposes into four sub-cases with different coverage:

| Sub-case | Covered by | Coverage |
|---|---|---|
| Replay of an earlier valid record | sequence number + replay window | full |
| Injection by an unauthenticated party | mTLS + provenance signature | full |
| Modification in transit or at rest | homomorphic hash challenge | full, up to the sampling probability of Eq. (4) |
| **Semantic falsification by an authenticated compromised sensor** | anomaly detector + cross-sensor redundancy + physical-consistency checks | **partial**; the integrity layer contributes nothing |

The evaluation must report the four sub-cases separately, and the manuscript
must not attribute the aggregate S2 detection result to the integrity layer
alone. `attacks/s2_falsified_telemetry/` implements all four.
