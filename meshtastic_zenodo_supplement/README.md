# Meshtastic logistics continuity supplement: experiment preparation and exploratory decision-support prototype

Version 1.1.0 — 28 November 2026. Reference [59] of the manuscript **Strengthening Operational Autonomy in Small and Medium-Sized Enterprise Logistics with Meshtastic Mesh Networks: Reference Architecture and Ex-Ante Model-Based Assessment** (MDPI *Logistics*, logistics-4699826).

## Evidence status — read first

> **No experiment has been performed and this bundle contains no measured data.**
>
> * The three-node testbed described in `docs/` has **not been assembled, powered or operated**. The protocol is a plan.
> * All 3,600 training observations are **synthetic**: they are drawn from assumed distributions, and their labels are produced by an invented logistic formula (`mesh_decision/demo.py`).
> * The neural prototype therefore has **no measured predictive accuracy**. The scores reported for its synthetic hold-out set (`models/evaluation.json`) are a software self-consistency check: they show how well the network recovers the invented formula, nothing more. A plain logistic regression recovers it slightly better.
> * The prototype **produced no result of the article**. The article's numbers are ex-ante model predictions computed with separate scripts (`model.py`, `figures.py`), which are not part of this bundle.
> * The prototype is included for one reason: it fixes the input fields that the event log has to record during the field experiment planned in Section 4.6 of the article (see `docs/COLLECTOR_FIELD_MAPPING.md`).

### Correction of version 1.0.0

Version 1.0.0 of this record (https://doi.org/10.5281/zenodo.23798128) contained the file
`reference_materials/Meshtastic_Three_Node_Blackout_Experiment_UA.pdf`, which stated in Ukrainian that a field
experiment "was conducted" on three physical Heltec nodes, including trials during power outages. **That statement
was false.** No such experiment took place; the text was a draft written as if the planned trial had been done.
The English protocol likewise referred to "initial installation and power-interruption trials". The file has been
removed and the protocol corrected in version 1.1.0. Version 1.0.0 remains visible on Zenodo because published
versions cannot be deleted; it should not be used or cited.

Version 1.0.0 also carried a pre-revision snapshot of the manuscript under its former title and listed all six
manuscript authors as creators although their contribution to the software had not been established. The snapshot
has been removed, and the creator is now the one named in the article's reference [59].

## Quick start

Use Python 3.12 or 3.13 (checked with 3.13.18 on Linux). From the extracted bundle folder:

```bash
python -m venv .venv
source .venv/bin/activate            # Windows PowerShell: .venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python -m mesh_decision predict --data data/inference_examples.csv --model models/neural_model.npz --output my_decisions.csv
```

For prediction only, install `requirements-inference.txt`. No network access, credentials, Meshtastic device or GPU are needed.
Every row of the output carries an `evidence_status` column that repeats that the bundled model is a synthetic demonstration.

To regenerate the synthetic data, retrain and obtain recommendations in a new folder:

```bash
python run_demo.py --output demo_run_1
```

With the pinned requirements this reproduces `data/`, `models/heldout_predictions.csv` and `results/example_decisions.csv` exactly.

Training on future measured trials uses the same commands with a CSV built from `data/templates/` (see `docs/INPUT_DATA_DICTIONARY.md`). No such data exist today. At least 12 independent `group_id` values and both outcome classes in each partition are required; this is a software safeguard, not a sample-size justification. Do not relabel synthetic rows as measured.

## Contents

| Path | Purpose |
|---|---|
| `mesh_decision/` | CSV validation, synthetic generator, MLP training, inference and recommendation rules |
| `data/` | Synthetic data, inference examples and empty templates for future measurements |
| `models/` | Demonstration weights (non-pickle NPZ), metadata, training history, split manifest and synthetic hold-out check |
| `results/` | Example recommendations and verification records of this release |
| `docs/` | Prospective experiment protocol (DOCX/PDF), software method, input dictionary, model card, collector field mapping, manuscript wording |
| `reference_materials/` | Hardware reference and manufacturer datasheet (third-party rights, see `LICENSING.md`) |
| `metadata/` | Creator information, draft Zenodo fields, source provenance, tested environment |
| `notebooks/` | Small runnable workflow without embedded outputs |
| `tests/` | Unit and integration tests |
| `SHA256SUMS.txt` | Integrity hashes of the release files |

## What the program does

Each CSV row describes one decision event using information available at `decision_time`. Thirteen numeric inputs cover link quality, preceding-window delivery and delay, information age, power, queueing, hops, endpoint availability, Internet availability and time remaining. A 13–16–8–1 multilayer perceptron produces an uncalibrated score for completion of the task by its deadline.

Hard checks precede the score: missing or invalid input, expired deadline, unavailable terminal or station, low backup, stale data, use of the synthetic model on rows labelled measured (refused), and values outside the training ranges. Thresholds (0.45–0.55 review band, 0.75 advice threshold, 15 % battery, 5 min backup, 120 s age) are proposed settings that have not been tuned or tested on anything real.

The software writes a CSV; it does not transmit instructions, choose routes, switch power or control vehicles. Every recommendation has `human_review_required=True`.

## Verification of this release

```bash
python -m unittest discover -s tests -v
python tools/verify_checksums.py
```

See `results/verification_report.json` and `results/test_output.txt`. These checks cover software behaviour only. No hardware-in-the-loop trial, field dataset, calibration or deployment validation exists.

## Citation, licence, assistance

See `CITATION.cff` and `LICENSING.md`. New software is under the MIT licence; manufacturer documents keep their original rights and must be cleared or removed before public redistribution. Version 1.1.0 is to be deposited as a new version of the Zenodo record; its version DOI is assigned at deposit and is deliberately not stated here.

ChatGPT (OpenAI) assisted in preparing the original prototype and protocol; Claude (Anthropic) assisted in the version 1.1.0 revision. The author reviewed the material and is responsible for it.

Contact: omega2417@umsf.edu.ua.
