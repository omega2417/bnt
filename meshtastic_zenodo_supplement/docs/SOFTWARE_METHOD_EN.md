# Supplementary neural decision support method

## Purpose and evidence boundary

The software converts a table of predecision observations into advisory outcomes for short logistics tasks in a three-node Meshtastic setting. It runs on a local computer and adds no functionality to the radio firmware. It is an exploratory supplement to the manuscript (logistics-4699826). No experiment has been performed: the three-node setting is planned, all training data are synthetic, and the model has no measured predictive accuracy. The manuscript's numerical economic results and the neural demonstration arise from different models and must not be combined as one empirical experiment.

## Learning objective and architecture

The supervised target is completion of the assigned task before its original deadline. Thirteen standardized numeric features feed two fully connected hidden layers of 16 and 8 units with ReLU activation, followed by a single logistic output. The output is reported as an uncalibrated neural score. The optimizer is Adam with initial learning rate 0.003, L2 penalty parameter 0.01, mini-batch size up to 128 and deterministic initialization seed 42. The model is trained for at most 250 epochs.

Independent groups are split approximately 60%/20%/20% for training, validation and testing using two GroupShuffleSplit operations. The scaler is fitted to training observations only. Validation log loss selects the retained epoch, with stopping after 25 non-improving epochs. Test observations are used only after model selection. Synthetic data and measured data cannot be mixed within one training invocation.

Weights, offsets, normalization statistics, feature order, training ranges and provenance are exported to NPZ numerical arrays. Loading uses `allow_pickle=False`. NumPy inference is compared with scikit-learn prediction, with a maximum accepted difference of 1e-10. This prevents silent mistakes in model export without relying on serialized Python objects.

## Decision policy

The decision layer is a documented rule system around the learned score. It first checks data validity and the original deadline, then operator availability, S0 availability, backup power and status age. It refuses use of a synthetic model for measured observations and flags inputs outside the marginal ranges observed in training. This range check detects some extrapolation; it is not a comprehensive out-of-distribution detector.

Proposed thresholds are 15% battery, five minutes of dispatch-path backup and 120 seconds for status/snapshot age. Scores in [0.45, 0.55] request manual review. Other scores below 0.75 request a check of the link or a feasible alternative contact method. Scores at least 0.75 permit a recommendation to continue under monitoring. These decisions always require human review and do not actuate equipment. They are neither a learned route planner nor a cost-optimal policy.

## Evaluation and baselines

On synthetic data the evaluation is a software self-consistency check, not a measurement of predictive accuracy. It reports accuracy, balanced accuracy, ROC AUC, Brier score, log loss and a confusion matrix at a classification threshold of 0.5. A logistic regression trained on the same training partition and a constant predictor using training prevalence provide baselines. They are evaluated on the identical test groups. The recommendation threshold of 0.75 is distinct from the 0.5 metric threshold and has not been optimized against operational costs.

Synthetic outcomes are sampled from the invented logistic mechanism in `mesh_decision/demo.py`. The generator is supplied in full so its assumptions are inspectable. The demonstration shows that the data pipeline and software execute; it cannot establish real accuracy, savings, endurance or resilience. It also cannot establish that a neural network is preferable to logistic regression. See the generated model card for the actual comparison.

## Planned field validation (not started)

Collect complete task outcomes, including failures, under E0–E8; preserve the source log and timing uncertainty. Predefine independent groups, a separate future deployment test, operational costs and thresholds. Examine class imbalance, calibration, missed failures, unnecessary interventions, performance by outage condition and operator behavior. Report uncertainty using independent experimental groups, not packets as independent replicates. The program's minimum of 12 groups is not a power analysis. No recommendation should be described as empirically validated solely because it was produced by a trained model.

## Software references

1. Scikit-learn. MLPClassifier. https://scikit-learn.org/stable/modules/generated/sklearn.neural_network.MLPClassifier.html
2. Scikit-learn. GroupShuffleSplit. https://scikit-learn.org/stable/modules/generated/sklearn.model_selection.GroupShuffleSplit.html
3. Scikit-learn. StandardScaler. https://scikit-learn.org/stable/modules/generated/sklearn.preprocessing.StandardScaler.html

Documentation checked 30 October 2026. Exact tested package versions are pinned in requirements.txt; online stable documentation may describe a newer release.
