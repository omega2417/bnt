"""Evidence gating and abstention (Section 4.6, Algorithm 2).

* Eq. (13)  the evidence score of a traceability chain

  ``E = min{1, (sum_k w_k s_k) (1 + kappa ln(1 + N^w_conv)) rho_rec}``

  with ``kappa = 0.15`` and ``rho_rec = 0.7`` when the chain relies only on
  reconstructed states, 1 otherwise;
* Eq. (14)  the decision rule REJECT / ABSTAIN / RECOMMEND with thresholds
  ``tau_E`` and ``tau_U`` fixed before the experiment.

The ABSTAIN branch does not return nothing.  It returns a missing-evidence
report naming the weakest edge of the chain, the component of ``U`` that
exceeds its budget, and the experiment that would raise the score — abstention
converts a gap in evidence into a research task.  Final approval always rests
with the engineer; RECOMMEND is a recommendation awaiting approval, never a
release.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, Mapping, Optional, Sequence, Tuple

import math

from .kg import CHAIN_EDGES, EvidenceChain

__all__ = [
    "Decision",
    "GateThresholds",
    "EvidenceWeights",
    "evidence_score",
    "MissingEvidenceReport",
    "GateResult",
    "decide",
]

#: Default convergence bonus of Eq. (13).
KAPPA_DEFAULT = 0.15

#: Multiplier applied when every record of a chain is a reconstruction.
RHO_REC_RECONSTRUCTED = 0.7


class Decision(str, Enum):
    """The three outcomes of Eq. (14)."""

    RECOMMEND = "RECOMMEND"
    ABSTAIN = "ABSTAIN"
    REJECT = "REJECT"


@dataclass(frozen=True)
class GateThresholds:
    """Decision thresholds, frozen before the experiment (Section 7.8).

    ``tau_U = 0.5`` is the value used in the case study of Section 6.3; the
    paper leaves ``tau_E`` to pre-registration, and 0.5 is the default shipped
    here — a deployment records its own value in the pre-registration document.
    """

    tau_E: float = 0.5
    tau_U: float = 0.5

    def as_dict(self) -> Dict[str, float]:
        return {"tau_E": self.tau_E, "tau_U": self.tau_U}


@dataclass(frozen=True)
class EvidenceWeights:
    """Importance weights ``w_1..w_4`` of the four chain edges; they sum to one.

    The order follows Eq. (4): hasTrait, performs, explainedBy, mapsTo.  The
    default is uniform; a deployment that trusts, say, the experimental
    ``explainedBy`` edge more than the taxonomic ``hasTrait`` edge records its
    own weights in the pre-registration.
    """

    w: Tuple[float, float, float, float] = (0.25, 0.25, 0.25, 0.25)

    def __post_init__(self) -> None:
        if len(self.w) != 4:
            raise ValueError("a traceability chain has exactly four edges")
        if any(x < 0 for x in self.w):
            raise ValueError("edge weights must be non-negative")
        if abs(sum(self.w) - 1.0) > 1e-9:
            raise ValueError(f"edge weights must sum to 1, got {sum(self.w)}")

    def as_dict(self) -> Dict[str, Any]:
        return {f"w_{i + 1}": value for i, value in enumerate(self.w)}


def evidence_score(
    supports: Sequence[float],
    n_conv_weighted: float,
    reconstruction_only: bool = False,
    weights: EvidenceWeights = EvidenceWeights(),
    kappa: float = KAPPA_DEFAULT,
) -> float:
    r"""Eq. (13): the evidence score of a traceability chain.

    :math:`E = \min\{1, (\sum_{k=1}^{4} w_k s_k)(1 + \kappa\ln(1 + N^w_{\mathrm{conv}}))\rho_{\mathrm{rec}}\}`

    A chain built only from reconstructed ancestral states is multiplied by
    ``rho_rec = 0.7``: reconstructions are model outputs whose uncertainty
    depends on tree and model, and Section 8.3 records this factor as a coarse
    device rather than a calibrated correction.
    """
    if len(supports) != 4:
        raise ValueError("Eq. (13) takes the four edge supports of a chain")
    if any(not 0.0 <= float(s) <= 1.0 for s in supports):
        raise ValueError("edge supports must lie in [0, 1]")
    if n_conv_weighted < 0:
        raise ValueError("N^w_conv must be non-negative")
    weighted_support = sum(w * float(s) for w, s in zip(weights.w, supports))
    convergence_bonus = 1.0 + kappa * math.log1p(float(n_conv_weighted))
    rho_rec = RHO_REC_RECONSTRUCTED if reconstruction_only else 1.0
    return float(min(1.0, weighted_support * convergence_bonus * rho_rec))


@dataclass(frozen=True)
class MissingEvidenceReport:
    """What the framework returns instead of a recommendation.

    ``suggested_experiment`` names the measurement that would populate the
    weakest edge, so that an abstention becomes a research task rather than a
    dead end.
    """

    reason: str
    weakest_edge: Optional[str] = None
    weakest_support: Optional[float] = None
    dominant_uncertainty_term: Optional[str] = None
    dominant_uncertainty_value: Optional[float] = None
    suggested_experiment: str = ""

    def as_dict(self) -> Dict[str, Any]:
        return {
            "reason": self.reason,
            "weakest_edge": self.weakest_edge,
            "weakest_support": self.weakest_support,
            "dominant_uncertainty_term": self.dominant_uncertainty_term,
            "dominant_uncertainty_value": self.dominant_uncertainty_value,
            "suggested_experiment": self.suggested_experiment,
        }


#: The experiment that would populate each chain edge if it is the weakest one.
_EDGE_EXPERIMENTS: Dict[str, str] = {
    "hasTrait": (
        "the trait state is weakly attested for this taxon; score the character on "
        "additional specimens, or resolve the taxon against a MorphoBank matrix with "
        "higher completeness (Eq. 1)"
    ),
    "performs": (
        "the functional contribution of the trait is inferred rather than demonstrated; "
        "a functional-morphology experiment (in vivo loading, kinematic measurement) "
        "would populate this edge"
    ),
    "explainedBy": (
        "no measured mechanism support; a mechanical test of the biological material at "
        "the relevant strain rate — for a stiffness mechanism, three-point bending on a "
        "specimen of the biological material — would populate this edge with a "
        "DOI-backed measurement"
    ),
    "mapsTo": (
        "the transfer to the design variable rests on dimensional analysis alone; a "
        "prior transfer measured at the engineering scale, or a calibration specimen, "
        "would populate this edge"
    ),
}

#: How to reduce each component of the transfer uncertainty of Eq. (9).
_UNCERTAINTY_ADVICE: Dict[str, str] = {
    "u_scale": (
        "the biological and engineering characteristic lengths differ by too much; "
        "re-derive the transfer by dimensional analysis instead of geometric copying, "
        "or select an analog closer in scale"
    ),
    "u_mat": (
        "the biological material class is far from the engineering material class; "
        "either qualify a material closer to the biological behaviour class or test "
        "whether the mechanism survives the substitution"
    ),
    "u_load": (
        "the loading regime of the biological system does not match the specified load "
        "spectrum; re-query the corpus for an analog under the target regime"
    ),
}


@dataclass(frozen=True)
class GateResult:
    """The outcome of Algorithm 2, with everything needed to audit it."""

    decision: Decision
    E: float
    U: float
    thresholds: GateThresholds
    chain: Optional[Dict[str, Any]] = None
    report: Optional[MissingEvidenceReport] = None
    uncertainty_components: Mapping[str, float] = field(default_factory=dict)

    @property
    def recommended(self) -> bool:
        return self.decision is Decision.RECOMMEND

    def as_dict(self) -> Dict[str, Any]:
        return {
            "decision": self.decision.value,
            "E": self.E,
            "U": self.U,
            "thresholds": self.thresholds.as_dict(),
            "uncertainty_components": dict(self.uncertainty_components),
            "chain": self.chain,
            "report": self.report.as_dict() if self.report else None,
            "note": "RECOMMEND is a recommendation awaiting engineer approval, not a release",
        }


def decide(
    chain: EvidenceChain,
    U: float,
    n_conv_weighted: float,
    verified: bool,
    uncertainty_components: Optional[Mapping[str, float]] = None,
    thresholds: GateThresholds = GateThresholds(),
    weights: EvidenceWeights = EvidenceWeights(),
    kappa: float = KAPPA_DEFAULT,
) -> GateResult:
    """Algorithm 2: the evidence-gated recommendation.

    ``verified`` is the outcome of the numerical verification stage of
    Section 4.6: a candidate that fails the higher-fidelity model is rejected
    regardless of its position in the ``(E, U)`` plane.
    """
    uncertainty_components = dict(uncertainty_components or {})

    if not verified:
        return GateResult(
            decision=Decision.REJECT,
            E=float("nan"),
            U=float(U),
            thresholds=thresholds,
            chain=chain.as_dict(),
            report=MissingEvidenceReport(
                reason="numerical verification failed",
                suggested_experiment=(
                    "the candidate violates a constraint under the higher-fidelity model; "
                    "re-enter the search with the verified model in the loop"
                ),
            ),
            uncertainty_components=uncertainty_components,
        )

    E = evidence_score(
        chain.supports,
        n_conv_weighted,
        reconstruction_only=chain.reconstruction_only,
        weights=weights,
        kappa=kappa,
    )

    if E < thresholds.tau_E:
        k = chain.weakest_edge()
        edge_name = CHAIN_EDGES[k].value
        return GateResult(
            decision=Decision.ABSTAIN,
            E=E,
            U=float(U),
            thresholds=thresholds,
            chain=chain.as_dict(),
            report=MissingEvidenceReport(
                reason=f"evidence score E = {E:.3f} is below tau_E = {thresholds.tau_E:.3f}",
                weakest_edge=edge_name,
                weakest_support=float(chain.supports[k]),
                suggested_experiment=_EDGE_EXPERIMENTS[edge_name],
            ),
            uncertainty_components=uncertainty_components,
        )

    if U > thresholds.tau_U:
        dominant = (
            max(uncertainty_components.items(), key=lambda kv: kv[1])
            if uncertainty_components
            else ("U", float(U))
        )
        return GateResult(
            decision=Decision.ABSTAIN,
            E=E,
            U=float(U),
            thresholds=thresholds,
            chain=chain.as_dict(),
            report=MissingEvidenceReport(
                reason=f"transfer uncertainty U = {U:.3f} exceeds tau_U = {thresholds.tau_U:.3f}",
                dominant_uncertainty_term=dominant[0],
                dominant_uncertainty_value=float(dominant[1]),
                suggested_experiment=_UNCERTAINTY_ADVICE.get(
                    dominant[0], "reduce the dominant term of the transfer uncertainty"
                ),
            ),
            uncertainty_components=uncertainty_components,
        )

    return GateResult(
        decision=Decision.RECOMMEND,
        E=E,
        U=float(U),
        thresholds=thresholds,
        chain=chain.as_dict(),
        uncertainty_components=uncertainty_components,
    )
