# Changelog

All notable changes to this deposit. Each Zenodo version is a separate,
linked record with its own persistent identifier; cite the version you used.

## 2.0.0 — [PUBLICATION DATE]

First public deposit.

### Contents
* Modular reference implementation `umsf_twin` 2.0.0: 66 Python modules,
  standard library only.
* Demonstration inventory, safety policy and DoE factor definitions.
* Five executed SIM scenarios: `baseline-quiet`, `wan-failover`,
  `cyber-campaign`, `power-outage`, `compound-challenge`.
* Three-replicate demonstration run, eight-point exploratory DoE, demonstration
  Monte Carlo with sequential stopping.
* 40 automated software checks; automated comparison against 86 reference values
  of the executable specification.
* Machine-readable run index, per-run manifests, campaign manifest, SHA-256
  checksums, environment record, security and privacy statement.

### Reproduction result recorded in this release
* 40/40 automated checks passed on CPython 3.11.15, Linux x86_64.
* 86/86 reference values of the specification reproduced.
* Engine source hash `2136f8f4be6e300c272a52056e15038260f33d67e0283cadde99939a09b24549`,
  identical to the prior reproduction.

### Packaging changes relative to the upstream reference tree
The reference tree printed in the executable specification places the package at
the repository root and its JSON configuration under `umsf_twin/config/`. In this
deposit the package lives in `src/` and configuration has a single canonical copy
in `configs/` and `scenarios/`, so that no machine-readable input is duplicated.
Two lines of `tests/run_tests.py` were changed accordingly; the exact diff is in
`docs/packaging_patch_tests.diff`. No module under `src/umsf_twin/` was modified,
and `engine_source_hash` is computed over `*.py` only and is therefore unchanged.

### Not included, by design
No measurements of the physical cyber range, no EMU or REPLAY results, no HIL
runs, no primary equipment logs, no credentials, network addresses, host names or
personal data.
