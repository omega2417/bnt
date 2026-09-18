# Reproducibility

The claim this file supports is narrow and checkable: **every number and every
figure in the article can be regenerated from this repository with one command
each, and two runs on different machines agree exactly.**

## One-command reproduction

```bash
pip install -e ".[dev]"      # or: pip install -r requirements-lock.txt
pytest                       # 106 tests, ~25 s
evoproto dryrun              # Section 7.7 -> results/dry_run/
evoproto figures             # Figures 1-8 -> figures/*.pdf and *.png
evoproto verify-dois         # reference list against CrossRef (needs network)
evoproto env                 # environment record for the appendix
```

`make all` runs the same sequence.

## Why the runs agree

1. **Seeds are derived, not drawn.** `stable_seed(task, arm, replicate)` is
   `blake2b(package_version | task | arm | replicate)` truncated to 32 bits.
   Python's built-in `hash` is randomized per process and would make replicates
   irreproducible across runs; blake2b is stable across processes, machines and
   Python versions. Because the arm is inside the digest, arms B and C cannot
   silently share a random stream. `tests/test_data.py` pins one seed value, so
   any change to the derivation fails the suite loudly.
2. **Every generator is explicit.** All randomness goes through
   `numpy.random.default_rng(seed)`; there is no global seeding and no reliance
   on process state.
3. **Every result carries a provenance tag.** A MODELED analytic result cannot
   be mistaken for a MEASURED one when tables are assembled: the tag travels
   with the dictionary (`data.Tag`).
4. **The environment is recorded with the results.**
   `experiment.environment_record()` is written into `results.json`.
5. **The figures call the same code paths as the protocol.** Figure 7 runs the
   dry run; Figure 8 calls `gate.decide` on the grid it colors; Figure 3 calls
   `phylo`. A figure cannot drift away from the numbers it illustrates.

`tests/test_reproducibility.py::test_two_runs_of_the_protocol_agree_exactly`
asserts point 1–2 directly.

## Environment of the archived run

```json
{
  "evoproto": "0.1.0",
  "python": "3.11.15",
  "platform": "Linux-6.18.44-fc-v33-x86_64-with-glibc2.39",
  "machine": "x86_64",
  "packages": {"numpy": "2.4.6", "scipy": "1.17.1", "networkx": "3.6.1", "matplotlib": "3.11.2"}
}
```

Exact pins are in `requirements-lock.txt`. The package itself supports
NumPy ≥ 1.22 / SciPy ≥ 1.8 / NetworkX ≥ 2.8 / Matplotlib ≥ 3.5 and Python 3.9+;
CI runs 3.9 through 3.12.

## Dry run reproduced here (Section 7.7)

Task T1, ten seeded replicates, population 40, 25 generations per arm.
Tag: **SYNTHETIC — pipeline validation only, no inference about H1–H3.**

| Arm | FSR | HV (normalized) | D | ITS (generations) |
|---|---|---|---|---|
| A (template-refinement stand-in) | 0.275 ± 0.219 | 0.081 ± 0.073 | 0.038 ± 0.050 | 15.100 ± 7.445 |
| B (uniform prior) | 1.000 ± 0.000 | 0.478 ± 0.005 | 0.078 ± 0.006 | 2.000 ± 1.155 |
| C (analog-shaped prior) | 1.000 ± 0.000 | 0.481 ± 0.002 | 0.073 ± 0.007 | 1.200 ± 0.632 |

Statistical module output (two-sided Wilcoxon, Holm within task, Cliff's δ):

| Contrast | Metric | p | p (Holm) | Cliff's δ | magnitude | significant |
|---|---|---|---|---|---|---|
| C vs B | FSR | 1.0000 | 1.0000 | +0.00 | negligible | no |
| C vs B | HV | 0.1309 | 0.4219 | +0.56 | large | no |
| C vs B | D | 0.1055 | 0.4219 | −0.38 | medium | no |
| C vs B | ITS | 0.1250 | 0.4219 | −0.40 | medium | no |
| C vs A | FSR | 0.0020 | 0.0156 | +1.00 | large | yes |
| C vs A | HV | 0.0020 | 0.0156 | +1.00 | large | yes |
| C vs A | D | 0.0840 | 0.4199 | +0.24 | small | no |
| C vs A | ITS | 0.0020 | 0.0156 | −1.00 | large | yes |

The whole run takes about 12 s on a laptop-class processor, so the computational
arms of the real experiment will be limited by the FE evaluator, not by the
search loop.

### How this compares with Table 7 of the manuscript

These numbers come from **this** implementation and differ from the Table 7 of
the current manuscript draft, which was produced by the authors' original
stand-in arms. The pattern is the same and the qualitative conclusion is
unchanged — arm A (a time-matched, not evaluation-matched, stand-in) trails the
computational arms; B and C both saturate the feasible-solution rate; arm C is
*not* more diverse than arm B — but the specific values differ, most visibly for
arm A's FSR (0.275 here versus 0.38) and for the C-versus-B contrast on HV,
which is directionally positive here with a large effect size but does not
survive Holm correction at ten replicates (p = 0.131, adjusted 0.422).

Two consequences for the manuscript, both recorded in `docs/paper_mapping.md`:

1. Replace Table 7 and the accompanying sentences in Section 7.7 with the output
   of `evoproto dryrun` from the archived version, or state explicitly which
   implementation produced the published table.
2. The sentence "the statistical module returned … a Holm-adjusted p = 0.029
   with Cliff's δ = 0.78 on HV" must be regenerated: it is an artifact of the
   arm-A/arm-C stand-ins, and both are hand-set, not derived from a curated
   EE-KG. The point the sentence makes — that the plan produces significant,
   non-significant and negative-direction results as appropriate — survives, and
   this run demonstrates it just as well.

This is exactly the kind of discrepancy the provenance tags exist to expose. No
inference about H1–H3 is drawn from either version of the table.

## Determinism caveats

- Results are bit-identical for a fixed `(package version, NumPy version,
  platform)`. Floating-point summation order can differ across BLAS builds; the
  metrics reported here are stable to the printed precision across the
  configurations in CI.
- `evoproto verify-dois` needs outbound access to `api.crossref.org`. It was
  **not** run to completion in the environment that produced this archive
  (network policy blocked CrossRef); the offline structural check passes for all
  63 entries, 8 of which legitimately have no DOI. Run the online check before
  submission.
