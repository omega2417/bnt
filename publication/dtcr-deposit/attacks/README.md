# Attack recipes

One directory per scenario. Each contains a `recipe.yaml` giving the exact
parameters a reviewer needs to reproduce the attack, and a `run.sh` reference
driver. **The drivers are for an isolated laboratory only** (see
`../PROTOCOL.md` §7); they have no external connectivity and target only the
lab addresses in `configs/`.

Every recipe fixes the ground-truth `attack_onset`, so detection latency is
measured against the driver's own log and never against a detector.

| Scenario | Mechanism | Ground-truth onset source |
|---|---|---|
| S1 | compromised edge identity issuing control commands | driver timestamps the first injected command |
| S2 | falsified telemetry (four sub-cases, see THREAT_MODEL §4) | driver timestamps the first tampered publish |
| S3 | TCP SYN flood denial of service | driver timestamps the first flood packet |
| S4 | unauthorised cross-domain workload migration | driver timestamps the placement request |
