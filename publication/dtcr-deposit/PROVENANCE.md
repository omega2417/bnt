# Provenance of the data in this deposit

**Read this before citing, reusing, or submitting anything from `data/`.**

## 1. Status of the current dataset

Every file under `data/` in this release is **synthetic reference data**, not
measurement. Each row carries the column `data_origin = synthetic_reference`,
each generated file is listed in `data/generation_manifest.json`, and
`analysis/verify_repository.py` refuses to certify the deposit as
submission-ready while that marker is present.

The synthetic dataset was produced by `analysis/simulate_reference_dataset.py`
with the fixed seed `20260731`. It exists for one reason: the manuscript
(version 02) reports only aggregate means, and the run-level observations that
produced them were not preserved. Without run-level data the revised Results
section — confidence intervals, effect sizes, per-run NRI, confusion matrices,
the ablation study — cannot be written, and the analysis code that must produce
it cannot be tested.

The synthetic dataset therefore makes the *pipeline* complete and executable
today, so that the moment real measurement exports exist they can be dropped
into `data/` and the entire Results section regenerates unchanged.

## 2. What the synthetic dataset does and does not guarantee

It **does** guarantee:

* the per-scenario means aggregate exactly to the values printed in the
  manuscript (43.1 → 8.5 s detection, 399 → 122 s recovery, NRI 0.71 → 0.93 for
  S3, 98.7% integrity accuracy, overhead below 6%);
* internal consistency: recovery time and NRI are *measured off* the published
  availability traces by `dtcr.resilience`, not stored independently, so
  Figure 5 and Figure 6 cannot disagree — the objection that motivated this
  deposit is structurally impossible here;
* realistic dispersion, censoring behaviour, and a documented statistical design.

It **does not** guarantee anything about the physical system. No row is an
observation. Dispersion, availability floors, confusion-matrix operating points
and ablation rates are modelling choices, not measurements. Nothing in `data/`
may be reported as an experimental result, quoted in a manuscript as evidence,
or cited as a finding.

## 3. Specific modelling choices that were calibrated to published values

Three choices are calibrations against the manuscript rather than free
parameters, and are called out here so that no reader mistakes them for
findings:

| Quantity | How it was set |
|---|---|
| Per-scenario detection and recovery means | Chosen so the unweighted mean over S1–S4 equals the published aggregate; each arm's sample is then rescaled so the realised sample mean matches exactly. |
| S3 availability floor | Bisected so the mean NRI over the 20 runs equals the published 0.71 (baseline) and 0.93 (framework). Floors for S1, S2 and S4 are priors; their NRI values are outputs, not targets. |
| Integrity confusion matrices | Per-cell error rates scaled by one common factor so the pooled *expected* accuracy is 98.7%; counts are then drawn binomially. The draw seed (`SEED + 164`) is the smallest offset in [1, 400) whose realised pooled accuracy reproduces 98.7% to four decimals. |

Resource measurements are drawn per run and then rescaled so each arm's mean
equals its intended value; without that step the sampling error of 80 runs moves
the realised Eq. (17) overhead by up to two percentage points, which would
silently contradict the published "below 6%" bound.

## 4. Replacing the synthetic data with real measurements

1. Export the real runs into the schema of `DATA_DICTIONARY.md`, keeping the
   column names. Set `data_origin` to a value identifying the measurement
   campaign, for example `testbed_2026-09`.
2. Delete `data/generation_manifest.json` and, if you wish,
   `analysis/simulate_reference_dataset.py` — no other file imports it.
3. Run `make analysis figures verify`. No analysis code needs to change.
4. `analysis/verify_repository.py` will now report `submission-ready: YES` once
   the DOI placeholder is also replaced.
5. Re-check the values in `analysis/verify_repository.py::MANUSCRIPT_CLAIMS`
   against the real data. If the real means differ from the published ones, the
   **manuscript** is what must change, not this file.

## 5. Declaration to reproduce in the manuscript

While `data/` remains synthetic, the Data Availability Statement must not claim
that experimental data are available. Use the wording in
`manuscript_integration/06_declarations.md`, which states plainly that the
deposit currently contains the analysis pipeline and a synthetic reference
dataset, and which is replaced by the full statement once real runs are
deposited.

## 6. Generative AI

The analysis code, the synthetic-data generator, the figures and the manuscript
integration text in this deposit were drafted with AI assistance and reviewed by
the authors, who take full responsibility for them. No experimental observation
in this deposit was produced by an AI tool — because this deposit currently
contains no experimental observations at all. See
`manuscript_integration/06_declarations.md` for the disclosure text.
