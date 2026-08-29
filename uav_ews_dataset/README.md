# uavews - dataset formation and preparation pipeline

Executable implementation of the data model, calculations, and technical
validation described in the Data Descriptor *Building and Validating a
Multisource, Multimodal Spatiotemporal Dataset for Early Warning of Approaching
Small Unmanned Aerial Vehicles*.

The package does three things:

1. **Forms the dataset.** It normalizes four heterogeneous source streams into
   the event-centered tables of the manuscript's Table 3, computes the kinematic
   ground truth of Equations (1) and (2), attaches observations to synchronized
   windows under an uncertainty-expanded overlap rule, and adjudicates labels
   across three evidence tiers.
2. **Validates it.** It computes every dimension of Table 7 - completeness
   (Eq. 4), duplicate rate (Eq. 5), synchronization error (Eq. 3), missingness,
   measured media quality, inter-annotator agreement, cross-modal consistency,
   and checksum integrity - and applies the release gates.
3. **Prepares the field trials that will replace the rehearsal data.** It sizes
   the flight matrix, computes acoustic and visual detection ranges, and turns
   those into an operational warning-time budget.

## Quick start

```bash
pip install -r requirements.txt
python -m uavews.cli all --out build          # from src/ on PYTHONPATH
python -m pytest tests/ -q
```

`all` generates the synthetic rehearsal corpus, runs all ten pipeline stages,
writes the deposit-shaped RO-Crate package, renders every figure, and emits
`build/report/validation_report.json`.

Other commands: `generate` (corpus only), `run` (pipeline only), `figures`,
`plan` (field-trial sizing, needs no data).

## The engineering report

`docs/UAV_EWS_Dataset_Engineering_Report.docx` is the companion document to the
Data Descriptor: it states each calculation, works a numeric example through
from the rehearsal run, shows the sixteen figures, reports the release gates,
and turns the detectability and power calculations into a field-trial plan.

It is generated, not written by hand. Every quantitative statement in it is read
from `build/report/validation_report.json`, so it cannot drift from the run that
produced it:

```bash
npm install                       # docx (one dependency)
python -m uavews.cli all --out build
npm run report                    # -> build/UAV_EWS_Dataset_Engineering_Report.docx
```

## What the numbers are and are not

`uavews.simulate` produces a **synthetic rehearsal corpus**. It exists so that
every stage can be exercised before hardware is deployed, so that the validation
gates have something to fail, and so that the worked examples in the engineering
report are reproducible from a fixed seed.

**No value it produces is a measurement**, and none may be transcribed into the
manuscript's bracketed placeholders. `validation_report.json` carries a
`manuscript_placeholders` map so that filling the paper from a real deposited
release is a lookup rather than a transcription - and it carries a
`PROVENANCE_WARNING` making the distinction explicit.

## Zenodo deposit

`scripts/build_zenodo_package.py` assembles the deposit archive from a pipeline
run: the code, the rehearsal release package, the raw corpus (so every published
digest can be verified against actual bytes), the figures, the validation report,
and the engineering report, plus deposit-level metadata and a top-level integrity
manifest.

```bash
python -m uavews.cli all --out build
npm run report
python scripts/build_zenodo_package.py          # -> dist/uavews-<version>-zenodo.zip
```

The archive deliberately ships with **no licence file and no `license` key** in
`.zenodo.json`: choosing one is the depositing institution's decision, not the
packager's. `DEPOSIT_CHECKLIST.md` inside the archive says so, warns that Zenodo
defaults to CC-BY-4.0 when nothing is chosen, and lists the remaining items —
related identifiers, co-authors, and the separate restricted-access record the
empirical dataset will need.

`upload_type` is `software`, not `dataset`. What is deposited is the pipeline
plus a synthetic rehearsal; filing it as a dataset would present a rehearsal
corpus as measurements.

## Layout

```
config/pipeline.yaml       every release-specific parameter; nothing is hard-coded
config/vocabularies.yaml   controlled vocabularies the validator enforces
src/uavews/
  config, ids, timebase    parameters, keyed identifiers, RFC 3339 <-> int64 ns
  geometry                 Eq. (1) boundary distance, Eq. (2) warning time
  schema                   table declarations, validator, data dictionary
  ingest/                  one adapter per source family S1-S4
  media_qc                 measured audio and visual quality, perceptual hashing
  association              window tiling, Eq. (3), uncertainty-expanded matching
  labeling, agreement      evidence tiers, adjudication, Krippendorff's alpha
  validation               Eq. (4), Eq. (5), gates
  privacy, splits          tiering and k-anonymity; leakage-resistant manifests
  trialdesign              detection ranges, warning budget, sample size
  packaging                RO-Crate, DataCite, PROV-O, SHA-256 manifest
  viz, cli, pipeline       figures, driver, stage orchestration
tests/                     54 tests, aimed at defects that would otherwise be silent
```

## Design notes worth knowing before changing anything

- **Nothing is hard-coded.** Every threshold lives in `config/pipeline.yaml`, so
  a run is reproducible from one artefact and the value in the report cannot
  drift from the value in the paper.
- **`epsilon` has a floor.** The direction dead-band is derived as
  `k * sqrt(2) * sigma_h` and an explicit override below that floor is rejected
  at load time: below it, positional noise becomes a direction label.
- **Equation (3) is measured on synchronization markers**, not against the event
  anchor. Sources that cannot observe a marker report a declared uncertainty and
  a null measurement - never a fabricated one.
- **Duplicates are grouped perceptually**, and degenerate content (silence,
  saturation) is grouped by digest only, because a perceptual hash of silence
  matches all other silence.
- **The SNR estimator declares its own sensitivity floor**, calibrated by a
  Monte-Carlo null, and returns null rather than reporting noise as a weak
  detection.
- **Split constraints are audited, not assumed.** A split bug produces manifests
  that look normal and scores that are merely too good.
