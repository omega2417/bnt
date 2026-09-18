# Datasheet for the evoproto corpus

Following *Datasheets for Datasets* (Gebru et al., 2021) [55], as required by
Section 3.1 of the article. This datasheet describes the corpus the framework
is designed to consume and the synthetic data the package actually ships.

## Motivation

**For what purpose was the dataset created?** To turn curated evolutionary data
— phylogenies, morphological character matrices, fossil occurrences and
DOI-backed mechanism measurements — into structured constraints on AI-driven
generation of technological prototypes, with provenance preserved end to end.

**Who created it and who funded it?** The authors of the accompanying article;
financial support from Halmstad University, Sweden.

## Composition

**What do the instances represent?** Six node types (Organism, Environment,
Trait, Function, Mechanism, EngParameter) and nine typed relations between
them, each edge carrying a provenance record `p = (source, version, license,
r, u)` and a support weight `w ∈ [0, 1]`.

**What is shipped with this package?** **No biological records at all.** The
repository contains only synthetic structures (`kg.demo_graph`,
`phylo.random_ultrametric_tree`, `phylo.induce_convergence`) tagged SYNTHETIC,
so the software can be executed and audited offline while the corpus is
assembled under its licenses. Every table and figure generated here is marked
SYNTHETIC or MODELED.

**Planned sources** (Table 2 of the article):

| Source | Role | Access | Provenance fields recorded |
|---|---|---|---|
| Open Tree of Life [48, 49] | phylogenetic backbone, name resolution, induced subtrees | API v3 (`tnrs/match_names`, `tree_of_life/induced_subtree`) | synthetic-tree version, OTT ids, source-tree citations, retrieval date |
| MorphoBank [50, 51] | morphological character states, images | per-project matrix download (NEXUS/TNT) | project id, matrix version, character definitions, license |
| Paleobiology Database [52, 53] | fossil occurrences, stratigraphic age, palaeo-environment | data service v1.2 (`occs/list`) | record id, reference id, age model, license (CC BY) |
| Experimental literature | mechanism-level measurements | manual curation | DOI, measurement type, sample size, reported uncertainty |

**Is any information missing?** Yes, structurally: coverage is biased towards
well-studied clades and towards mechanisms with published measurements. The
sampling weight of Eq. (2) corrects the *count* of independent origins; it
cannot correct for mechanisms nobody has measured (Section 8.3).

**Does the corpus contain data that might be considered confidential or
sensitive?** No. All sources are public scientific resources; no personal data
are involved.

## Collection process

Five curation operations are mandatory before a record enters the graph
(Section 3.2), and each is checkable:

1. **Taxonomic reconciliation** — every name resolved to an OTT identifier, so
   one taxon is one node regardless of nomenclatural history.
2. **Trait standardization** — character states mapped to a controlled
   vocabulary with units; continuous traits stored with units and, where
   reported, standard errors.
3. **Observation versus reconstruction** — reconstructed ancestral states carry
   `r = 1`, the reconstruction method and its confidence interval, and are
   down-weighted by Eq. (13). `data.Provenance` refuses to build a
   reconstructed record without a method.
4. **Missing-data control** — Eq. (1); a record enters retrieval only if
   `c ≥ c_min` for the characters that participate in the query. `c_min` is a
   corpus-level hyperparameter and **must be recorded here** when the corpus is
   assembled: `c_min = NEEDS INPUT`.
5. **Sampling-bias control** — Eq. (2) with reference sampling fraction
   `f_ref = 0.1` in this implementation: `f_ref = NEEDS INPUT (confirm)`.

**Connectors are offline by default.** `data.Connector.fetch` raises
`OfflineAccessError` unless the connector was explicitly constructed with
`allow_network=True`, so corpus assembly is a deliberate, logged, licensed act
rather than a side effect of importing the package.

## Preprocessing, cleaning, labeling

Corpus snapshots are content-addressed (`data.corpus_snapshot_hash`, blake2b
over canonically serialized records), and every recommendation refers to the
snapshot hash under which it was generated. Feedback from physical tests
changes **weights and priors only**; the biological records themselves are
never modified (Section 4.7), and each weight update keeps its predecessor in
the edge history.

## Uses

**What is the corpus meant for?** Retrieving and scoring biological analogs for
an engineering functional requirement, with the strength of evidence and the
uncertainty of cross-domain transfer as first-class quantities.

**What should it not be used for?** It must not be used to assert that a
biological form is optimal, nor to skip numerical verification or physical
testing. Convergence raises confidence; it never replaces a test (Section 8.3).

## Distribution and licensing

The software is MIT-licensed; this documentation is CC BY 4.0. Retrieved
records remain under the licenses of their sources — PBDB is CC BY 4.0, OTOL's
synthetic tree is CC0 while source trees keep their own terms, and MorphoBank
matrices are licensed per project. **Do not redistribute retrieved records
without checking each source's terms**, and record the license in the
provenance field of every record you do redistribute.

## Maintenance

Maintainer: Dmytro Prokopovych-Tkachenko (see `CITATION.cff`). Errors in the
corpus are corrected by adding a new versioned snapshot, never by editing a
published one; the snapshot hash makes the change visible.
