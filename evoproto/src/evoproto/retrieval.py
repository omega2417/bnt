"""Analog retrieval and transfer uncertainty (Section 4.4).

* Eq. (8)   the analog score
  ``S(c) = w_F F(c) + w_M M(c) + w_C ln(1 + N^w_conv(c)) - w_U U(c)``
  with the pre-registered defaults ``w_F = 0.4``, ``w_M = 0.3``, ``w_C = 0.15``,
  ``w_U = 0.4``;
* Eq. (9)   ``U = alpha u_scale + beta u_mat + gamma u_load`` with
  ``alpha = beta = 0.35``, ``gamma = 0.30``;
* Eq. (10)  ``u_scale = 1 - exp(-|log10(l_eng / l_bio)|)``, so one decade of
  scale mismatch gives 0.63 and two decades 0.86;
* the grounding rule of the retrieval-augmented stage: a statement citing
  material outside the retrieved subgraph is discarded.  This is the concrete
  mitigation of hallucination, and it is deliberately a filter rather than a
  prompt instruction.

The material and load tables are small, curated and deliberately coarse; they
belong to the corpus datasheet, not to the code, and are exposed here so that a
deployment can replace them without touching the scoring logic.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Dict, Iterable, List, Mapping, Optional, Sequence, Set, Tuple

from .data import Provenance, ProvenanceTag

__all__ = [
    "RetrievalWeights",
    "TransferWeights",
    "MATERIAL_CLASSES",
    "LOAD_REGIMES",
    "material_mismatch",
    "load_mismatch",
    "u_scale",
    "transfer_uncertainty",
    "AnalogCandidate",
    "score_analog",
    "rank_analogs",
    "GroundedStatement",
    "filter_grounded_statements",
]


@dataclass(frozen=True)
class RetrievalWeights:
    """Weights of Eq. (8).  Fixed before the experiment and reported (Section 7)."""

    w_F: float = 0.40
    w_M: float = 0.30
    w_C: float = 0.15
    w_U: float = 0.40

    def as_dict(self) -> Dict[str, float]:
        return {"w_F": self.w_F, "w_M": self.w_M, "w_C": self.w_C, "w_U": self.w_U}


@dataclass(frozen=True)
class TransferWeights:
    """Weights of Eq. (9); they must sum to one."""

    alpha: float = 0.35
    beta: float = 0.35
    gamma: float = 0.30

    def __post_init__(self) -> None:
        total = self.alpha + self.beta + self.gamma
        if abs(total - 1.0) > 1e-9:
            raise ValueError(f"alpha + beta + gamma must equal 1, got {total}")

    def as_dict(self) -> Dict[str, float]:
        return {"alpha": self.alpha, "beta": self.beta, "gamma": self.gamma}


#: Behaviour classes of the material term of Eq. (9), ordered by how far the
#: mechanical response is from a monolithic isotropic solid.  Distances are
#: normalised differences of position on this coarse scale (datasheet Table D1).
MATERIAL_CLASSES: Dict[str, float] = {
    "monolithic_isotropic": 0.0,     # wrought or printed metal, bulk polymer
    "mineralised_foam": 0.25,        # echinoid stereom, trabecular bone
    "printed_lattice": 0.30,         # LPBF or MJF cellular core
    "fibre_composite": 0.55,         # laminate, unidirectional composite
    "hierarchical_composite": 0.80,  # bamboo culm, cortical bone, nacre
    "viscoelastic": 1.00,            # soft tissue, elastomer
}

#: Loading regimes of the load term of Eq. (9) (datasheet Table D2).
LOAD_REGIMES: Dict[str, float] = {
    "static": 0.0,
    "quasi_static": 0.15,
    "intermittent_inertial": 0.35,
    "cyclic": 0.55,
    "impact": 1.00,
}


def material_mismatch(biological: str, engineering: str) -> float:
    """``u_mat``: coarse distance between two material behaviour classes."""
    try:
        a, b = MATERIAL_CLASSES[biological], MATERIAL_CLASSES[engineering]
    except KeyError as exc:  # pragma: no cover - defensive
        raise KeyError(f"unknown material class {exc.args[0]!r}; see MATERIAL_CLASSES") from exc
    return abs(a - b)


def load_mismatch(biological: str, engineering: str) -> float:
    """``u_load``: coarse distance between two loading regimes."""
    try:
        a, b = LOAD_REGIMES[biological], LOAD_REGIMES[engineering]
    except KeyError as exc:  # pragma: no cover - defensive
        raise KeyError(f"unknown load regime {exc.args[0]!r}; see LOAD_REGIMES") from exc
    return abs(a - b)


def u_scale(length_engineering: float, length_biological: float) -> float:
    r"""Eq. (10): :math:`u_{\mathrm{scale}} = 1 - \exp(-|\log_{10}(\ell_{\mathrm{eng}}/\ell_{\mathrm{bio}})|)`.

    The two lengths are characteristic lengths in the same unit.  One decade of
    mismatch yields 0.632, two decades 0.865: naive geometric transfer across
    orders of magnitude fails because surface-to-volume ratios, buckling loads
    and viscous-versus-inertial regimes all change with size.
    """
    if length_engineering <= 0 or length_biological <= 0:
        raise ValueError("characteristic lengths must be positive")
    decades = abs(math.log10(length_engineering / length_biological))
    return float(1.0 - math.exp(-decades))


def transfer_uncertainty(
    length_engineering: float,
    length_biological: float,
    material_biological: str,
    material_engineering: str,
    load_biological: str,
    load_engineering: str,
    weights: TransferWeights = TransferWeights(),
) -> Tuple[float, Dict[str, float]]:
    r"""Eq. (9): transfer uncertainty ``U`` and its three components.

    Returns ``(U, components)`` where ``components`` holds ``u_scale``,
    ``u_mat`` and ``u_load`` so that an abstention report can name the term that
    exceeded its budget (Algorithm 2, line 7).
    """
    components = {
        "u_scale": u_scale(length_engineering, length_biological),
        "u_mat": material_mismatch(material_biological, material_engineering),
        "u_load": load_mismatch(load_biological, load_engineering),
    }
    U = (
        weights.alpha * components["u_scale"]
        + weights.beta * components["u_mat"]
        + weights.gamma * components["u_load"]
    )
    return float(U), components


@dataclass
class AnalogCandidate:
    """A candidate biological analog with everything Eq. (8) needs.

    Attributes
    ----------
    functional_match:
        ``F(c)`` in ``[0, 1]``: cosine similarity of the query to the Function
        node, as returned by the multimodal encoder.
    mechanism_evidence:
        ``M(c)`` in ``[0, 1]``: the fraction of chain edges (Eq. 4) whose
        support derives from experimental measurement rather than inference.
    n_conv_weighted:
        ``N^w_conv``: sampling-weighted number of independent origins (Eq. 3).
    """

    identifier: str
    name: str
    functional_match: float
    mechanism_evidence: float
    n_conv_weighted: float
    length_biological: float
    length_engineering: float
    material_biological: str
    material_engineering: str
    load_biological: str
    load_engineering: str
    mechanism: str = ""
    clade: str = ""
    provenance: Optional[Provenance] = None
    citations: Tuple[str, ...] = ()

    def __post_init__(self) -> None:
        for field_name in ("functional_match", "mechanism_evidence"):
            value = float(getattr(self, field_name))
            if not 0.0 <= value <= 1.0:
                raise ValueError(f"{field_name} must lie in [0, 1], got {value}")
        if self.n_conv_weighted < 0:
            raise ValueError("N^w_conv must be non-negative")

    def transfer_uncertainty(self, weights: TransferWeights = TransferWeights()) -> Tuple[float, Dict[str, float]]:
        return transfer_uncertainty(
            self.length_engineering,
            self.length_biological,
            self.material_biological,
            self.material_engineering,
            self.load_biological,
            self.load_engineering,
            weights=weights,
        )


def score_analog(
    candidate: AnalogCandidate,
    weights: RetrievalWeights = RetrievalWeights(),
    transfer_weights: TransferWeights = TransferWeights(),
) -> Dict[str, object]:
    r"""Eq. (8): score one candidate analog.

    The logarithm reflects diminishing returns: the third independent origin of
    a mechanism adds less confidence than the second.  Returns the score with
    its decomposition and the provenance tag it inherits, so that a MODELED
    score can never be tabulated as a MEASURED one.
    """
    U, components = candidate.transfer_uncertainty(transfer_weights)
    convergence_term = math.log1p(float(candidate.n_conv_weighted))
    score = (
        weights.w_F * candidate.functional_match
        + weights.w_M * candidate.mechanism_evidence
        + weights.w_C * convergence_term
        - weights.w_U * U
    )
    tag = candidate.provenance.tag if candidate.provenance else ProvenanceTag.MODELED
    return {
        "identifier": candidate.identifier,
        "name": candidate.name,
        "score": float(score),
        "F": float(candidate.functional_match),
        "M": float(candidate.mechanism_evidence),
        "N_conv_weighted": float(candidate.n_conv_weighted),
        "convergence_term": float(convergence_term),
        "U": float(U),
        "U_components": components,
        "weights": weights.as_dict(),
        "transfer_weights": transfer_weights.as_dict(),
        "tag": tag.value,
    }


def rank_analogs(
    candidates: Sequence[AnalogCandidate],
    weights: RetrievalWeights = RetrievalWeights(),
    transfer_weights: TransferWeights = TransferWeights(),
) -> List[Dict[str, object]]:
    """Score every candidate and return them ordered by decreasing ``S``."""
    scored = [score_analog(c, weights, transfer_weights) for c in candidates]
    return sorted(scored, key=lambda d: (-float(d["score"]), str(d["identifier"])))


@dataclass(frozen=True)
class GroundedStatement:
    """A functional-correspondence statement produced by the retrieval LLM.

    ``citations`` are the identifiers (DOIs or edge ids) the statement relies
    on.  Only the excerpts attached to the retrieved subgraph are admissible.
    """

    candidate_id: str
    text: str
    citations: Tuple[str, ...]


def filter_grounded_statements(
    statements: Iterable[GroundedStatement],
    allowed_sources: Iterable[str],
) -> Tuple[List[GroundedStatement], List[GroundedStatement]]:
    """Discard statements citing material outside the retrieved set (Section 4.4).

    Returns ``(kept, discarded)``.  A statement with no citation at all is
    discarded as well: an ungrounded claim is exactly what this stage exists to
    remove, and the framework must not let it reach the engineer.
    """
    allowed: Set[str] = set(allowed_sources)
    kept: List[GroundedStatement] = []
    discarded: List[GroundedStatement] = []
    for statement in statements:
        citations = set(statement.citations)
        if citations and citations <= allowed:
            kept.append(statement)
        else:
            discarded.append(statement)
    return kept, discarded
