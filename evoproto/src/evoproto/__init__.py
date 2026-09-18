"""evoproto: reference implementation of the evolution-informed design framework.

The package realises the framework of "From Evolutionary Biology Data to
Technological Prototypes: An AI-Driven Engineering Design Framework with an
Evidence-Gated Validation Protocol".  Module layout mirrors the paper:

===================  ==========================================  =========
module               content                                     section
===================  ==========================================  =========
``evoproto.data``    provenance, stable seeding, curation,        3
                     source connectors
``evoproto.kg``      the EE-KG, Eq. (3) and Eq. (4)              4.2
``evoproto.phylo``   K, lambda, C1 and its p-value               4.3
``evoproto.retrieval`` Eqs. (8)-(10) and the grounding filter    4.4
``evoproto.design``  parametric bracket, Eqs. (15)-(19)          6
``evoproto.optimize`` Algorithm 1, Eqs. (12), (20)-(23)          4.5
``evoproto.gate``    Eqs. (13)-(14), Algorithm 2                 4.6
``evoproto.casestudy`` the case study end to end                 6
``evoproto.experiment`` protocol runner and analysis plan        7
``evoproto.figures`` regenerates every figure                    -
``evoproto.tools``   DOI verification                            -
===================  ==========================================  =========

The package runs in SYNTHETIC mode: no biological records are bundled, and the
source connectors do not touch the network unless a caller opts in.
"""

from __future__ import annotations

from .data import (
    PACKAGE_VERSION,
    CorpusSnapshot,
    Provenance,
    ProvenanceTag,
    stable_seed,
)
from .gate import Decision, GateThresholds, decide, evidence_score
from .kg import EdgeType, EvidenceChain, EvoKG, NodeType
from .retrieval import AnalogCandidate, rank_analogs, score_analog, transfer_uncertainty

__version__ = PACKAGE_VERSION

__all__ = [
    "__version__",
    "PACKAGE_VERSION",
    "Provenance",
    "ProvenanceTag",
    "CorpusSnapshot",
    "stable_seed",
    "EvoKG",
    "NodeType",
    "EdgeType",
    "EvidenceChain",
    "AnalogCandidate",
    "score_analog",
    "rank_analogs",
    "transfer_uncertainty",
    "evidence_score",
    "decide",
    "Decision",
    "GateThresholds",
]
