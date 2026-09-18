"""Evidence score, decision rule and abstention (Section 4.6).

Numerical verification is necessary but not sufficient for a recommendation:
the framework also requires that the biological justification be strong enough
to be worth communicating to the engineer.  :func:`evidence_score` implements
Eq. (13) over a traceability chain, :func:`decide` implements the decision rule
of Eq. (14) as Algorithm 2.

The ABSTAIN branch never returns nothing.  It returns a missing-evidence report
naming the weakest edge of the chain, the component of ``U`` that exceeds its
budget, and the experiment that would raise the score - which converts a gap in
evidence into a research task.  Final approval always rests with the engineer;
RECOMMEND means "here is a chain worth reading", not "build this".
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Any

__all__ = [
    "Decision",
    "EvidenceWeights",
    "GateResult",
    "Thresholds",
    "decide",
    "evidence_score",
]


class Decision(str, Enum):
    """The three outcomes of Algorithm 2."""

    RECOMMEND = "RECOMMEND"
    ABSTAIN = "ABSTAIN"
    REJECT = "REJECT"


@dataclass(frozen=True)
class EvidenceWeights:
    """Importance weights of the four chain edges in Eq. (13).

    The weights sum to 1 and are ordered ``(hasTrait, performs, explainedBy,
    mapsTo)``: the mechanism edge carries the most weight because it is the one
    backed by DOI-referenced measurement, and the transfer edge follows.
    """

    has_trait: float = 0.20
    performs: float = 0.25
    explained_by: float = 0.35
    maps_to: float = 0.20
    reconstruction_penalty: float = 0.20
    convergence_bonus: float = 0.15

    def __post_init__(self) -> None:
        total = self.has_trait + self.performs + self.explained_by + self.maps_to
        if abs(total - 1.0) > 1e-9:
            raise ValueError("chain edge weights must sum to 1")
        for name in ("reconstruction_penalty", "convergence_bonus"):
            value = float(getattr(self, name))
            if not 0.0 <= value <= 1.0:
                raise ValueError(f"{name} must lie in [0, 1]")

    @property
    def vector(self) -> tuple[float, float, float, float]:
        return (self.has_trait, self.performs, self.explained_by, self.maps_to)

    def to_dict(self) -> dict[str, float]:
        return asdict(self)


@dataclass(frozen=True)
class Thresholds:
    """Decision thresholds of Eq. (14).

    ``tau_E`` is the minimum evidence score and ``tau_U`` the maximum transfer
    uncertainty a recommendation may carry.  Both are fixed before the
    experiment and archived with the pre-registration (Section 7.8); Fig. 8
    plots the resulting regions in the ``(E, U)`` plane.
    """

    tau_E: float = 0.60
    tau_U: float = 0.50

    def __post_init__(self) -> None:
        for name in ("tau_E", "tau_U"):
            value = float(getattr(self, name))
            if not 0.0 <= value <= 1.0:
                raise ValueError(f"{name} must lie in [0, 1]")

    def to_dict(self) -> dict[str, float]:
        return asdict(self)


def evidence_score(
    supports: Sequence[float],
    reconstructed: bool = False,
    n_independent_origins: float = 0.0,
    weights: EvidenceWeights | None = None,
) -> float:
    """Evidence score ``E`` of a traceability chain (Eq. 13).

    .. math::

        E = \\Bigl(\\sum_k w_k s_k\\Bigr)\\,(1 - \\gamma r)
            + \\beta\\,\\mathbf{1}[\\tilde N_\\text{conv} \\ge 2]

    clipped to ``[0, 1]``, where ``s_k`` are the four chain supports, ``w_k``
    their importance weights, ``r`` the reconstruction flag, ``gamma`` the
    reconstruction penalty and ``beta`` a small convergence bonus (default
    0.15) awarded when the mechanism has at least two independent origins.

    The reconstruction penalty is a coarse device (Section 8.3): reconstructed
    ancestral states are model outputs whose uncertainty depends on the tree and
    the model, and a single ``gamma`` cannot express that.
    """
    weights = weights or EvidenceWeights()
    supports = [float(s) for s in supports]
    if len(supports) != 4:
        raise ValueError("Eq. (13) expects the four supports of the chain of Eq. (4)")
    if any(not 0.0 <= s <= 1.0 for s in supports):
        raise ValueError("chain supports must lie in [0, 1]")
    base = sum(w * s for w, s in zip(weights.vector, supports))
    penalized = base * (1.0 - weights.reconstruction_penalty * int(bool(reconstructed)))
    bonus = weights.convergence_bonus if float(n_independent_origins) >= 2.0 else 0.0
    return float(min(1.0, max(0.0, penalized + bonus)))


@dataclass
class GateResult:
    """Outcome of the gate, with everything a design review needs to read it."""

    decision: Decision
    evidence: float
    transfer_uncertainty: float
    thresholds: Thresholds
    reason: str
    report: dict[str, Any] = field(default_factory=dict)

    @property
    def recommended(self) -> bool:
        return self.decision is Decision.RECOMMEND

    def to_dict(self) -> dict[str, Any]:
        return {
            "decision": self.decision.value,
            "E": self.evidence,
            "U": self.transfer_uncertainty,
            "thresholds": self.thresholds.to_dict(),
            "reason": self.reason,
            "report": self.report,
        }


def decide(
    verified: bool,
    supports: Sequence[float],
    uncertainty: Mapping[str, float] | float,
    reconstructed: bool = False,
    n_independent_origins: float = 0.0,
    weights: EvidenceWeights | None = None,
    thresholds: Thresholds | None = None,
    chain: Any | None = None,
) -> GateResult:
    """Evidence-gated recommendation (Eq. 14, Algorithm 2).

    Parameters
    ----------
    verified:
        Did the candidate pass numerical verification (all ``g_j >= 0`` under
        the higher-fidelity model)?  If not, the answer is REJECT regardless of
        the biological evidence - convergence raises confidence, it never skips
        verification (Section 8.3).
    supports:
        The four chain supports ``s_1..s_4`` of Eq. (4).
    uncertainty:
        Either ``U`` directly, or the dictionary returned by
        :func:`evoproto.retrieval.transfer_uncertainty`, in which case the
        dominant component is named in the abstention report.
    chain:
        Optional :class:`evoproto.kg.Chain`; when given, the missing-evidence
        report names the offending edge and its endpoints rather than an index.

    Returns
    -------
    GateResult
        On ABSTAIN, ``report`` carries the weakest edge, the dominant
        uncertainty term and a concrete experiment that would raise the score.
    """
    thresholds = thresholds or Thresholds()
    weights = weights or EvidenceWeights()
    if isinstance(uncertainty, Mapping):
        u_value = float(uncertainty["U"])
        dominant = str(uncertainty.get("dominant", ""))
        components = {k: float(v) for k, v in uncertainty.items()
                      if k in ("u_scale", "u_mat", "u_load")}
    else:
        u_value = float(uncertainty)
        dominant, components = "", {}

    if not verified:
        return GateResult(
            decision=Decision.REJECT,
            evidence=float("nan"),
            transfer_uncertainty=u_value,
            thresholds=thresholds,
            reason="numerical verification failed",
            report={"next_step": "repair the design or tighten the parametric family"},
        )

    e_value = evidence_score(supports, reconstructed, n_independent_origins, weights)

    if e_value < thresholds.tau_E:
        index = int(min(range(len(supports)), key=lambda k: supports[k]))
        edge_names = ("hasTrait", "performs", "explainedBy", "mapsTo")
        edge_label = edge_names[index]
        endpoints = None
        if chain is not None and getattr(chain, "links", None):
            link = chain.links[index]
            edge_label = link.edge_type.value
            endpoints = f"{link.tail} -> {link.head}"
        return GateResult(
            decision=Decision.ABSTAIN,
            evidence=e_value,
            transfer_uncertainty=u_value,
            thresholds=thresholds,
            reason=f"evidence score {e_value:.3f} below tau_E = {thresholds.tau_E:.2f}",
            report={
                "weakest_edge": edge_label,
                "weakest_edge_endpoints": endpoints,
                "weakest_support": float(supports[index]),
                "reconstructed": bool(reconstructed),
                "next_step": _missing_evidence_advice(edge_label),
            },
        )

    if u_value > thresholds.tau_U:
        return GateResult(
            decision=Decision.ABSTAIN,
            evidence=e_value,
            transfer_uncertainty=u_value,
            thresholds=thresholds,
            reason=f"transfer uncertainty {u_value:.3f} above tau_U = {thresholds.tau_U:.2f}",
            report={
                "dominant_term": dominant,
                "components": components,
                "next_step": _transfer_advice(dominant),
            },
        )

    return GateResult(
        decision=Decision.RECOMMEND,
        evidence=e_value,
        transfer_uncertainty=u_value,
        thresholds=thresholds,
        reason="verified, evidence above tau_E and transfer uncertainty within budget",
        report={
            "next_step": "engineer approval required before release",
            "chain": chain.to_dict() if hasattr(chain, "to_dict") else None,
        },
    )


def _missing_evidence_advice(edge: str) -> str:
    """The experiment that would populate a weak chain edge (Section 4.6)."""
    return {
        "hasTrait": (
            "no scored observation of the trait in the taxon; score the character "
            "on specimens or import a MorphoBank matrix that covers it"
        ),
        "performs": (
            "the trait-to-function link rests on inference; a functional-morphology "
            "experiment or a published functional test would populate this edge"
        ),
        "explainedBy": (
            "no measured support for the mechanism; a three-point bending test on a "
            "specimen of the biological material at the relevant strain rate would "
            "populate this edge"
        ),
        "mapsTo": (
            "the transfer to the design variable rests on analogy; a dimensional "
            "analysis or a prior verified transfer would populate this edge"
        ),
    }.get(edge, "collect DOI-backed evidence for the weakest edge of the chain")


def _transfer_advice(dominant: str) -> str:
    return {
        "u_scale": (
            "scale mismatch dominates; redo the transfer through dimensional analysis "
            "rather than geometric similarity, or find an analog at the target scale"
        ),
        "u_mat": (
            "material mismatch dominates; either qualify a material closer to the "
            "biological behavior class or measure the mechanism in the target material"
        ),
        "u_load": (
            "load-regime mismatch dominates; test the mechanism under the target "
            "loading type and rate before transferring it"
        ),
    }.get(dominant, "reduce the dominant transfer-uncertainty term before recommending")
