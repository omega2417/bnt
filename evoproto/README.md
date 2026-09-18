# evoproto

Reference implementation accompanying

> O. Torstensson, Y. Danyk, D. Prokopovych-Tkachenko,
> **From Evolutionary Biology Data to Technological Prototypes: An AI-Driven
> Engineering Design Framework with an Evidence-Gated Validation Protocol.**

[![Open in Colab](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/github/omega2417/bnt/blob/master/evoproto/notebooks/01_quickstart.ipynb)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Docs: CC BY 4.0](https://img.shields.io/badge/Docs-CC%20BY%204.0-lightgrey.svg)](LICENSE-DOCS)
<!-- [![DOI](https://zenodo.org/badge/DOI/10.5281/zenodo.XXXXXXX.svg)](https://doi.org/10.5281/zenodo.XXXXXXX) NEEDS INPUT after deposit -->

The package turns curated evolutionary data into **verifiable, traceable
constraints** on AI-driven design, and refuses to recommend when the evidence is
too thin. Its strongest output is a recommendation with a traceability chain;
its weakest is an abstention with a missing-evidence report naming the
experiment that would close the gap.

**Nothing here is an empirical result.** No biological records ship with the
package; the demonstration pipeline runs in SYNTHETIC mode only, and every
number it produces carries a provenance tag (`MEASURED`, `MODELED`, `PROXY`,
`EXTERNAL`, `SYNTHETIC`).

## Install

```bash
pip install -e ".[dev]"            # from a clone
pip install -r requirements-lock.txt   # exact versions used for the archive
```

Python 3.9+; NumPy, SciPy, NetworkX, Matplotlib. Deliberately dependency-light,
so a reviewer can execute the protocol without proprietary tools.

## Run it

```bash
evoproto demo          # the whole pipeline once, with the decision at the end
evoproto dryrun        # Section 7.7: 3 arms x 10 replicates + statistics
evoproto figures       # Figures 1-8 as PDF (vector) and 600 dpi PNG
evoproto verify-dois   # every DOI of the reference list against CrossRef
evoproto env           # environment record for the reproducibility appendix
pytest                 # 106 tests
```

Or open the notebooks in Colab — no local install required:

| Notebook | What it does |
|---|---|
| [`01_quickstart`](notebooks/01_quickstart.ipynb) | the five stages of the framework, end to end |
| [`02_reproduce_figures`](notebooks/02_reproduce_figures.ipynb) | regenerates every figure of the article |
| [`03_protocol_dry_run`](notebooks/03_protocol_dry_run.ipynb) | the three-arm protocol and its statistics |

## What is implemented

| Module | Contents | Article |
|---|---|---|
| `evoproto.data` | provenance record with five tags; `stable_seed()` (blake2b over package version, task, arm, replicate); offline-by-default OTOL / PBDB / MorphoBank connectors; Eqs. (1)–(2) | 3 |
| `evoproto.kg` | `EvoKG` multigraph with schema enforcement; `evidence_chain()` (Eq. 4); `independent_origins()` (Eq. 3) by union–find over homology edges | 4.2 |
| `evoproto.phylo` | Brownian covariance and simulation; Blomberg's *K* (Eq. 5); profile-likelihood *λ* (Eq. 6); ML ancestral states; Stayton's *C1* (Eq. 7) with a Brownian null (Eq. A.2) | 4.3 |
| `evoproto.retrieval` | `AnalogCandidate`; `transfer_uncertainty()` (Eqs. 9–10); `score_analog()` (Eq. 8) | 4.4 |
| `evoproto.design` | parametric EOAT bracket and analytic evaluator (Eqs. 15–19); the three samplers of the arms | 6 |
| `evoproto.optimize` | non-dominated sorting with Deb's constraint domination, crowding distance, exact two-objective hypervolume (Eq. A.3), design diversity, Algorithm 1 | 4.5 |
| `evoproto.gate` | `evidence_score()` (Eq. 13); `decide()` (Eq. 14, Algorithm 2) with the abstention report | 4.6 |
| `evoproto.experiment` | three arms × tasks × replicates runner; Wilcoxon, Holm, Cliff's δ, bootstrap CI; Eq. (24) | 7 |
| `evoproto.figures` | regenerates Figures 1–8 from code | — |
| `evoproto.tools` | `verify_dois.py`: CrossRef check of every DOI in the reference list | — |

Three choices matter for reproducibility, and each has a test:

1. **Seeds are derived with blake2b**, not with Python's per-process-randomized
   `hash`, so replicates reproduce across machines and arms never share a stream.
2. **Every result dictionary carries its evaluator's provenance tag**, so a
   MODELED analytic number cannot be mistaken for a MEASURED one.
3. **The demonstration pipeline is SYNTHETIC-only**, so the software can be
   audited offline while the corpus is assembled under its licenses.

## What is deliberately *not* implemented

- The **retrieval language model** of Section 4.4. The framework specifies its
  guard (citations restricted to the retrieved subgraph and its DOI-backed
  excerpts; anything else discarded), and the protocol requires the model
  identifier and prompts to be archived — but no model is bundled or called here.
- **Tasks T2 and T3** (heat-exchanger fin, compliant gripper finger). They are
  registered and raise `NotImplementedError`: their evaluators are to be built
  with the industrial partner's CFD and contact-mechanics solvers.
- **Finite-element verification.** The analytic evaluator is a surrogate that
  makes the protocol executable end to end; it ignores shear deformation, stress
  concentration, LPBF anisotropy and lattice discreteness, and the FE stage
  replaces it before any physical build.

## Repository layout

```
src/evoproto/      the package (one module per article section)
tests/             106 tests: seeding, schema, chains, K/lambda/C1, Pareto/HV, gate, protocol
docs/              datasheet, model card, pre-registration, reproducibility,
                   article-to-code map, Elsevier checklist, Zenodo instructions
docs/publication/  ready-to-paste declarations and highlights
notebooks/         three Colab-ready notebooks
figures/           regenerated figures (PDF + PNG)
results/dry_run/   archived dry-run output with its environment record
scripts/           the Zenodo archive builder
```

Start with [`docs/paper_mapping.md`](docs/paper_mapping.md): it maps every
equation, algorithm, table and figure to the code and the test that pins it, and
lists the **open items** the authors must close before submission.

## Building the Zenodo archive

```bash
make all       # tests, dry run, figures
make zenodo    # dist-zenodo/evoproto-v0.1.0.zip with manifest and SHA-256 sums
```

See [`docs/zenodo_deposit.md`](docs/zenodo_deposit.md) for the deposit walk-through
(reserve the DOI *before* publishing; it goes into the Data availability statement).

## Citing

See [`CITATION.cff`](CITATION.cff). Cite both the software (version DOI) and the
article.

## License

MIT for the software; CC BY 4.0 for documentation and figures
([`LICENSE-DOCS`](LICENSE-DOCS)). Records retrieved from Open Tree of Life,
MorphoBank and the Paleobiology Database remain under their own licenses and are
**not** redistributed here — see [`docs/datasheet.md`](docs/datasheet.md).
