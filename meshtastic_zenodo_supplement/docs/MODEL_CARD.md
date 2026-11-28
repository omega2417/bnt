# Demonstration model card

**Status: synthetic demonstration. The model has no measured predictive accuracy.**

## Identity and intended use

Version 1.1.0 (weights unchanged from 1.0.0). Offline exploratory prototype attached to a planned three-node Meshtastic experiment that has not been carried out. The score estimates the synthetic target `completed_on_time`. The model produced no result of the accompanying article and must not be used to advise on real operations; the software refuses to score rows labelled `measured` with it.

## Training data

3,600 synthetic observations in 90 simulated groups (2,160 training, 720 validation, 720 test rows; whole groups kept together). Features are drawn from assumed distributions and the label is sampled from an invented logistic formula, both given in full in `mesh_decision/demo.py`. Nothing was observed. Architecture 13–16–8–1; best epoch 13 of 38; normalisation fitted on training rows only.

## Software self-consistency check on the synthetic hold-out set

These numbers show how well each model recovers the invented formula that generated the labels. **They are not predictive accuracy** and say nothing about a Meshtastic network.

| Model | ROC AUC | Brier score | Accuracy at 0.5 |
|---|---:|---:|---:|
| Neural MLP | 0.8855 | 0.1376 | 0.8042 |
| Logistic regression | 0.8918 | 0.1344 | 0.7986 |
| Constant training prevalence | 0.5000 | 0.2496 | 0.5292 |

The logistic baseline does better on ROC AUC and Brier score, which is expected because the labels come from a logistic formula. The check gives no reason to prefer a neural network.

## Limitations

Scores are uncalibrated. Decision thresholds and guard values are proposed settings, not tuned on anything. Marginal range checks do not detect all distribution shifts. A random group split is not a future-site test. The generator simulates neither radio propagation, channel contention, battery behaviour nor people. Training on measured rows would change the provenance label but would not validate the model: independent field testing, calibration and cost-sensitive threshold assessment would still be needed.

## Reproducibility

Dataset SHA-256: `92b1f710b9b7d8b52ed2fdf15bb429087d4c152b37d30682ef46c53cef5de277`. Maximum difference between exported NumPy inference and scikit-learn inference: 2.22e-16. For version 1.1.0 the data, hold-out predictions and example decisions were regenerated with the pinned requirements under Python 3.13.18 and are identical to those of 1.0.0. Environment: `metadata/tested_environment.json`.

## Assistance

Software, tests and generator were prepared with ChatGPT assistance; the 1.1.0 revision with Claude assistance.
