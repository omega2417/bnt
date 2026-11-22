# Changelog

## 2.0.0 (2026-10-08) - ebaw-soc

Extends `ebaw-sim 1.0.0`. The simulation model (`ebaw/model.py`, `ebaw/sim.py`) and the article scripts are
unchanged; they reproduce every number of the article bit for bit (`results/` and `figures/fig1-6`).

Added

- `ebaw/warrant.py`: warrant claims of Table 3, canonical JSON, compact signed tokens (Ed25519 via
  `cryptography`, HMAC-SHA256 fallback), single-use nonce store, Merkle roots.
- `ebaw/ledger.py`: permissioned evidence ledger with masking Byzantine quorum reads (n >= 4f + 1, read quorum
  ceil((n + 2f + 1)/2), f + 1 identical reports) and validator fault models (crash, withhold, fabricate,
  equivocate).
- `ebaw/gateway.py`: deterministic reference gateway core implementing Algorithm 1 (ADMIT, REVALIDATE,
  re-issue) from authenticated inputs only, and an enforcement point (signature, binding, expiry, committed
  verdict, nonce).
- `ebaw/dataset.py`: generator, loader and validator of **EBAW-SOC-Synth 1.0.0**, a synthetic dataset with the
  record schema of Table 7 and the scenario catalog of Table 8 (900 episodes, 6300 proposals, 615 adversarial),
  with digests, sensor signatures, signed warrant tokens, a signed manifest, a Frictionless `datapackage.json`
  and a datasheet.
- `ebaw/benchmark.py`: benchmark tasks T1 calibration, T2 thresholds, T3 admission policies; `ebaw/stats.py`:
  Eq. (22), rule of three, intervals, ECE, Friedman/Nemenyi.
- `ebaw/demo.py` and `python -m ebaw {demo,dataset,validate,benchmark}`.
- `notebooks/EBAW_Colab.ipynb`: self-contained Google Colab notebook that embeds the whole package.
- `tests/`: 48 property tests (Propositions 3 and 4, quorum masking, warrant integrity, calibration,
  determinism, dataset integrity, Eq. 22).
- Figures 7-8 (dataset composition and policy comparison; calibration reliability).

## 1.0.0 (2026-10-08) - ebaw-sim

Simulation package accompanying the article (Supplementary Material S1).
