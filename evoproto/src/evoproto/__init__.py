"""evoproto - reference implementation of the evolution-informed design framework.

The package accompanies the article

    O. Torstensson, Y. Danyk, D. Prokopovych-Tkachenko,
    "From Evolutionary Biology Data to Technological Prototypes: An AI-Driven
    Engineering Design Framework with an Evidence-Gated Validation Protocol".

Module layout mirrors the article (Table 5):

===================  ==========================================================
Module               Article section
===================  ==========================================================
evoproto.data        3 - provenance, stable seeding, source connectors
evoproto.kg          4.2 - evolutionary-engineering knowledge graph
evoproto.phylo       4.3 - phylogenetic signal, convergence, independence
evoproto.retrieval   4.4 - analog scoring and transfer uncertainty
evoproto.design      6 - parametric EOAT bracket and analytic evaluator
evoproto.optimize    4.5 - constrained multi-objective search (Algorithm 1)
evoproto.gate        4.6 - evidence score and abstention (Algorithm 2)
evoproto.experiment  7 - three-arm protocol runner and statistics
evoproto.figures     figure regeneration
evoproto.tools       auxiliary tools (DOI verification)
===================  ==========================================================

Every numeric artifact produced by this package carries a provenance tag
(:class:`evoproto.data.Tag`).  The bundled demonstration pipeline runs in
SYNTHETIC mode only: no biological records are distributed with the package.
"""

from evoproto.data import (
    Provenance,
    Tag,
    completeness,
    corpus_snapshot_hash,
    sampling_weight,
    stable_seed,
)
from evoproto.gate import Decision, EvidenceWeights, Thresholds, decide, evidence_score
from evoproto.kg import EdgeType, EvoKG, NodeType
from evoproto.retrieval import (
    AnalogCandidate,
    ScoreWeights,
    UncertaintyWeights,
    score_analog,
    transfer_uncertainty,
)

__version__ = "0.1.0"

__all__ = [
    "AnalogCandidate",
    "Decision",
    "EdgeType",
    "EvidenceWeights",
    "EvoKG",
    "NodeType",
    "Provenance",
    "ScoreWeights",
    "Tag",
    "Thresholds",
    "UncertaintyWeights",
    "__version__",
    "completeness",
    "corpus_snapshot_hash",
    "decide",
    "evidence_score",
    "sampling_weight",
    "score_analog",
    "stable_seed",
    "transfer_uncertainty",
]
