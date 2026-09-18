"""Analog retrieval scoring and transfer uncertainty (Section 4.4).

Retrieval itself is two-stage (multimodal embedding of the functional query,
then a retrieval-augmented language model restricted to the retrieved subgraph
and its DOI-backed excerpts).  The *scoring* stage, which is what determines
whether a candidate reaches the optimizer, is fully specified and implemented
here:

* :func:`transfer_uncertainty` - Eqs. (9)-(10): how far the biological source
  sits from the engineering target in scale, material class and load regime;
* :func:`score_analog` - Eq. (8): functional match, mechanism evidence and the
  logarithm of the number of independent origins, penalized by ``U``.

The logarithm in Eq. (8) reflects diminishing returns: the third independent
origin of a mechanism adds less confidence than the second.  All weights are
fixed before the experiment and reported (Section 7.8); the defaults below are
the reference implementation's, not a claim about their optimality.
"""

from __future__ import annotations

import math
from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any

__all__ = [
    "AnalogCandidate",
    "LOAD_REGIME_DISTANCE",
    "MATERIAL_CLASS_DISTANCE",
    "ScoreWeights",
    "UncertaintyWeights",
    "load_mismatch",
    "material_mismatch",
    "scale_mismatch",
    "score_analog",
    "transfer_uncertainty",
]

#: Coarse, curated distances between material behavior classes (Section 4.4).
#: Deliberately coarse: the table is a corpus artifact recorded in the
#: datasheet, and Section 9 proposes learning it from MEASURED records instead.
MATERIAL_CLASS_DISTANCE: dict[frozenset[str], float] = {
    frozenset({"hierarchical_composite", "monolithic_alloy"}): 0.8,
    frozenset({"hierarchical_composite", "polymer"}): 0.6,
    frozenset({"hierarchical_composite", "mineralized_foam"}): 0.3,
    frozenset({"hierarchical_composite", "fiber_composite"}): 0.2,
    frozenset({"mineralized_foam", "monolithic_alloy"}): 0.7,
    frozenset({"mineralized_foam", "cellular_metal"}): 0.3,
    frozenset({"viscoelastic", "monolithic_alloy"}): 0.9,
    frozenset({"viscoelastic", "polymer"}): 0.3,
    frozenset({"cellular_metal", "monolithic_alloy"}): 0.4,
    frozenset({"fiber_composite", "monolithic_alloy"}): 0.6,
}

#: Coarse, curated distances between loading regimes (Section 4.4).
LOAD_REGIME_DISTANCE: dict[frozenset[str], float] = {
    frozenset({"static", "quasi_static"}): 0.1,
    frozenset({"static", "cyclic"}): 0.5,
    frozenset({"static", "impact"}): 0.9,
    frozenset({"quasi_static", "cyclic"}): 0.4,
    frozenset({"quasi_static", "impact"}): 0.8,
    frozenset({"cyclic", "impact"}): 0.5,
    frozenset({"cyclic", "intermittent_inertial"}): 0.2,
    frozenset({"quasi_static", "intermittent_inertial"}): 0.4,
    frozenset({"static", "intermittent_inertial"}): 0.5,
    frozenset({"impact", "intermittent_inertial"}): 0.6,
}

SCALE_DECADES_TO_UNITY = 2.0
"""Decades of length-scale mismatch at which ``u_scale`` saturates at 1."""


def scale_mismatch(length_ratio: float, decades_to_unity: float = SCALE_DECADES_TO_UNITY) -> float:
    """Scale term ``u_scale`` of the transfer uncertainty (Eq. 10).

    ``length_ratio`` is the ratio of characteristic lengths between the
    engineering target and the biological source.  With the default, one decade
    of mismatch yields ``u_scale = 0.5`` and two decades ``u_scale = 1.0``.

    The term encodes the documented failure of naive geometric transfer across
    orders of magnitude [57-59]: surface-to-volume ratio, buckling loads and
    the viscous/inertial balance all change with size, so dimensional analysis
    [58], not shape copying, is the appropriate transfer instrument.
    """
    if length_ratio <= 0:
        raise ValueError("length_ratio must be positive")
    if decades_to_unity <= 0:
        raise ValueError("decades_to_unity must be positive")
    return float(min(1.0, abs(math.log10(length_ratio)) / decades_to_unity))


def _lookup(table: Mapping[frozenset[str], float], a: str, b: str, default: float) -> float:
    if a == b:
        return 0.0
    return float(table.get(frozenset({a, b}), default))


def material_mismatch(biological: str, engineering: str, default: float = 0.5) -> float:
    """Material term ``u_mat``: distance between material behavior classes."""
    return _lookup(MATERIAL_CLASS_DISTANCE, biological, engineering, default)


def load_mismatch(biological: str, engineering: str, default: float = 0.5) -> float:
    """Load term ``u_load``: mismatch in loading type and rate."""
    return _lookup(LOAD_REGIME_DISTANCE, biological, engineering, default)


@dataclass(frozen=True)
class UncertaintyWeights:
    """Weights of the three mismatch terms in Eq. (9).

    Defaults give scale and material equal say and load half as much, which
    matches the case study of Section 6.3 (biological and engineering lengths
    within one decade; hierarchical composite versus monolithic printed alloy).
    They are a pre-registered choice, not an estimate: freeze them before the
    experiment and report them (Section 7.8).
    """

    scale: float = 0.4
    material: float = 0.4
    load: float = 0.2

    def __post_init__(self) -> None:
        total = self.scale + self.material + self.load
        if abs(total - 1.0) > 1e-9:
            raise ValueError("uncertainty weights must sum to 1")
        if min(self.scale, self.material, self.load) < 0:
            raise ValueError("uncertainty weights must be non-negative")


@dataclass(frozen=True)
class ScoreWeights:
    """Weights of the analog score (Eq. 8).

    ``functional`` weights the functional match ``F``, ``mechanism`` the
    mechanism-evidence score ``M``, ``origins`` the logarithmic term in the
    sampling-weighted number of independent origins, and ``uncertainty`` the
    penalty on ``U``.
    """

    functional: float = 0.40
    mechanism: float = 0.30
    origins: float = 0.20
    uncertainty: float = 0.30

    def to_dict(self) -> dict[str, float]:
        return {
            "w_F": self.functional,
            "w_M": self.mechanism,
            "w_N": self.origins,
            "w_U": self.uncertainty,
        }


def transfer_uncertainty(
    length_ratio: float,
    material_biological: str,
    material_engineering: str,
    load_biological: str,
    load_engineering: str,
    weights: UncertaintyWeights | None = None,
) -> dict[str, float]:
    """Transfer uncertainty ``U`` and its three components (Eqs. 9-10).

    Returns a dictionary with ``u_scale``, ``u_mat``, ``u_load`` and the
    aggregate ``U`` in ``[0, 1]``, plus the name of the dominant term - which
    is what the abstention branch of Algorithm 2 reports when ``U > tau_U``.
    """
    weights = weights or UncertaintyWeights()
    u_scale = scale_mismatch(length_ratio)
    u_mat = material_mismatch(material_biological, material_engineering)
    u_load = load_mismatch(load_biological, load_engineering)
    u = weights.scale * u_scale + weights.material * u_mat + weights.load * u_load
    components = {"u_scale": u_scale, "u_mat": u_mat, "u_load": u_load}
    contributions = {
        "u_scale": weights.scale * u_scale,
        "u_mat": weights.material * u_mat,
        "u_load": weights.load * u_load,
    }
    dominant = max(contributions, key=lambda key: contributions[key])
    return {**components, "U": float(min(1.0, max(0.0, u))), "dominant": dominant}


@dataclass
class AnalogCandidate:
    """A candidate biological analog with everything Eq. (8) needs.

    Attributes
    ----------
    identifier, taxon, trait, mechanism:
        Identity of the candidate and the EE-KG nodes it points at.
    functional_match:
        ``F`` in ``[0, 1]``: cosine similarity of the query to the Function
        node, as returned by the first retrieval stage.
    mechanism_evidence:
        ``M`` in ``[0, 1]``: fraction of chain edges (Eq. 4) whose support
        derives from experimental measurement rather than inference.  Use
        :attr:`evoproto.kg.Chain.measured_fraction` to compute it from a graph.
    n_independent_origins:
        The sampling-weighted number of independent origins from
        :meth:`evoproto.kg.EvoKG.independent_origins` (Eqs. 2-3).
    length_ratio, material_*, load_*:
        Inputs of the transfer-uncertainty terms (Eqs. 9-10).
    """

    identifier: str
    taxon: str = ""
    trait: str = ""
    mechanism: str = ""
    functional_match: float = 0.0
    mechanism_evidence: float = 0.0
    n_independent_origins: float = 0.0
    length_ratio: float = 1.0
    material_biological: str = "hierarchical_composite"
    material_engineering: str = "monolithic_alloy"
    load_biological: str = "cyclic"
    load_engineering: str = "intermittent_inertial"
    notes: str = ""
    extras: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        for name in ("functional_match", "mechanism_evidence"):
            value = float(getattr(self, name))
            if not 0.0 <= value <= 1.0:
                raise ValueError(f"{name} must lie in [0, 1]")
        if self.n_independent_origins < 0:
            raise ValueError("n_independent_origins must be non-negative")


def score_analog(
    candidate: AnalogCandidate,
    weights: ScoreWeights | None = None,
    uncertainty_weights: UncertaintyWeights | None = None,
) -> dict[str, Any]:
    """Score one candidate analog (Eq. 8).

    .. math::

        S = w_F F + w_M M + w_N \\ln(1 + \\tilde N_\\text{conv}) - w_U U

    Returns the score together with every term that produced it, so that a
    ranking can be audited rather than trusted.
    """
    weights = weights or ScoreWeights()
    u = transfer_uncertainty(
        candidate.length_ratio,
        candidate.material_biological,
        candidate.material_engineering,
        candidate.load_biological,
        candidate.load_engineering,
        uncertainty_weights,
    )
    origins_term = math.log1p(float(candidate.n_independent_origins))
    score = (
        weights.functional * candidate.functional_match
        + weights.mechanism * candidate.mechanism_evidence
        + weights.origins * origins_term
        - weights.uncertainty * u["U"]
    )
    return {
        "identifier": candidate.identifier,
        "S": float(score),
        "F": float(candidate.functional_match),
        "M": float(candidate.mechanism_evidence),
        "N_conv": float(candidate.n_independent_origins),
        "log1p_N_conv": float(origins_term),
        "U": u["U"],
        "u_components": {k: u[k] for k in ("u_scale", "u_mat", "u_load")},
        "dominant_uncertainty": u["dominant"],
        "weights": weights.to_dict(),
    }


def rank_analogs(
    candidates: list[AnalogCandidate],
    weights: ScoreWeights | None = None,
    uncertainty_weights: UncertaintyWeights | None = None,
) -> list[dict[str, Any]]:
    """Score and rank candidates by ``S``, descending."""
    scored = [score_analog(c, weights, uncertainty_weights) for c in candidates]
    scored.sort(key=lambda row: (-row["S"], row["identifier"]))
    return scored
