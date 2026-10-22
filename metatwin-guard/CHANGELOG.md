# Changelog

## 1.0.1 — 2026-10-22

Archived on Zenodo: https://doi.org/10.5281/zenodo.23557608 (DOI, title, description and
citation added to README, CITATION.cff, codemeta.json, .zenodo.json and the notebook; no code change).

Fixes from an independent code review; methods and constants are unchanged.

### Fixed
- Colab notebook: an uploaded release zip was put on `sys.path` at the wrong level
  (`ModuleNotFoundError`). Renamed or prefixed zips (`… (1).zip`) are now detected,
  extracted into their own folder, and the setup cell can be re-run safely (it purges
  stale imports and prints which copy is used).
- `metrics.average_precision`: infinite loop or `ZeroDivisionError` on NaN scores and
  `TypeError` on `None`; unscored events now rank last.
- `IntegrityGateway`: an out-of-range integer feature (e.g. `10**400`) raised
  `OverflowError` instead of being rejected as `schema:feature_<name>`.
- `MetaTwinGuard.process`: a non-string `event_id` (NaN, bytes, …) crashed the evidence
  write; non-string identifiers are now recorded as `null`.
- `QuorumEvidenceLedger.verify`: malformed blocks raised instead of being reported;
  `tampered_copy()` shared the append-timing list with the original.
- Telemetry-modification scenario: tampered copies were made from already-admitted
  events, so they were also caught by the id/sequence/chain checks. The adversary now
  modifies a fresh signed event that races ahead of its original, so only the
  payload-hash or Ed25519 signature check can reject it; the original is admitted.
  Results for this scenario changed accordingly (see `results/`).

### Changed
- Ledger verification stops counting signatures once the 3-of-4 quorum is reached;
  strict timestamp parsing uses a regex + `fromisoformat` instead of `strptime`;
  the twin-state hash is computed once per event (48-run benchmark 21.3 s → 17.9 s, ≈16 % faster).
- Notebook embeds a byte-reproducible archive (fixed gzip mtime, file modes).
- 7 regression tests added (27 in total).

## 1.0.0 — 2026-10-22
Initial release.
