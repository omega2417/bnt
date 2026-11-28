# Changelog

## 1.1.0 — 2026-11-28

Revision made in response to peer review of the accompanying manuscript (logistics-4699826, Reviewer 3).

Corrections of false or misleading content in 1.0.0
- Removed `reference_materials/Meshtastic_Three_Node_Blackout_Experiment_UA.pdf`. It stated that a field experiment on three physical nodes "was conducted", including trials during power outages. No such experiment took place.
- English protocol (DOCX/PDF): the sentences "The initial installation and power-interruption trials provide the starting configuration" and "a quantitative follow-up to the initial physical setup" implied the same and were replaced by an explicit statement that nothing has been assembled or run.
- Removed `manuscript/`, a pre-revision manuscript snapshot under the former title.
- Creator list reduced from the six manuscript authors, whose contribution to the software had not been established, to the author named in the article's reference [59].
- Manuscript title updated everywhere; statements that no Zenodo record or DOI exists were replaced by the actual status.

Evidence labelling
- Synthetic hold-out scores are now called a software self-consistency check and are explicitly not predictive accuracy (`models/evaluation.json` field `evidence_status`, model card, console output of `run_demo.py` and `train`).
- Every row of a decisions CSV has an `evidence_status` column.
- New `docs/COLLECTOR_FIELD_MAPPING.md`: which input fields the collector [54] records and which it does not.

Unchanged
- Synthetic data, model weights' behaviour, hold-out predictions and example recommendations are identical to 1.0.0 (regenerated and compared).

## 1.0.0 — 2026-10-30

First release (https://doi.org/10.5281/zenodo.23798128). Superseded; do not use — see above.
