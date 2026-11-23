# Reproducibility

## One command

```bash
python -m pip install -e ".[figures]"
recovery-evidence reproduce --check
```

The command runs the 27 implementation checks, the 13 conditions (300 paired trajectories of
180 days, four policies each), the independent analysis, the claim-to-evidence register and
the figures, and then compares all 95 output files with `results/SHA256SUMS.txt`. Expected
last lines:

```
[6/6] SHA-256
  95 files identical to the released SHA256SUMS.txt; 0 differ; 0 absent
```

Wall time is about 40 s on four cores (experiment 15 s, analysis 18 s, figures 6 s).
Without Matplotlib use `--no-figures`; the 15 figure files are then reported as absent and
every number is still produced.

## What is fixed

| Element | Value | Where |
| --- | --- | --- |
| Root entropy | 20261123 | `data/conditions.json` |
| Bit generator | NumPy `PCG64`, `SeedSequence(root, spawn_key=(configuration, replicate, stream))` | `generator.stream` |
| Replicate index | 0 … 299 | `experiment.run_condition` |
| Streams | 0 transitions, 1 notices, 2 delays, 3 non-substantive notices, 4 joint degradation | `docs/RNG_STREAMS.md` |
| Bootstrap | 10,000 resamples of replicate identifiers, percentile method, `default_rng(20261124)` | `analysis.bootstrap_indices` |
| Tie-break | largest priority; ties to the alphabetically first identifier; exact integer or rational arithmetic | `policies.select` |
| File format | fixed row order and number format; gzip without file name, time stamp 0, level 6 | `experiment._GzCsv` |

Only `run_manifest.json` differs between runs (it stores the UTC time) and is excluded from
the digest list.

## Levels of verification

1. **Formulas.** `supplementary/worked_example.py` (standard library only, no shared code)
   re-derives the worked example, the static importances and both audit cases.
2. **Implementation.** `recovery-evidence checks` runs the 27 checks of Section 4.6; pytest
   runs the same functions plus 73 further tests.
3. **Outcomes.** `analysis.py` imports nothing from the simulator. It recomputes false
   assurances, false rejections and spells from `verdicts.csv.gz` and compares them with the
   evaluator's `trace_summary.csv` for every trajectory and policy
   (`results/tables/integrity_report.txt`: all 13 conditions agree). A test alters one verdict
   row and confirms that the comparison fails.
4. **Files.** `recovery-evidence verify` compares the files on disk with the digests;
   `tests/test_reproducibility.py` regenerates every condition and compares it with the
   released per-trajectory summaries.

## Environment of the released files

CPython 3.13.18, NumPy 2.5.3, Matplotlib 3.11.2, Pillow as installed with Matplotlib,
Linux x86-64. Logs and tables depend only on Python and NumPy. The `PCG64` bit stream is
frozen by NumPy's compatibility policy; `Generator.random` and bounded `Generator.integers`
are not formally frozen, so the NumPy version is recorded and the digests would expose any
change. All other arithmetic is integer, rational or a single IEEE division per value. Figure files
(PDF, PNG, TIFF) are byte-identical only with the same Matplotlib, FreeType and Pillow
versions; with other versions the 80 non-figure files still match and the figures show the
same data.

## Relation to the manuscript draft

The draft of the article was written from an earlier run of the experiment. The text fixes
the seed scheme and the five streams but not the order in which each stream is consumed, and
the earlier code is not part of this archive. This package therefore fixes and documents one
order (`docs/RNG_STREAMS.md`). The consequences were measured, not assumed:

* **Transitions (stream 0) are recovered exactly.** Everything in the draft that does not
  depend on notices is reproduced digit for digit: all P0 values of Table 5 (10.15, 9.69,
  19.84, 13.7%, 2.74, 95), all P0 entries of Table 7, condition C1 (24.76) and the whole of
  condition C10 (10.11 / 9.78 / 9.07; P3 − P1 = −1.05 and −3.85), which exercises P2, P3, the
  evaluator and the bootstrap.
* **Notice-dependent values differ within Monte Carlo error.** Of 410 printed numbers, 112
  are identical and 298 differ; among differing means the largest gap is 2.3 Monte Carlo
  standard errors and the median is 0.6.
* **Conclusions are unchanged in direction; three statements need rewording.**

| Statement in the draft | Draft | This package | Consequence |
| --- | --- | --- | --- |
| Primary contrast P3 − P1, false assurance, C0 | −0.54 [−0.72, −0.35] | −0.42 [−0.60, −0.24] | H1 supported in both; relative reduction about 7% instead of 9% |
| P3 − P1, false rejection, C0 | −1.97 [−2.19, −1.75] | −2.12 [−2.35, −1.90] | unchanged |
| P3 − P2, false assurance, C0 | −0.12 [−0.29, 0.05] | 0.01 [−0.16, 0.17] | interval includes zero in both; "static importance captured most of the gain" becomes "all of the gain" |
| C7 joint failure, P3 − P1, false assurance | −0.17 [−0.34, −0.00], "only just excludes zero" | −0.25 [−0.41, −0.09] | advantage is reduced but the interval clearly excludes zero |
| C8 map error, P3 − P2, false assurance | −0.28 [−0.44, −0.13] | −0.11 [−0.25, 0.04] | interval now includes zero |

The complete list is `results/tables/manuscript_alignment.md` (generated; one row per number
to replace) and `results/tables/claims_register.csv` (all 410 numbers with source file).
**The article and the archive must report the same digits**: before submission either replace
the draft numbers with the values of this package, or, if the original logs still exist,
archive those logs and state which code produced them. The first option is the one this
package supports.

## Deviations from the planning protocol

Section 4.7 of the article lists them. In this package: five streams instead of three; own
delay draws for non-substantive notices (second block of stream 3); both kinds of notices
suppressed for A and H in C6; a `metric` column and additional contrasts in
`paired_results.csv`; gzip time stamps fixed to zero. The re-check-delay analysis
(`recheck_delay.csv`) is exploratory.
