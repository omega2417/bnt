# evoproto

Reference implementation of the framework described in

> **From Evolutionary Biology Data to Technological Prototypes: An AI-Driven
> Engineering Design Framework with an Evidence-Gated Validation Protocol**
> Olga Torstensson, Yuriy Danyk, Dmytro Prokopovych-Tkachenko

The paper proposes a path from curated evolutionary data — phylogenies,
morphological character matrices, fossil occurrences and DOI-backed mechanism
measurements — to verified technological prototypes, in which every
recommendation exposes a traceability chain and the system **abstains** when the
biological evidence is too weak or the cross-domain transfer too uncertain.

`evoproto` is the software half of that proposal: it implements every equation,
both algorithms, the case study and the pre-registered protocol, and it
regenerates the figures of the paper from code.

> **No biological records are bundled.** The package runs in `SYNTHETIC` mode
> and its source connectors do not touch the network unless a caller opts in,
> so the whole pipeline can be executed and audited offline while the corpus of
> Section 3 is assembled under its licences.

---

## Install

```bash
python -m pip install -e ".[dev]"     # from the directory containing pyproject.toml
```

Dependencies are deliberately light — NumPy, SciPy, NetworkX, Matplotlib — so a
reviewer can execute the protocol code without proprietary tools. Python 3.9 or
newer.

## Start here: the walkthrough notebook

[`notebooks/evoproto_walkthrough.ipynb`](notebooks/evoproto_walkthrough.ipynb)
runs the whole framework end to end with explanations and 17 plots — provenance
and curation, the knowledge graph drawn as a graph, phylogenetic signal and a
convergence p-value, analog scoring decomposed term by term, the feasible region
of the design space, the three search arms, the decision map, the statistical
plan and the ablations. About two minutes on a free Colab runtime, and it
installs the package itself.

[![Open In Colab](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/github/omega2417/bnt/blob/claude/software-project-publication-lz9nuu/evoproto/notebooks/evoproto_walkthrough.ipynb)

It is also the quickest way to see the two observations the ablations turned up:
the sampling correction of Eq. (2) leaves the convergence bonus contributing
about 1 % of the evidence score, and with uniform edge weights a single
unsupported edge cannot pull `E` below `τ_E`. Both are properties of the
specification worth settling in the pre-registration.

## Run it

```bash
evoproto info          # mode and every pre-registered constant
evoproto case-study    # Section 6: retrieval -> search -> verification -> gate
evoproto dry-run       # Section 7.7: the protocol on synthetic arms (~5 s)
evoproto ablation      # Section 7.5: arm C with one source of value removed
evoproto figures       # regenerate Figs. 1-8 into ./figures
evoproto verify-dois   # CrossRef check of the reference list (offline by default)
pytest                 # the test suite
make notebook          # execute the walkthrough notebook end to end (needs nbclient)
```

Every command takes `--out FILE` (or `--outdir`) and emits provenance-tagged
JSON, so results can be archived alongside the corpus snapshot hash that
produced them. `verify-dois` only lists what it would check until you pass
`--online`, which needs outbound access to `api.crossref.org`; in a sandbox
without it, the tool reports each DOI as unresolved with the network error
rather than pretending to have checked it.

## What is in here

| module | content | paper |
|---|---|---|
| `evoproto.data` | provenance record with five tags, `stable_seed()` (blake2b over package version, task, arm, replicate), completeness and sampling-weight controls, content-addressed snapshots, OTOL v3 / PBDB v1.2 / MorphoBank connectors | §3, Eqs. (1)–(2) |
| `evoproto.kg` | `EvoKG` multigraph with schema enforcement, mutually exclusive homology/convergence, `independent_origins()` by union–find, `evidence_chains()`, block split, ablation views | §4.2, Eqs. (3)–(4) |
| `evoproto.phylo` | Brownian-motion simulation and VCV, Blomberg's K, profile-likelihood Pagel's λ, two-pass ML ancestral states, Stayton's C1 and its simulation p-value | §4.3, Eqs. (5)–(7), (A.1)–(A.2) |
| `evoproto.retrieval` | `AnalogCandidate`, `transfer_uncertainty()`, `score_analog()`, and the filter that discards LLM statements citing material outside the retrieved subgraph | §4.4, Eqs. (8)–(10) |
| `evoproto.design` | parametric EOAT bracket and analytic evaluator, the three arm priors | §6, Eqs. (15)–(19) |
| `evoproto.optimize` | non-dominated sorting with Deb's constraint domination, crowding distance, exact two-objective hypervolume, design diversity, Algorithm 1 | §4.5, Eqs. (12), (20)–(23), (A.3) |
| `evoproto.gate` | `evidence_score()`, `decide()`, and the missing-evidence report | §4.6, Eqs. (13)–(14), Algorithm 2 |
| `evoproto.casestudy` | the EOAT bracket end to end, producing the per-prototype deliverable | §6.3–6.4 |
| `evoproto.experiment` | arms × tasks × replicates runner, Wilcoxon signed-rank, Holm, Cliff's δ, bootstrap CI, sample size, dry run, ablations | §7 |
| `evoproto.figures` | regenerates Figs. 1–8 | — |
| `evoproto.tools.verify_dois` | CrossRef check of every DOI in the reference list | — |
| `notebooks/` | the Colab walkthrough: every section of the paper, run and plotted | all |

`docs/paper_mapping.md` maps each numbered equation to the function that
implements it and to the test that checks it.

## Three design decisions worth knowing about

**Seeds are derived with blake2b, not `hash()`.** Python's built-in hash is
randomised per process, so a seed derived from it is not reproducible across
machines. `stable_seed(task, arm, replicate)` hashes the tuple
`(package version, task id, arm, replicate)`, which makes every replicate
reproducible and prevents silent seed collisions between arms.

**Every result carries the provenance tag of its evaluator.** A `MODELED`
analytic result cannot be tabulated as a `MEASURED` one; a quantity derived
from several records inherits the weakest tag of those records.

**The gate can decline.** `decide()` returns `RECOMMEND`, `ABSTAIN` or
`REJECT`. An abstention is not an empty result: it names the weakest edge of the
traceability chain, the component of the transfer uncertainty that exceeded its
budget, and the experiment that would raise the score. Final approval always
rests with the engineer — `RECOMMEND` is a recommendation awaiting approval,
never a release.

## Reproducing the dry run of Section 7.7

`evoproto dry-run` executes task T1 with three arms, ten seeded replicates,
population 40 and 25 generations, then applies the full analysis plan. It takes
about five seconds on a laptop-class processor:

```
cell                 FSR              HV               D             ITS
------------------------------------------------------------------------
T1/A         0.247 ± 0.092     0.008 ± 0.002     0.027 ± 0.009     8.500 ± 4.327
T1/B         1.000 ± 0.000     0.479 ± 0.003     0.080 ± 0.004     2.000 ± 1.247
T1/C         1.000 ± 0.000     0.482 ± 0.001     0.074 ± 0.005     1.000 ± 0.000

  C vs B  HV   p_holm = 0.0391  delta = +0.82 (large)
  C vs B  D    p_holm = 0.1703  delta = -0.64 (large)
  C vs A  FSR  p_holm = 0.0346  delta = +1.00 (large)
  C vs A  ITS  p_holm = 0.0346  delta = -1.00 (large)
```

**These numbers test the pipeline, not the hypothesis.** All three arms are
synthetic: arm A is a template-ratio sampler standing in for human designers and
the analog-shaped prior of arm C is hand-set, not derived from a curated EE-KG.
The run is reported to show that the statistical plan produces significant,
non-significant and negative-direction results as appropriate — note that the
synthetic arm C is *not* more diverse than arm B, exactly the kind of outcome
the real experiment must be able to report. No inference about H1–H3 follows.

The values differ in the third decimal from Table 7 of the manuscript, which was
produced by the authors' original run; the qualitative pattern — arm A weak and
highly variable, arms B and C both fully feasible with C slightly ahead on
hypervolume and not ahead on diversity — is reproduced. Anyone re-running this
command on any machine gets the numbers above, because the seeds are content-
derived.

## Checks that anchor the implementation

The test suite is not only a regression net; several tests check the code
against results that are known analytically:

- Blomberg's K has expectation 1 under Brownian motion on a given tree
  (Appendix A.1) — verified over 300 simulated traits.
- The two-pass ancestral-state reconstruction agrees to machine precision with
  the joint maximum-likelihood solution obtained by solving the quadratic
  program directly.
- The exact two-objective hypervolume matches a hand-computed staircase case
  (Appendix A.3).
- The Wilcoxon signed-rank p-values match SciPy on both the exact and the
  tie-corrected normal branch.
- The sample-size formula returns the 9 and 13 pairs quoted in Section 7.6.
- Uniform sampling of the design box yields a feasible fraction near 1 %, as
  Section 6.2 reports.
- The case-study transfer uncertainty is U ≈ 0.38 < τ_U = 0.5, as Section 6.3
  reports.

## Limitations

The analytic evaluator is a surrogate: it ignores shear deformation, stress
concentration at the flange, anisotropy of the LPBF material and the
discreteness of a real lattice. Its role is to make the protocol executable end
to end; the FE stage of Section 4.6 replaces it before any physical build, and
the `verification` step in `casestudy` is an explicitly tagged stand-in for that
stage, not a substitute for it. Task T1 is the only task with a fully specified
evaluator — the T2 heat-exchanger fin and T3 gripper evaluators are marked
`NEEDS INPUT` and raise `NotImplementedError` rather than silently returning
something. The comparative measures are implemented here so the package stays
dependency-light; production use should substitute `ape` or `phytools`, and
`pymoo` for the search.

The demonstration knowledge graph is hand-built. Its support weights are
plausible placeholders, not curated evidence, and the biological content is an
illustration of the schema — nothing in it should be read as a claim about
birds, bamboos or sea urchins.

## Citing

See `CITATION.cff`. Please cite both the software archive and the article.

## Licence

MIT — see `LICENSE`. The public evolutionary resources the connectors address
carry their own licences (PBDB: CC BY; MorphoBank: per project; Open Tree of
Life: see its documentation), and this package neither redistributes nor
relicenses any of their data.
