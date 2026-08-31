# Reproducibility

## One command

```bash
python -m pip install -e ".[figures]"
acp-sme reproduce
```

Runtime is a few seconds on a laptop. Without `matplotlib`, use `acp-sme reproduce
--no-figures`; every number is still produced.

## What "reproduces" means here

The article specifies every parameter (Tables A1–A3) but not the order in which the
pseudo-random draws are consumed. Two faithful implementations will therefore agree on the
*reported intervals*, not on identical digits. This package makes the achievable claim
explicit and tests it: `tests/test_reproducibility.py` asserts that each value falls inside
the confidence interval the article reports.

Within a single implementation, reproducibility is exact. The same seed produces
bit-identical traces on any platform, because the simulator uses only the Python
standard-library Mersenne Twister and no floating-point-sensitive third-party library
(`test_same_seed_reproduces_bit_identical_traces`).

## Primary results — Table 6

Article values are in brackets. Observed values are from this implementation, Python 3.11.

| Method | Measure | Article | This package | Inside the reported CI |
| --- | --- | --- | --- | --- |
| ACP-SME | Mean coverage, % | 80.4 [79.2, 81.6] | **80.36** [79.15, 81.57] | ✅ |
| Monthly review | Mean coverage, % | 78.8 [77.5, 80.1] | **78.83** [77.53, 80.13] | ✅ |
| Static profile | Mean coverage, % | 75.6 [74.3, 76.8] | **75.88** [74.57, 77.18] | ✅ |
| ACP-SME | 10th-percentile coverage, % | 74.1 [72.2, 76.1] | **74.12** [72.18, 76.06] | ✅ |
| Monthly review | 10th-percentile coverage, % | 72.0 [70.3, 73.8] | **71.85** [70.09, 73.62] | ✅ |
| Static profile | 10th-percentile coverage, % | 67.7 [65.9, 69.5] | **68.06** [66.22, 69.90] | ✅ |
| ACP-SME | Adaptation delay, days | 2.0 [1.7, 2.4] | **2.15** [1.74, 2.55] | ✅ |
| Monthly review | Adaptation delay, days | 6.4 [5.5, 7.2] | **6.30** [5.43, 7.18] | ✅ |
| Static profile | Adaptation delay, days | 18.2 [16.5, 19.9] | **17.83** [16.06, 19.60] | ✅ |
| ACP-SME | Review hours / 120 d | 3.7 [3.6, 3.8] | **3.66** [3.54, 3.77] | ✅ |
| Monthly review | Review hours / 120 d | 14.4 | **14.40** | ✅ (assigned constant) |
| Static profile | Review hours / 120 d | 4.0 | **4.00** | ✅ (assigned constant) |
| ACP-SME | False alerts / 120 d | 0.46 [0.31, 0.60] | **0.43** [0.29, 0.58] | ✅ |

Paired comparisons over matched scenario–replicate traces:

| Comparison | Article | This package |
| --- | --- | --- |
| ACP-SME − static | 4.77 pp [4.25, 5.29], positive in 90/90 | **4.48** pp [3.99, 4.97], positive in **90/90** |
| ACP-SME − monthly | 1.53 pp [1.39, 1.67], positive in 84/90 | **1.53** pp [1.40, 1.66], positive in **86/90** |

Mean irrelevant resource units — article 0.89 / 0.29 / 0.18 (static / monthly / ACP-SME);
this package **0.77 / 0.30 / 0.19**. The ordering and magnitude reproduce.

Design totals reproduce exactly: 3 archetypes × 30 replicates = **90 traces**,
**10,800 enterprise-days**, **420 labeled material events**.

## Sensitivity — Table 7

| Budget factor | Coverage, article | Coverage, this package |
| --- | --- | --- |
| 0.85 | 72.6% | **72.5%** |
| 1.00 | 80.3% | **80.4%** |
| 1.15 | 85.3% | **85.4%** |

Coverage is flat across τ ∈ {0.18, 0.23, 0.28, 0.33, 0.38} in both, confirming the article's
point that in this scenario catalog coverage is **budget-dominated, not threshold-dominated**
— a property of the deliberately well-separated event magnitudes, not a general finding.

### One documented deviation

**False alerts in the sensitivity grid.** The article reports 0.67 at τ=0.18 and 0.27 at
τ=0.38. This package observes **0.97** and **0.60** over its 30 sensitivity traces.

The article's figures match the *analytic design expectation* of the disclosed nuisance
process almost exactly:

```
E[false alerts] = 119 × (0.0008 + 0.012·e^(−5.2τ))
                = 0.66 at τ=0.18      (article: 0.67)
                = 0.29 at τ=0.38      (article: 0.27)
```

This package emits that expectation as the `expected_false_alerts` column of
`results/sensitivity.csv` and plots it alongside the observed counts in Figure 6, so the
two are never conflated. The gap is finite-sample noise: the sensitivity configuration uses
only 10 replicates per archetype (30 traces), where the standard error of the mean count is
roughly 0.15, and this particular seed block is alert-rich. The **primary** experiment,
which uses 90 traces, observes 0.43 against an expectation of 0.43 and against the
article's reported 0.46 — well inside the reported interval.

Both the observed and expected values decrease monotonically with τ, which is the behavior
the article draws its (explicitly labeled) sanity-check conclusion from. As Section 4.3
notes, this is a simulator sanity check, not independent detector evidence: the
false-trigger probability was *parameterized* to decrease with τ.

## Seed schedule

```
seed(archetype, replicate) = 27012026 + 101 × replicate + 10007 × archetype_index
archetype_index: micro = 0, small = 1, medium = 2
sensitivity runs: replicate index + 1000
```

Each trace derives five independent sub-streams by a fixed offset, so switching one
stochastic component off does not perturb the others:

| Sub-stream | Offset | Governs |
| --- | --- | --- |
| `initial` | 0 | the shared day-0 observation |
| `events` | 1,000,003 | event-score noise and triggered review delay |
| `false_triggers` | 2,000,003 | the daily nuisance-trigger process |
| `monthly` | 3,000,003 | monthly-review observations |
| `acp` | 4,000,003 | ACP-SME reassessment observations |

This is an implementation decision the article does not constrain. It is documented because
it is the single largest reason digit-level agreement is not achievable across independent
implementations.

## Underspecified details and how they were resolved

The article fixes every parameter, but a few mechanical details had to be settled. Each was
resolved in the way most consistent with the article's own reported values:

| Detail | Resolution | Consistency check |
| --- | --- | --- |
| Does demand decay after an event? | No. Demand accumulates and is capped at 1.75 | Reproduces the article's coverage trajectories and Table 6 |
| Monthly recompute days | 30, 60, 90 (day 0 is the shared initial profile) | Matches the assigned 4 × 3.6 = 14.4 review hours |
| Adaptation delay when a capability is already selected | Contributes 0 | The article states the static delay is finite "because some capabilities … were already selected in the initial profile" |
| Adaptation-delay censoring | Censored at 120 − event_day | Reproduces the static mean of ≈18 days |
| Is a nuisance day that coincides with a real triggered review a false alert? | No — it is not a separate reassessment | Matches the definition in Table 5; the effect is negligible at p ≈ 0.0036 |
| Does attenuation apply to the day-0 observation? | No — Table A3 assigns it to the "common reassessment model" only | Reproduces the shared initial profile across conditions |

## Environment

`results/run_environment.json` records the Python version, implementation and platform of
each run. The core package has **zero third-party dependencies**, so the numerical results
do not depend on NumPy, BLAS or any accelerated library version.

Verified on CPython 3.11 (Linux). Requires Python 3.9 or newer.
