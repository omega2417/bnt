#!/usr/bin/env python3
"""Assemble the Zenodo deposit archive.

Run after ``python -m uavews.cli all --out build`` and ``npm run report``. The
script copies the code, the rehearsal release package, the raw corpus, the
figures, and the engineering report into one tree, writes the deposit-level
metadata, digests every file, and zips the result.

    python scripts/build_zenodo_package.py [--out dist]

Two rules govern what the script writes.

* It never invents an institutional value. The deposit ships with no licence
  file and no licence key in ``.zenodo.json``, because choosing a licence is the
  depositor's decision and not the packager's. DEPOSIT_CHECKLIST.md says so, and
  warns that Zenodo silently defaults to CC-BY-4.0 when no choice is made.
* It records what it packaged. ``checksums_sha256.txt`` covers every file in the
  archive, so a reviewer can verify the deposit end to end - including verifying
  the media digests inside ``dataset/tables/media_manifest.parquet`` against the
  actual bytes in ``corpus/``.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import sys
import zipfile
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

TITLE = ("uavews: dataset formation, validation and field-trial preparation "
         "pipeline for a multisource multimodal sUAV early-warning dataset")

CREATORS = [{
    "name": "Prokopovych-Tkachenko, Dmytro",
    "affiliation": ("Department of Cybersecurity and Information Technologies, "
                    "University of Customs and Finance, Dnipro, Ukraine"),
    "orcid": "0000-0002-6590-3898",
}]

KEYWORDS = [
    "small unmanned aerial vehicle", "multimodal dataset", "early warning",
    "spatiotemporal data", "acoustic sensing", "visual sensing",
    "data provenance", "technical validation", "FAIR data", "RO-Crate",
    "leakage-resistant evaluation", "field trial design",
]


def sha256_file(path: Path, chunk: int = 1 << 20) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for block in iter(lambda: fh.read(chunk), b""):
            h.update(block)
    return h.hexdigest()


def copy_tree(src: Path, dst: Path, skip=("__pycache__", ".pytest_cache")) -> int:
    n = 0
    for p in sorted(src.rglob("*")):
        if not p.is_file() or any(s in p.parts for s in skip) or p.suffix == ".pyc":
            continue
        target = dst / p.relative_to(src)
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(p, target)
        n += 1
    return n


# --------------------------------------------------------------------------- #
# Deposit-level metadata
# --------------------------------------------------------------------------- #
def zenodo_json(version: str, metrics: dict, coverage: dict) -> dict:
    """Zenodo deposit metadata.

    ``upload_type`` is *software*, not *dataset*, and the distinction is
    deliberate. What is deposited here is the versioned pipeline the manuscript's
    Table 3 requires under ``code/``, together with a synthetic rehearsal release
    that demonstrates it. The empirical dataset does not exist yet. Labelling
    this record a dataset would misrepresent a rehearsal corpus as measurements,
    which is exactly the confusion the whole package is built to prevent.

    No ``license`` key is emitted. Zenodo defaults to CC-BY-4.0 when none is
    supplied, so the checklist tells the depositor to choose actively.
    """
    return {
        "upload_type": "software",
        "title": TITLE,
        "creators": CREATORS,
        "description": (
            "<p><strong>What this is.</strong> An executable implementation of the "
            "data model, the five equations, the technical-validation framework and "
            "the tiered-release policy set out in the Data Descriptor "
            "<em>Building and Validating a Multisource, Multimodal Spatiotemporal "
            "Dataset for Early Warning of Approaching Small Unmanned Aerial "
            "Vehicles</em>. The pipeline normalizes four heterogeneous source "
            "streams into an event-centered model, computes kinematic ground truth, "
            "associates observations with synchronized windows under an "
            "uncertainty-expanded overlap rule, adjudicates labels across three "
            "evidence tiers, validates the result against configured release gates, "
            "builds leakage-resistant evaluation manifests, and emits an RO-Crate "
            "package with DataCite and PROV-O metadata and a SHA-256 integrity "
            "manifest. It also sizes the field trials that are to replace the "
            "rehearsal corpus with measurements.</p>"
            "<p><strong>What the numbers are not.</strong> The release package and "
            "the validation report in this record are computed from a "
            "<em>synthetic rehearsal corpus</em> generated with a fixed seed. They "
            "exist to demonstrate that the computations are correct, that the "
            "release gates fire on defects, and that the whole chain is reproducible "
            "before any hardware is deployed. <em>No value in this record is a "
            "measurement</em>, and none may be transcribed into the manuscript's "
            "bracketed placeholders. The empirical dataset will be deposited as a "
            "separate Zenodo record and linked to this one.</p>"
            f"<p><strong>Contents.</strong> Rehearsal release: {metrics['n_events']} "
            f"events, {metrics['n_observations']} observations, "
            f"{metrics['n_media_objects']} media objects, "
            f"{metrics['n_labels_released']} released labels, covering "
            f"{coverage['collection_start_utc'][:10]} to "
            f"{coverage['collection_end_utc'][:10]}. Source code (18 modules, 54 "
            "tests), the raw synthetic corpus so that every published digest can be "
            "verified against actual bytes, 16 figures, a machine-readable "
            "validation report, and a 12-section engineering report in DOCX "
            "describing every calculation with a worked numeric example.</p>"
            "<p><strong>Reproducing.</strong> "
            "<code>pip install -r code/requirements.txt</code> then "
            "<code>PYTHONPATH=code/src python -m uavews.cli all --out build</code>. "
            "Canonical tables and split manifests reproduce byte-for-byte; only the "
            "three files carrying wall-clock timestamps differ between runs.</p>"
        ),
        "keywords": KEYWORDS,
        "access_right": "open",
        "version": version,
        "language": "eng",
        "related_identifiers": [],
        "notes": (
            "LICENCE NOT SET BY THE PACKAGER. This archive deliberately ships with "
            "no licence file and no licence key in .zenodo.json, because the choice "
            "belongs to the depositing institution. Zenodo defaults to CC-BY-4.0 "
            "when no licence is selected, so the licence must be chosen actively in "
            "the deposit form before publishing. See DEPOSIT_CHECKLIST.md, which "
            "also lists the related identifiers to add once the manuscript and the "
            "empirical dataset have identifiers of their own."
        ),
    }


def dataset_record_template() -> dict:
    """Metadata skeleton for the future empirical-dataset record.

    Supplied so that the eventual dataset deposit is linked to this software
    record from the start rather than retrofitted, and so that the fields the
    Data Descriptor requires are visible now, while the collection protocol can
    still be changed to produce them.
    """
    return {
        "_README": (
            "TEMPLATE for the SEPARATE Zenodo record holding the empirical "
            "dataset. Do not upload this file as metadata for the software "
            "record. Every value in angle brackets must come from the deposited "
            "release - most of them from report/validation_report.json - and "
            "none may be copied from the rehearsal figures in this archive."
        ),
        "upload_type": "dataset",
        "title": "<DATASET_TITLE>",
        "creators": CREATORS,
        "description": "<abstract of the deposited release>",
        "keywords": KEYWORDS,
        "access_right": "<open for the sanitized tier; restricted for the controlled tier>",
        "version": "<DATASET_VERSION>",
        "language": "eng",
        "dates": [{"type": "Collected",
                   "start": "<COLLECTION_START>", "end": "<COLLECTION_END>"}],
        "related_identifiers": [
            {"identifier": "<software record DOI, i.e. this deposit>",
             "relation": "isCompiledBy", "resource_type": "software"},
            {"identifier": "<manuscript DOI once published>",
             "relation": "isSupplementTo", "resource_type": "publication-article"},
        ],
        "notes": (
            "Two access tiers. The open tier holds sanitized media or "
            "privacy-preserving derived representations, generalized "
            "spatiotemporal metadata, released labels, documentation, code and "
            "integrity manifests. The controlled tier holds higher-resolution "
            "time and location data and raw audiovisual objects, and requires an "
            "approved research purpose, a data-use agreement, security controls, "
            "a non-reidentification commitment, and a defined deletion date. "
            "Zenodo supports restricted access with manual approval; the "
            "controlled tier must not be uploaded as an open record."
        ),
    }


def citation_cff(version: str) -> str:
    """CITATION.cff, with no licence key for the same reason as .zenodo.json."""
    c = CREATORS[0]
    family, given = [s.strip() for s in c["name"].split(",", 1)]
    return f"""cff-version: 1.2.0
message: "If you use this software, please cite it as below."
type: software
title: "{TITLE}"
version: "{version}"
date-released: "{date.today().isoformat()}"
authors:
  - family-names: "{family}"
    given-names: "{given}"
    orcid: "https://orcid.org/{c['orcid']}"
    affiliation: "{c['affiliation']}"
keywords:
{chr(10).join('  - "' + k + '"' for k in KEYWORDS)}
abstract: >-
  Executable implementation of the data model, calculations and technical
  validation of a Data Descriptor for a multisource, multimodal spatiotemporal
  dataset for early warning of approaching small unmanned aerial vehicles. The
  archive additionally contains a synthetic rehearsal release, generated with a
  fixed seed, that exercises every pipeline stage and every release gate. No
  value in the rehearsal release is a measurement.
# license: deliberately unset - see DEPOSIT_CHECKLIST.md
# doi: add once Zenodo has minted it, then re-upload this file
"""


def deposit_readme(version: str, report: dict, counts: dict) -> str:
    m, cov, plan = report["metrics"], report["coverage"], report["campaign_plan"]
    gates = report["gates"]
    n_pass = sum(1 for g in gates if g["status"] == "pass")
    fails = [g["gate"] for g in gates if g["status"] == "FAIL"]
    return f"""# uavews {version} - Zenodo deposit

Executable implementation of the data model, the five equations, the technical
validation and the tiered-release policy of the Data Descriptor *Building and
Validating a Multisource, Multimodal Spatiotemporal Dataset for Early Warning of
Approaching Small Unmanned Aerial Vehicles*, together with a synthetic rehearsal
release that exercises the whole chain.

## Read this first

This record is **software plus a rehearsal**, not a measurement campaign.

Everything under `dataset/`, `corpus/`, `figures/` and `report/` is computed from
a synthetic corpus generated by `uavews.simulate` with a fixed seed. It exists so
that every pipeline stage can be exercised, so that the release gates have
something to fail, and so that the worked examples in the engineering report are
reproducible - all before any hardware is deployed.

**No value in this record is a measurement.** None of it may be transcribed into
the manuscript's bracketed placeholders. `report/validation_report.json` carries
a `manuscript_placeholders` map so that filling the paper from a real deposited
release is a lookup rather than a transcription, and a `PROVENANCE_WARNING`
making the distinction explicit. The empirical dataset will be a separate Zenodo
record; `metadata/zenodo-dataset-record-template.json` is its metadata skeleton.

## Contents

| Path | What it is |
|---|---|
| `code/` | The `uavews` package: 18 modules, 54 tests, configuration, and the report generator |
| `dataset/` | The deposit-shaped RO-Crate package produced by the release stage: canonical tables, split manifests, data dictionary, DataCite and PROV-O metadata, integrity manifest |
| `corpus/` | The raw synthetic corpus the pipeline ingested, including real media bytes, so every digest in `dataset/tables/media_manifest.parquet` can be verified against actual files |
| `report/` | `validation_report.json` - every computed metric, and the manuscript placeholder map |
| `figures/` | The 16 report figures as PNG |
| `docs/` | The engineering report (DOCX): 12 sections, 2 appendices, 16 figures, 18 tables |
| `metadata/` | Zenodo metadata for this record and the template for the future dataset record |
| `checksums_sha256.txt` | Digest of every file in this archive |

## The rehearsal release at a glance

| Quantity | Value |
|---|---|
| Events | {m['n_events']} ({cov['event_kind_counts'].get('controlled_flight', 0)} controlled, {cov['event_kind_counts'].get('verified_observation', 0)} verified, {cov['event_kind_counts'].get('weak_observation', 0)} weak, {cov['event_kind_counts'].get('negative_control', 0)} negative control) |
| Observations | {m['n_observations']} |
| Media objects | {m['n_media_objects']} ({m['n_visual_objects']} visual, {m['audio_hours']:.3f} h audio) |
| Released labels | {m['n_labels_released']} |
| Coverage | {cov['collection_start_utc'][:10]} to {cov['collection_end_utc'][:10]}, {cov['n_generalized_locations']} generalized locations |
| Release gates | {n_pass} of {len(gates)} pass |
| Failing gates | {', '.join(fails) if fails else 'none'} |

The failing gates are properties of the rehearsal corpus rather than defects in
the computation, and each demonstrates the corresponding gate doing its job.
Section 8.1 of the engineering report discusses each one, and is generated from
the gate results so it cannot disagree with the table above.

## Reproducing

```bash
pip install -r code/requirements.txt
PYTHONPATH=code/src python -m pytest code/tests -q
PYTHONPATH=code/src python -m uavews.cli all --out build
```

From an empty directory this regenerates the corpus, runs all ten pipeline
stages, writes the release package, renders the figures and emits the validation
report. Canonical tables and split manifests reproduce byte-for-byte; three files
differ between runs because they legitimately carry wall-clock timestamps - the
RO-Crate manifest, the provenance log, and the checksum manifest that digests
them.

To rebuild the engineering report from a run:

```bash
cd code && npm install && npm run report
```

## Verifying this archive

```bash
sha256sum -c checksums_sha256.txt
```

To verify the media digests published inside the release package against the
actual bytes in `corpus/`:

```bash
PYTHONPATH=code/src python - <<'EOF'
import pandas as pd, hashlib, pathlib
m = pd.read_parquet('dataset/tables/media_manifest.parquet')
bad = [r.object_uri for r in m.itertuples()
       if hashlib.sha256(pathlib.Path('corpus', r.object_uri).read_bytes()).hexdigest() != r.sha256]
print('mismatched:', bad or 'none')
EOF
```

## Field-trial planning

Section 9 of the engineering report is forward-looking design computed from the
planning assumptions in `code/config/pipeline.yaml`. Under those assumptions the
campaign requires {plan['n_per_cell_planned']} sorties per cell after a
{plan['expected_run_loss_rate']:.0%} loss allowance, which is
{plan['full_factorial_sorties']:,} sorties as a full factorial over
{plan['full_factorial_cells']:,} cells, or {plan['reduced_sorties']:,} under a
blocked design. Section 9.5 lists which measurement replaces which assumption
during the first calibration campaign.

## Before publishing this record

See `DEPOSIT_CHECKLIST.md`. In particular, a licence has deliberately **not**
been chosen for you, and Zenodo defaults to CC-BY-4.0 if you do not choose one.
"""


def deposit_checklist(version: str, report: dict) -> str:
    dc = report.get("_datacite_requires_completion", ["doi", "open_tier_license"])
    return f"""# Deposit checklist

Complete every item before publishing. Items marked **blocking** will produce a
misleading record if skipped.

## 1. Licence - blocking

This archive ships with **no licence file** and **no `license` key** in
`metadata/.zenodo.json`. That is deliberate: the choice belongs to the
depositing institution, and a packager who supplies one has made an
institutional decision on your behalf.

**Zenodo defaults to CC-BY-4.0 when no licence is selected.** You must choose
actively in the deposit form.

| Candidate | Implication |
|---|---|
| MIT / BSD-3-Clause | Permissive; anyone may reuse the pipeline including commercially. Usual choice for research software intended to be adopted. |
| Apache-2.0 | Permissive, with an explicit patent grant. Preferable where the institution holds or may seek patents touching the detection chain. |
| GPL-3.0 | Copyleft; derivatives must be released under the same terms. Restricts uptake by closed systems. |
| CC-BY-4.0 | Intended for data and documents, not software. Appropriate for the future *dataset* record; a poor fit for `code/`. |

Because this record mixes code with documents, state the split explicitly in the
Zenodo description if the institution wants different terms for each - for
example a software licence for `code/` and CC-BY-4.0 for `docs/` and `figures/`.

Once chosen, add the SPDX identifier to `metadata/.zenodo.json`, uncomment the
`license:` line in `CITATION.cff`, and add a `LICENSE` file at the archive root.

## 2. Related identifiers - blocking once they exist

`related_identifiers` in `metadata/.zenodo.json` is deliberately empty; no
identifier has been invented. Add, as each becomes available:

| Relation | Target |
|---|---|
| `isSupplementTo` | The manuscript DOI, once the Data Descriptor is published or preprinted |
| `isSourceOf` | The empirical dataset record, once deposited |
| `isSupplementedBy` | The source-code repository, if it is public |

## 3. Affiliation and author list

Verify the creator block in `metadata/.zenodo.json` and `CITATION.cff`. It
currently names one author with the affiliation and ORCID given in the
manuscript. Add co-authors and funder acknowledgements before publishing;
Zenodo's `grants` field takes funder award identifiers.

## 4. The empirical dataset is a separate record

Do not add real collected data to this record. Create a new deposit using
`metadata/zenodo-dataset-record-template.json`, and link the two through the
`related_identifiers` of both. Reasons:

- this record is `upload_type: software`, and a dataset filed under it will not
  be discoverable as data;
- the software will be versioned on a different cadence than the data;
- the controlled-access tier cannot share a record with an open one.

## 5. Controlled tier - blocking

Nothing in this archive is controlled-tier material; the rehearsal corpus is
synthetic throughout. When the empirical dataset is deposited, the controlled
tier must be a **restricted-access** record with manual approval, never an open
one. The required conditions are stated in Section 2.5 of the manuscript:
approved research purpose, institutional identity, data-use agreement, security
controls, non-reidentification commitment, disclosure-limited publication review,
and a defined deletion date.

## 6. Outstanding items the pipeline could not fill

`dataset/metadata/datacite.json` carries a `requires_completion` list. On this
build it contains: {', '.join(dc)}. These need institutional or instrument
information and no plausible value has been substituted for any of them. The
same applies to the manuscript placeholders that are not in
`report/validation_report.json`: the authorization and operating procedure, the
ground-truth system and its rate, the camera and microphone models, the final
platform taxonomy, the signing and preservation method, and the ethics approval.

## 7. Two open findings carried from the rehearsal

Both are decisions, not bugs. Section 10.1 of the engineering report states them
in full.

1. **Residual disclosure risk.** {report['k_anonymity']['rate_below_k']:.0%} of
   records sit in an equivalence class smaller than k = {report['k_anonymity']['k']},
   the smallest having {report['k_anonymity']['min_class_size']} member. A 1 km
   spatial cell with day-level time granularity is not sufficient generalization.
   Coarsen the time, the cell, or move the sparse strata to the controlled tier,
   then re-run the probe and record the result in the release metadata.
2. **Low-visibility coverage.** Under the declared planning assumptions the
   acoustic channel yields no actionable lead time in high-ambient-noise
   environments, leaving the system dependent on an unobstructed optical line of
   sight. Decide before site selection whether that weather envelope is accepted
   and documented as a stated limitation, or whether a channel that survives low
   visibility must be added.

## 8. Final verification

```bash
sha256sum -c checksums_sha256.txt
PYTHONPATH=code/src python -m pytest code/tests -q
```

Both must pass on the extracted archive before the record is published.
"""


def changelog(version: str) -> str:
    return f"""# Changelog

## {version} - {date.today().isoformat()}

First deposit. Software plus a synthetic rehearsal release; no empirical data.

### Implemented

- Event-centered data model over six canonical tables, with a schema declaration
  that drives the structural validator, the exported data dictionary, and the
  required-field set of Equation (4) from one source.
- Equation (1) boundary distance to a generalized warning-zone polygon, measured
  to edges rather than vertices, horizontal components only.
- Direction rule with a dead-band derived as k*sqrt(2)*sigma_h and enforced as a
  floor: an explicitly configured epsilon below it is rejected at load time.
- Equation (2) warning time with an interpolated crossing and explicit censoring
  where no crossing is verified.
- Equation (3) synchronization error measured on per-run synchronization markers.
  Sources that cannot observe a marker report a declared uncertainty and a null
  measurement.
- Uncertainty-expanded association with a dual overlap criterion, absolute or
  fractional, plus per-observation decisiveness diagnostics.
- Equation (4) completeness against the declared required-field set, and
  Equation (5) duplicate rate at object-group level, separating exact from
  near-duplicate.
- Measured media quality: a harmonic-sum SNR estimator referred to total in-band
  noise, with a Monte-Carlo null and an explicit not-measurable state; visual
  blur, exposure and apparent target extent; DCT perceptual hashing for
  near-duplicate grouping.
- Evidence-tiered labelling with an authoritative-field set, weighted-majority
  adjudication, unresolved ties left uncertain, and a retained audit trail.
- Krippendorff's alpha with bootstrap intervals resampled over units.
- Access tiering, a k-anonymity probe over the published quasi-identifiers, and
  an independent open-export audit.
- Five leakage-resistant evaluation manifests with per-constraint audits and
  explicit resolution of duplicate-versus-grouping conflicts.
- RO-Crate, DataCite and PROV-O packaging with a SHA-256 integrity manifest.
- Field-trial design: acoustic and visual detection ranges, warning-time budget,
  one-proportion sample sizing with loss inflation, and flight-matrix planning.
- 54 tests, aimed at defects that produce plausible output rather than errors.
- Generated engineering report in DOCX, built from the validation report so the
  document cannot drift from the run.

### Known limitations of the rehearsal corpus

- Three release gates fail: near-duplicate rate (injected by design), cross-modal
  consistency (marginal), and inter-annotator alpha (a property of the simulated
  annotators). Each demonstrates its gate working.
- The location and time holdouts produce an empty validation partition, because
  the corpus has only three site groups and three temporal blocks. This sets a
  floor on the number of independent monitoring sites the field campaign must
  instrument.
"""


# --------------------------------------------------------------------------- #
def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--build", default="build", help="pipeline output directory")
    ap.add_argument("--out", default="dist", help="where to write the archive")
    ap.add_argument("--include-corpus", default=True, action="store_true")
    args = ap.parse_args()

    build = ROOT / args.build
    report_path = build / "report" / "validation_report.json"
    if not report_path.exists():
        print("run 'python -m uavews.cli all --out build' first", file=sys.stderr)
        return 1
    report = json.loads(report_path.read_text(encoding="utf-8"))
    version = report["dataset_version"]

    docx = ROOT / "docs" / "UAV_EWS_Dataset_Engineering_Report.docx"
    if not docx.exists():
        print("run 'npm run report' first", file=sys.stderr)
        return 1

    stage_root = ROOT / args.out / f"uavews-{version}"
    if stage_root.exists():
        shutil.rmtree(stage_root)
    stage_root.mkdir(parents=True)

    counts = {}
    counts["code"] = sum(
        copy_tree(ROOT / sub, stage_root / "code" / sub)
        for sub in ("src", "tests", "config", "scripts"))
    for f in ("requirements.txt", "package.json", "README.md"):
        shutil.copy2(ROOT / f, stage_root / "code" / f)
        counts["code"] += 1

    counts["dataset"] = copy_tree(build / "package", stage_root / "dataset")
    counts["figures"] = copy_tree(build / "figures", stage_root / "figures")
    (stage_root / "report").mkdir(parents=True, exist_ok=True)
    shutil.copy2(report_path, stage_root / "report" / "validation_report.json")
    counts["report"] = 1
    (stage_root / "docs").mkdir(parents=True, exist_ok=True)
    shutil.copy2(docx, stage_root / "docs" / docx.name)
    counts["docs"] = 1
    if args.include_corpus:
        counts["corpus"] = copy_tree(build / "raw", stage_root / "corpus")

    meta = stage_root / "metadata"
    meta.mkdir(parents=True, exist_ok=True)
    (meta / ".zenodo.json").write_text(
        json.dumps(zenodo_json(version, report["metrics"], report["coverage"]),
                   indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    (meta / "zenodo-dataset-record-template.json").write_text(
        json.dumps(dataset_record_template(), indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8")
    # Zenodo reads .zenodo.json from the archive root when one is present.
    shutil.copy2(meta / ".zenodo.json", stage_root / ".zenodo.json")

    (stage_root / "CITATION.cff").write_text(citation_cff(version), encoding="utf-8")
    (stage_root / "README.md").write_text(
        deposit_readme(version, report, counts), encoding="utf-8")
    (stage_root / "DEPOSIT_CHECKLIST.md").write_text(
        deposit_checklist(version, report), encoding="utf-8")
    (stage_root / "CHANGELOG.md").write_text(changelog(version), encoding="utf-8")

    # Integrity manifest last, so it covers the metadata files too.
    lines, total = [], 0
    for p in sorted(stage_root.rglob("*")):
        if p.is_file() and p.name != "checksums_sha256.txt":
            rel = p.relative_to(stage_root).as_posix()
            lines.append(f"{sha256_file(p)}  {rel}")
            total += p.stat().st_size
    (stage_root / "checksums_sha256.txt").write_text("\n".join(lines) + "\n",
                                                     encoding="utf-8")

    archive = ROOT / args.out / f"uavews-{version}-zenodo.zip"
    if archive.exists():
        archive.unlink()
    with zipfile.ZipFile(archive, "w", zipfile.ZIP_DEFLATED, compresslevel=6) as z:
        for p in sorted(stage_root.rglob("*")):
            if p.is_file():
                z.write(p, Path(f"uavews-{version}") / p.relative_to(stage_root))

    print(f"staged   {stage_root}")
    print(f"files    {len(lines) + 1}  ({total / 1e6:.1f} MB uncompressed)")
    for k, v in counts.items():
        print(f"  {k:<9} {v}")
    print(f"archive  {archive}  ({archive.stat().st_size / 1e6:.1f} MB)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
