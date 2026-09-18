# Datasheet for the evoproto corpus specification

Following Gebru et al., *Datasheets for Datasets* (Commun. ACM 64 (2021) 86–92,
https://doi.org/10.1145/3458723). This datasheet describes the corpus the
framework **specifies** (Section 3 of the paper) and the synthetic data the
package **ships**. They are different things, and the distinction matters:

> **The package bundles no biological records.** Everything executable here is
> tagged `SYNTHETIC`. This datasheet states what a real deployment must record
> before any recommendation is made.

## Motivation

The corpus exists to turn evolutionary evidence into structured constraints on
AI-driven engineering design, in a form where the strength of that evidence can
be queried, weighted and audited. It was specified by the authors of the paper;
funding for the publication came from Halmstad University, Sweden.

## Composition

| source | role | access | provenance fields recorded |
|---|---|---|---|
| Open Tree of Life | phylogenetic backbone, name resolution, induced subtrees | API v3 (`tnrs/match_names`, `tree_of_life/induced_subtree`) | synthetic-tree version, OTT ids, source-tree citations, retrieval date |
| MorphoBank | morphological character states per taxon, images | per-project matrix download (NEXUS/TNT) | project id, matrix version, character definitions, licence |
| Paleobiology Database | fossil occurrences, stratigraphic age, palaeo-environment | data service v1.2 (`occs/list`) | record id, reference id, age model, licence (CC BY) |
| experimental literature | mechanism-level measurements | manual curation | DOI, measurement type, sample size, reported uncertainty |

The corpus is a selection, not a chronicle: it is biased toward well-studied
clades and toward mechanisms with published measurements. Eq. (2) corrects the
count of independent origins for uneven sampling; it does not correct for
mechanisms nobody has studied.

Each record carries `π = (source, version, licence, tag, uri, date, r, u)` where
`r` flags a reconstructed ancestral state and `u` is an uncertainty estimate.
The tag is one of `MEASURED`, `MODELED`, `PROXY`, `EXTERNAL`, `SYNTHETIC` and
propagates to every metric computed from the record — a derived quantity
inherits the weakest tag of its inputs.

## Collection and curation

Five operations are mandatory before a record enters the knowledge graph:

1. **Taxonomic reconciliation** — names resolved to OTT identifiers, so one
   taxon is one node regardless of nomenclatural history.
2. **Trait standardisation** — character states mapped to a controlled
   vocabulary with units; continuous traits stored with units and standard
   errors where reported.
3. **Observation versus reconstruction** — reconstructed states carry the
   method and its confidence interval and are down-weighted by `ρ_rec = 0.7`
   in Eq. (13).
4. **Missing-data control** — a record enters retrieval only if `c_i ≥ c_min`
   over the characters participating in the query (Eq. 1). **`c_min` is a
   corpus-level hyperparameter and must be recorded here by the deployment.**
5. **Sampling-bias control** — `w_k = min(1, n_obs/n̂)` per clade (Eq. 2).

## Coarse lookup tables used by Eq. (9)

These tables are deliberately coarse and belong to the corpus, not to the
method; a deployment replaces them and records the replacement here. Their
values in the shipped code are in `evoproto.retrieval`.

**Table D1 — material behaviour classes** (`u_mat` is the absolute difference
of the two positions): monolithic isotropic 0.00, mineralised foam 0.25,
printed lattice 0.30, fibre composite 0.55, hierarchical composite 0.80,
viscoelastic 1.00.

**Table D2 — loading regimes** (`u_load` likewise): static 0.00, quasi-static
0.15, intermittent inertial 0.35, cyclic 0.55, impact 1.00.

Section 9 notes that both tables could be learned from the accumulated
`MEASURED` records instead of being hand-curated; until they are, they are
assumptions and are labelled as such.

## Uses

Intended: evidence-gated retrieval and weighting of biological analogs for
engineering design, with a traceability chain exposed for every recommendation.

**Not intended**: the corpus does not support claims about optimality. Natural
selection optimises locally under historical contingency; a convergent mechanism
is evidence of repeated adequacy, not of optimality, and convergence is used to
raise confidence, never to skip verification.

## Distribution and maintenance

Corpus snapshots are content-addressed (blake2b over the canonical JSON), and a
recommendation refers to the snapshot hash under which it was generated. The
underlying resources carry their own licences — PBDB is CC BY, MorphoBank is
per project, Open Tree of Life is documented on its site — and this package
neither redistributes nor relicenses any of their data. Physical test results
are written back as new `MEASURED` records attached to the `mapsTo` edge; the
system never modifies the biological records themselves, only weights and
priors (Section 4.7).

## What the package actually ships

A hand-built demonstration graph (`evoproto.casestudy.build_demo_kg`) with four
organisms, four traits, two functions, one mechanism and one engineering
parameter, plus synthetic trees and traits generated on demand. Its support
weights are plausible placeholders. Nothing in it is evidence about birds,
bamboos or sea urchins, and every value it produces is tagged `SYNTHETIC`.
