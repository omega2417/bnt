# Research-integrity statement for this deposit

## What was actually done to produce release 2.0.0

1. The modular reference implementation, its configurations, scenarios and test
   suite were extracted from the executable specification
   `UMSF_CyberRange_Digital_Twin_Modules_UA.md` into a real file tree: 66 Python
   modules, 3 configuration files, 5 scenarios, 1 test module.
2. The package was executed in a clean computational environment (CPython
   3.11.15, Linux x86_64, no third-party packages, no network access).
3. The following were run and their raw outputs stored, unedited, in `results/`:
   the 40-check test suite, inventory validation, the determinism check, the
   three-replicate demonstration run, the five scenarios, the eight-point DoE and
   the Monte Carlo campaign.
4. Each produced value was compared automatically against the reference values
   printed in the specification (`scripts/check_reference_values.py`).
5. Manifests and SHA-256 checksums were generated last, over the final files.

## What is claimed

* The specification is executable, and the implementation extracted from it
  reproduces the specification's own reference values: **40/40** automated checks
  and **86/86** enumerated reference values.
* Runs are deterministic for a fixed `(seed, replicate_id)` and genuinely
  separated across replicates.
* Every result is traceable from parameter to run to artifact to metric.

## What is not claimed

* No calibration against real telemetry was performed.
* No validation against the physical cyber range was performed.
* No physical, EMU, REPLAY or HIL run exists in this deposit.
* The reproduction was performed by the same workflow that produced the
  specification, so it is **re-execution in a separate clean environment**, not
  *independent* third-party reproduction.

## Disclosed discrepancies

* The specification prints a truncated engine source hash `925c24c6…`. The tree
  extracted from that specification hashes to `2136f8f4…4549`, matching the prior
  reproduction. The cause is byte-level (trailing newlines when code is lifted out
  of Markdown). The trees are not claimed to be byte-identical.
* Two lines of `tests/run_tests.py` were changed for this deposit's directory
  layout; the diff is in `docs/packaging_patch_tests.diff`. No module under
  `src/umsf_twin/` was modified.
* The source report for this package stated 62 behavioural reference values. This
  package enumerates 86 checks from the same appendix. The number differs because
  the enumeration differs, not because more values were reproduced than existed;
  the enumeration is fully visible in `scripts/check_reference_values.py`.
* `results/doe/` adds 8 further runs (14,442 rows) beyond the 13,049 rows of the
  scenario and demonstration runs. Row totals are reported separately in
  `manifests/campaign_manifest.json` so that neither figure is inflated by the
  other.

## Identifiers recorded in this release

* Archive DOI: 10.5281/zenodo.22287426 — supplied by the depositor and written into README.md,
  CITATION.cff, CHANGELOG.md, the experiment report and zenodo_metadata.json.
  It was **not verified against the live Zenodo record**, because the packaging
  environment had no network access to zenodo.org. Whether it is the version DOI
  or the concept DOI must be confirmed on the record page.
* Publication date 2026-09-03 is the date the DOI was supplied, not a value read
  from the record. Confirm it against the record page.
* Source repository: https://github.com/omega2417/bnt/tree/claude/zenodo-software-deposit-hdxmbh/zenodo-deposit/umsf-cyberrange-digital-twin-sim-reproducibility-package-v2.0.0

## Fields still left for the author to complete

The final list of co-authors and their contributions, the funding statement, the
journal, and the article DOI remain marked `[IN BRACKETS]` throughout the
package. They are deliberately unfilled: they are facts that only the
corresponding author can supply, and inventing them would defeat the purpose of
this deposit.
