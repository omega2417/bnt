# UMSF Cyber-Range Digital Twin — Reproducible SIM Experiment, Synthetic Telemetry, and Provenance-Aware Verification Package

**Version:** 2.0.0  ·  **Mode:** SIM (simulation only)  ·  **Evidence class:** pre-experimental synthetic model
**Zenodo DOI:** [10.5281/zenodo.22287426](https://doi.org/10.5281/zenodo.22287426)
**Source repository:** <https://github.com/omega2417/bnt/tree/claude/zenodo-software-deposit-hdxmbh/zenodo-deposit/umsf-cyberrange-digital-twin-sim-reproducibility-package-v2.0.0>
**Related manuscript DOI:** `[ARTICLE DOI, AFTER ACCEPTANCE]`

Ukrainian title: *Цифровий двійник кіберполігону УМСФ: відтворюваний SIM-експеримент, синтетична телеметрія та пакет провенанс-орієнтованої верифікації (v2.0.0).*

---

## 1. Evidence boundary — read this first

**All numerical results in this deposit are outputs of a software model under
explicitly stated assumptions. They are not measurements of the physical UMSF
cyber range.** They do not establish actual WAN, VPN or automatic-transfer-switch
switchover times, Wi-Fi coverage or capacity, EcoFlow or 48 V battery autonomy,
battery thermal behaviour, or the field accuracy of any detector.

This deposit demonstrates **executability, internal verification and
reproducibility** of a software artifact. It does **not** demonstrate
calibration against a physical object, sim-to-real transfer, or operational
fitness.

Provenance status of the parameter inventory shipped here, recomputed by
`make validate`:

| Evidence status | Count |
|---|---:|
| MEASURED | 0 |
| VENDOR_SPEC | 0 |
| DERIVED | 0 |
| ASSUMED | 0 |
| SYNTHETIC_DEMO | 194 |
| UNKNOWN | 4 |

The four UNKNOWN parameters — `power.site_a.chemistry`,
`power.site_a.parallel_count`, `vpn.mtu`, `vpn.protocol` — are not a defect.
They block HIL mode in software until they are physically measured.

**Terminology used consistently in this package.** *Verification* = the
implementation matches its specification. *Calibration* = model parameters are
fitted to real telemetry (**not performed**). *Physical validation* = model
behaviour is tested against the real range (**not performed**).

---

## 2. What this package is for

A safe, reproducible, pre-experimental check of network, energy, telemetry and
cyber-security scenarios for a two-site cyber range, executed entirely in
software, before any move to EMU, REPLAY, HIL or physical testing. It is the
reproducibility companion to the manuscript listed in `zenodo/publication_snippets.md`.

It is **not** a safety controller, **not** an attack tool, and it opens no
sockets. Threats are modelled at feature level only; the package contains no
exploit code and no live targets.

## 3. Contents

| Path | Contents |
|---|---|
| `src/umsf_twin/` | 66 Python modules, standard library only — kernel, federates, pipelines, experiment layer, read-only vendor adapters, CLI |
| `configs/inventory/demo.json` | Demonstration inventory; every value carries an `evidence_status` |
| `configs/policies/` | Safety policy and DoE factor definitions |
| `scenarios/` | The five scenarios that were actually executed |
| `tests/run_tests.py` | The 40 automated checks (unit, property, contract, determinism, safety, integration, calibration, performance) |
| `scripts/` | Run index builder, reference-value checker, manifest/checksum builder, package builder |
| `results/scenarios/` | Artifacts of the five executed scenario runs, one directory per `run_id` |
| `results/demo/` | Three-replicate demonstration run |
| `results/doe/` | Eight-point exploratory Latin-hypercube sweep |
| `results/monte_carlo/` | Demonstration Monte Carlo with sequential stopping |
| `results/verification/` | Test log, inventory validation, determinism check, reference-value comparison |
| `results/run_index.csv` | One row per independent software run/replicate |
| `data/synthetic/` | Pointer to the record-level synthetic data (see §7) |
| `manifests/` | Campaign manifest, per-file SHA-256, provenance histogram |
| `docs/` | Experiment report, evidence boundary, data dictionary, methodological note, integrity statement, **publication insert** |
| `zenodo/` | Ready-to-paste Zenodo metadata, upload checklist, manuscript snippets |
| `LICENSES/` | Separate terms for code, synthetic data and documentation |
| `SHA256SUMS.txt` | SHA-256 of every file, generated last |
| `environment.txt` | Interpreter, OS, architecture, locale, dependencies |

## 4. System requirements

CPython 3.10 or newer (this campaign was executed on **CPython 3.11.15, Linux
x86_64**), GNU make optional, no third-party packages, no network access. Cross
platform behaviour has not been verified.

## 5. Quick start

```sh
unzip umsf-cyberrange-digital-twin-sim-reproducibility-package-v2.0.0.zip
cd  umsf-cyberrange-digital-twin-sim-reproducibility-package-v2.0.0
make test        # 40 automated checks
make validate    # inventory + evidence histogram
make verify      # determinism and seed-stream separation
make demo        # three-replicate demonstration run
make scenarios   # the five SIM scenarios
make doe         # eight-point exploratory sweep
make mc          # demonstration Monte Carlo
make refcheck    # compare this reproduction against the specification's values
make index       # rebuild results/run_index.csv
make manifests   # rebuild manifests/ and SHA256SUMS.txt
```

`make all` runs the whole sequence in that order. Without `make`, read the
recipes in `Makefile`; each is a single `python3` command with
`PYTHONPATH=src`.

Verify integrity of the unpacked archive with:

```sh
sha256sum -c SHA256SUMS.txt
```

## 6. Expected control values

Reproduced in this release, and checked automatically by
`scripts/check_reference_values.py` against the values published in the
executable specification (Appendix K):

| Check | Expected | Observed here |
|---|---|---|
| Automated software checks | 40/40 | **40/40** |
| Reference values from the specification | 86 enumerated | **86/86 reproduced** |
| Inventory config hash | `4e162d71…a740` | identical |
| Determinism / seed separation | deterministic, replicates differ, 1806 rows | identical |
| Demonstration run | gates pass, 5422 rows | identical |
| Five scenarios | 1204 / 1406 / 1405 / 2408 / 1204 rows, all gates PASS | identical |
| Monte Carlo | stops at 5 replicates, estimate 71.8948 | identical |
| Engine source hash | `2136f8f4…4549` (prior reproduction) | identical |

**Known, disclosed discrepancy.** The specification prints a truncated engine
source hash `925c24c6…`, while the source tree extracted from that same
specification hashes to
`2136f8f4be6e300c272a52056e15038260f33d67e0283cadde99939a09b24549`. The prior
reproduction recorded the same `2136f8f4…` value. The difference is a byte-level
consequence of extracting code out of Markdown (trailing newlines), not a
behavioural difference. The trees are **not** claimed to be byte-identical.

The source report for this deposit stated *62* behavioural reference values. The
86 values checked here are this package's own explicit enumeration of Appendix K
(K.3–K.7), not a restatement of that count.

## 7. Data, provenance and the unit of analysis

Record-level synthetic data is stored inside each run directory rather than
duplicated: `telemetry.csv`, `ground_truth.csv`, `alerts.csv`,
`response_audit.json`, `parameters.json`, `scenario.resolved.json`,
`summary.json`, `manifest.json` and `report.md`. Field-by-field definitions are
in `docs/data_dictionary.md`.

**The unit of analysis is one software run/replicate, never one telemetry row.**
Rows inside a run are dependent. This campaign contains 16 independent
run/replicate units: 5 scenario runs, 3 demonstration replicates and 8 DoE
points. The 13,049 rows of the scenario and demonstration runs (7,627 + 5,422)
are dependent time-series records, not 13,049 independent observations.

Every dataset in this package carries the provenance vector
`stimulus_origin = scripted_synthetic`, `observation_origin = simulator_output`,
`label_origin = scenario_controller`, `curation_origin = automated_pipeline`,
`analysis_origin = derived_metric`. The values `measured`, `physical_sensor` and
`cyber_range_instrumentation` are not used anywhere and must not be introduced
without a separate primary-log evidence package.

## 8. Limitations

* No physical calibration and no independent sim-to-real validation.
* EMU, replay of real telemetry, HIL, passive physical baselining and shadow-mode
  evaluation are out of scope for this release.
* The battery model is a gray-box surrogate; RF, VPN, WAN and thermal behaviour
  are simplified.
* One run per scenario does not support between-run variability estimates.
* The eight-point DoE is an exploratory demonstration of the pipeline, not a
  global or confirmatory sensitivity analysis.
* Monte Carlo with early stopping at five replicates characterises the internal
  stability of the model, not field uncertainty.
* Detection precision/recall describe the model's own scenario-ground-truth loop
  and say nothing about field detector performance.
* Cross-platform reproducibility beyond CPython 3.11 on Linux x86_64 is unverified.

## 9. Licences

Code: MIT. Synthetic data and documentation: CC BY 4.0. See `LICENSES/README.md`
for the file-by-file mapping. **Before publishing the record**, confirm that the
institutional and funder rights permit these terms; the README grants no rights
beyond the LICENSE files.

## 10. Source repository and archive

| Resource | Location |
|---|---|
| Archived release (citable, immutable) | <https://doi.org/10.5281/zenodo.22287426> |
| Source repository | <https://github.com/omega2417/bnt> |
| This package in the repository | <https://github.com/omega2417/bnt/tree/claude/zenodo-software-deposit-hdxmbh/zenodo-deposit/umsf-cyberrange-digital-twin-sim-reproducibility-package-v2.0.0> |
| Permalink to the exact commit that produced this release | <https://github.com/omega2417/bnt/tree/92f9f52a12f057a49efe68ce7de7b9b46071383e/zenodo-deposit/umsf-cyberrange-digital-twin-sim-reproducibility-package-v2.0.0> |

Cite the Zenodo DOI, not the repository URL: the repository can change, the
archived version cannot. Use the repository only to follow development or to
open an issue.

## 11. How to cite

See `CITATION.cff`. After publication, copy the citation string directly from the
Zenodo record page and check author order, year, resource type, version and DOI.

## 12. Contact and issues

Corresponding author: Dmytro Prokopovych-Tkachenko, ORCID
[0000-0002-6590-3898](https://orcid.org/0000-0002-6590-3898), Department of
Cybersecurity and Information Technologies, University of Customs and Finance,
Dnipro, Ukraine. Report reproduction failures with your `environment.txt`, the
failing command and the produced `manifest.json`.

---

## Український опис

Цей депозит містить відтворюваний пакет програмного прототипу цифрового
двійника двомайданчикового кіберполігону Університету митної справи та
фінансів. Пакет призначений для безпечної передекспериментальної перевірки
сценаріїв мережевої, енергетичної, телеметрійної та кібербезпекової поведінки до
перенесення дослідів у середовища EMU, REPLAY, HIL або на фізичний стенд.

Ресурс охоплює вихідний код версії 2.0.0, конфігурації сценаріїв, seed-політику,
тести, synthetic telemetry, сценарний ground truth, alerts, агреговані summaries,
manifests, результати обмеженого DOE та демонстраційного Monte Carlo. У цьому
випуску пройдено 40 із 40 автоматичних перевірок і відтворено 86 із 86
контрольних значень специфікації. У сценарних і демонстраційних SIM-прогонах
сформовано 13 049 залежних часових записів.

**Усі числові результати є синтетичними виходами програмної моделі.** Депозит не
містить вимірювань фізичного кіберполігону: статус MEASURED відсутній, 194
параметри мають статус SYNTHETIC_DEMO, а чотири залишаються UNKNOWN і блокують
режим HIL. Відтворюваність стосується програмного артефакту та його
відповідності специфікації, а не фізичної достовірності мережі, Wi-Fi, VPN,
резервного живлення або детекторів.

Повний український опис методології, межі тверджень і звіт експерименту —
у `docs/` (`evidence_boundary.md`, `experiment_report_uk.md`,
`methodological_note_uk.md`).
