# Contributing

## Before you change a parameter pack

The capability, crosswalk, rule and scenario packs are **versioned artifacts**, not
configuration. A change to any of them alters published results.

1. Bump the pack version constant (`CAPABILITY_PACK_VERSION`, `CROSSWALK_PACK_VERSION`,
   `RULE_PACK_VERSION`, `SCENARIO_PACK_VERSION`, `SCHEMA_VERSION`).
2. Run the full suite, including the reproducibility tests.
3. Record the change and its effect on the reported tables in `CHANGELOG.md`.

Section 6.1 of the article requires dual approval and a regression replay for changes to
critical mappings. A crosswalk edit that is not accompanied by an updated regression
expectation should not be merged.

## Ground rules that are not negotiable

These are correctness properties of the artifact, not style preferences:

- **Do not add a network call.** Local-first processing (R2) is a structural property.
  The package performs no network I/O, and the absence of any such call is part of what
  the privacy argument rests on.
- **Do not reproduce ISO/IEC control text.** Cite identifiers and write your own summary.
  `tests/test_crosswalk.py::test_no_iso_control_text_is_reproduced` enforces this.
- **Do not weaken the metadata allowlist.** A new field needs an entry in `ALLOWLIST`
  with a stated adaptation purpose, and it must survive the prohibited-field tests.
- **Do not let the software approve anything.** Only `Role.APPROVER` may change an
  approved profile. Any code path that bypasses `ProfileLedger.apply` is a defect.
- **Do not overstate a result.** Synthetic output is described as model behaviour. If you
  add an output, add its claims boundary too.

## Running the tests

```bash
python -m pip install -e ".[dev]"
python -m pytest
python -m pytest -m "not slow"
```

The core package must keep working with **zero third-party dependencies**. If you need a
library, make it optional and guard the import, as `figures.py` does.
