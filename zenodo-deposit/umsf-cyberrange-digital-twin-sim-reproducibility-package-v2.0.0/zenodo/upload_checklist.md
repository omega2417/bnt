# Zenodo upload checklist — release 2.0.0

**Record published:** <https://doi.org/10.5281/zenodo.22287426>
**Source repository:** <https://github.com/omega2417/bnt/tree/claude/zenodo-software-deposit-hdxmbh/zenodo-deposit/umsf-cyberrange-digital-twin-sim-reproducibility-package-v2.0.0>

Work top to bottom. Publish only when every applicable line is genuinely true.
Ticks below are the state of the package as delivered; the unticked lines are
the ones only the corresponding author can close.

## A. Reproducibility — verified in this package

- [x] The ZIP unpacks into a clean directory and no shipped file contains an
      absolute local path.
- [x] The commands named in `README.md` match the `Makefile` targets and the CLI.
- [x] 40/40 automated checks pass on CPython 3.11.15, Linux x86_64
      (`results/verification/tests.txt`).
- [x] Behavioural reference values, row counts and configuration hashes were
      re-checked: 86/86 (`results/verification/reference_check.json`).
- [x] The full `engine_source_hash` is recorded, and its difference from the
      hash printed in the specification is explained rather than hidden
      (`README.md` §6).
- [x] Every result is traceable to `run_id`, `scenario_id`, `replicate_id`,
      `seed` and `config_hash` (`results/run_index.csv`).
- [x] `SHA256SUMS.txt` was generated after the last file change and verifies
      with `sha256sum -c SHA256SUMS.txt`.
- [x] DOI inserted into README.md, CITATION.cff, CHANGELOG.md, the experiment
      report and zenodo_metadata.json; manifests and checksums regenerated;
      archive rebuilt.
- [ ] Confirm on the record page which DOI is the **version** DOI and which is
      the **concept** DOI, and cite the version DOI in the article.
- [ ] Confirm the record's publication date matches the `2026-09-03` recorded in
      CITATION.cff and CHANGELOG.md.
- [ ] If the record was published with an earlier build of the ZIP, upload this
      rebuilt archive as a **New version** — published files cannot be replaced
      in place.

## B. Research integrity — verified in this package

- [x] SIM and *synthetic* appear in the title, description, README, report and
      the manuscript snippets.
- [x] No synthetic value is described as a physical measurement or real telemetry.
- [x] Verification, calibration and physical validation are separated explicitly.
- [x] Precision/recall and intervals are labelled as properties of the model's
      own scenario-ground-truth loop.
- [x] The eight-point DoE is presented as exploratory, never as a global or
      confirmatory sensitivity analysis.
- [x] 13,049 time-series rows are never presented as 13,049 independent
      observations; the unit of analysis is the run/replicate.
- [x] The four UNKNOWN parameters and the known limitations remain visible.

Wording that must not reappear anywhere in the record or the manuscript:

| Do not write | Write instead |
|---|---|
| "independently reproduced" (when the same team repeated it) | "re-executed in a separate clean computational environment" |
| "real gaps" | "deliberately injected synthetic gaps" |
| "dominant factor" (from 8 DoE points) | "the clearest descriptive dependency within a limited demonstration design" |
| "N = 13,049 independent observations" | "13,049 dependent time-series records across scenario and demonstration SIM runs" |
| "proven field accuracy" | "internal model metric of the scenario-ground-truth loop" |
| "the digital twin of the physical range was validated" | "the software digital-twin prototype was verified against its specification" |

## C. Security, privacy and rights

- [x] No credentials, tokens, private keys, VPN configuration, passwords,
      cookies, CI/CD secrets or access logs (`SECURITY_AND_PRIVACY.md`).
- [x] No IP addresses, domain names, MAC addresses, serial numbers, internal
      node names or sensitive topology fragments.
- [x] No personal data or third-party data.
- [x] No exploit code, live targets or instructions beyond feature-level
      modelling.
- [x] Licences cover code, synthetic data and text separately, and the README
      grants nothing broader (`LICENSES/README.md`).
- [ ] All authors have agreed to publication of code, data and documentation.
- [ ] Institutional and funder rights were checked and permit these licences.

Repeat the scan yourself on the unpacked archive:

```sh
grep -rEo '\b(25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)(\.(25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)){3}\b' . | sort -u
grep -rEo '\b([0-9A-Fa-f]{2}:){5}[0-9A-Fa-f]{2}\b' . | sort -u
grep -rEin 'password|secret|api[_-]?key|token|private[_-]?key|BEGIN [A-Z ]*PRIVATE' .
grep -rEo '[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}' . | sort -u
```

## D. Stop criterion

If the actual ZIP were to lack code, configurations, record/run-level results,
manifests or reproduction commands, it must not be described as a
reproducibility package: the record would have to be titled a methodological or
technical report, with no data or code availability claim. This package contains
all five, so the reproducibility-package description is warranted.

## E. Record creation, in order

1. Sign in to Zenodo, choose **New upload**. Rehearse on sandbox.zenodo.org first
   if you want a dry run.
2. Upload `umsf-cyberrange-digital-twin-sim-reproducibility-package-v2.0.0.zip`,
   and optionally a PDF of the report. Do not upload editorial drafts, letters to
   editors or documents with unfilled conditional blocks.
3. Existing DOI? Answer **No**, press **Get a DOI now!**, copy the reserved DOI.
4. Paste the reserved DOI into `README.md`, `CITATION.cff`, `CHANGELOG.md` and
   `zenodo/zenodo_metadata.json`; run `make manifests`; rebuild the ZIP with
   `scripts/build_package.sh`; replace the file in the draft.
5. Fill resource type, titles, publication date, creators with ORCID, both
   descriptions, keywords, licences, funding and related identifiers from
   `zenodo_metadata.json`.
6. Set public visibility only after the security and rights review. If an embargo
   or restricted access is needed, state the real reason and the access procedure.
7. **Save draft**, clear every validation error, open **Preview** and check
   authors, version, DOI, licences and files.
8. **Publish**. The DOI is registered on publication.
9. Copy the version DOI and the full citation into the manuscript.
10. For any later file change, create a **New version** — a separate linked
    record with its own identifier. Cite in the article the exact version used.

## F. Zenodo cautions

* The article DOI and the archive DOI identify different objects. Never paste the
  article DOI into the existing-DOI field of this upload.
* Deleting a draft with a reserved DOI loses the reservation. Check the file list
  before reserving.
* Metadata of a published record can be edited; files effectively cannot. Finish
  the files before pressing Publish and release changed files as a new version.

## G. Final author sign-off

Sign only after the checks above are genuinely done:

> I confirm that the Zenodo record and the related article identify every result
> as a synthetic SIM output; that the archive presents no software-generated
> value as a physical measurement; that the reproducibility claims are backed by
> the actual code, configurations, run-level artifacts, manifests and run
> commands; that authorship, licences, funding, version and DOI were verified;
> and that no confidential information is disclosed.

Corresponding author: Dmytro Prokopovych-Tkachenko
Date: ____________________    Signature: ____________________
