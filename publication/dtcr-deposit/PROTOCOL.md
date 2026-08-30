# Experimental protocol

This file states the design decisions the analysis code assumes. It is the
document a reviewer needs in order to judge whether the statistics are the right
ones, and it is what Section 2.7 of the revised manuscript cites.

## 1. Design

* **Factors.** Scenario (S1–S4, fixed) x arm (baseline, framework).
* **Repetitions.** 20 per cell; 160 runs in total for the main comparison, plus
  480 runs for the ablation matrix.
* **Pairing.** Runs are executed as **interleaved matched pairs**: within
  repetition *k* of scenario *s*, the baseline arm and the framework arm are run
  back to back against the same freshly reset testbed state and the same attack
  parameters. Repetition index *k* is therefore a blocking factor, and the
  primary analysis is paired (`stats.compare_groups(..., paired=True)`).
  If your campaign does **not** interleave, set `PAIRED = False` in
  `analysis/statistics.py`; the code then uses Welch and Mann–Whitney instead.
* **Randomisation.** The order of scenarios within a repetition block is
  permuted with seed 20260731. The arm order within a pair alternates by
  repetition parity, so arm order is balanced across the campaign.

## 2. Reset and washout

Between every run: the edge namespace is fully redeployed, twin state is
discarded and re-synchronised from the physical tier, trust scores are reset to
their initial value, Suricata state tables are flushed, and the attacker host
idles for a 300 s washout before the next `t_a`. The washout is not part of any
observation window.

## 3. Ground truth

* `attack_onset_s` is taken from the attack driver's own log, not from any
  detector, so detection latency cannot be defined circularly.
* `risk_ranking_correct` is scored against an incident trace recorded by the
  attack driver, which knows which assets it actually touched.
* Recovery is validated by an independent service prober, not by the
  orchestrator's own report of success.

## 4. Handling of missed detections, failed recovery and censoring

| Situation | Rule |
|---|---|
| Attack never detected within the observation window | `detection_latency_s` is left empty; the run counts in `n` and is reported as a missed detection. It is **not** replaced by the window length. |
| Availability never satisfies the Eq. (15) hold condition | `recovery_censored = 1`, `recovery_time_s` empty. Excluded from means, reported in the run count, and reported as a censored count next to every recovery statistic. |
| Recovery achieved but a rollback occurred | The run is retained; `rollback = 1` is reported separately. Rollback is an outcome, not an exclusion criterion. |
| Run aborted by testbed failure unrelated to the scenario | Run is discarded and re-executed; the discard is logged in the campaign log with a reason. Discards are reported in the manuscript. |

No run is dropped for being an outlier.

## 5. Statistical analysis plan (fixed before analysis)

* **Primary endpoints.** Detection latency and service recovery time, per
  scenario, baseline vs framework.
* **Secondary endpoints.** NRI, integrity-verification metrics, resource
  overhead, and the ablation endpoints.
* **Estimators.** Mean with a 95% *t* interval; median with IQR; the paired mean
  difference with a percentile bootstrap interval (10,000 resamples, seed
  20260731). Latency distributions are right-skewed, so the bootstrap interval
  is the one quoted in the text and the *t* interval is reported for
  completeness.
* **Tests.** Paired *t*-test as the primary test with the Wilcoxon signed-rank
  test reported alongside it; Holm correction across the four scenario-level
  tests of each endpoint family.
* **Effect sizes.** Hedges' *g* and Cliff's delta, both reported. Cliff's delta
  is the one to trust when the distributions are skewed.
* **Classification rates.** Wilson score intervals, never the normal
  approximation, because specificity sits near 1.
* **No subgroup analysis** beyond the four pre-specified scenarios, and no
  threshold re-tuning after seeing the evaluation data: `theta`, `lambda`, the
  trust weights and the challenge budget are fixed in
  `configs/framework_parameters.yaml` before the campaign and are not touched
  afterwards.

## 6. Threats to validity this design does not remove

* **Pseudoreplication.** Twenty repetitions on one testbed are not twenty
  independent deployments. Intervals describe run-to-run variation on a single
  topology, not between-deployment variation.
* **Baseline confounding.** The `B0` baseline mixes an automation deficit with a
  detection deficit. `B1` (IDS + automated playbook) exists to separate them and
  must be reported whenever `B0` is.
* **Threshold leakage.** Baselines were estimated on a normal window disjoint in
  time from the evaluation window, but drawn from the same deployment; a
  cross-deployment evaluation would be stronger.
* **Scale.** Twelve emulated sensors and a four-node dependency graph do not
  support claims about smart-region-scale behaviour.

## 7. Safe-experiment statement

All attacks are executed inside an isolated laboratory network with no route to
production or public infrastructure. The attacker host has no external
connectivity. No third-party system is targeted, scanned or affected. Attack
scripts are published so that reviewers can confirm their scope.
