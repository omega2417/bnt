"""The EOAT bracket case study end to end (Sections 6 and 4.6).

Builds the demonstration EE-KG for the query "high bending stiffness per unit
mass in a slender, intermittently loaded member", retrieves and scores the
three candidate analog families of Section 6.3 — the thin-cortex, internally
strutted long bones of flying birds, the hollow diaphragmed culms of bamboos
and the open-cell mineral foam (stereom) of echinoid spines — searches the
design space, verifies the result and runs the evidence gate.

Every record here is SYNTHETIC: the graph is a hand-built demonstration whose
support weights stand in for a curated corpus.  It exists so the pipeline can
be executed and audited offline, not to assert anything about birds, bamboos or
sea urchins.  Section 6.3 is explicit that these families are candidates, not
conclusions: each must pass a phylogenetic-signal test, a convergence test and
a DOI-backed mechanism test before it contributes to ``N_conv``.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Mapping, Optional, Sequence, Tuple

import numpy as np

from . import design as design_module
from . import optimize as optimize_module
from .data import CorpusSnapshot, Provenance, ProvenanceTag, stable_seed
from .gate import EvidenceWeights, GateResult, GateThresholds, decide
from .kg import EdgeType, EvoKG, NodeType
from .retrieval import (
    AnalogCandidate,
    RetrievalWeights,
    TransferWeights,
    rank_analogs,
)

__all__ = [
    "FUNCTIONAL_QUERY",
    "CLADE_SAMPLING",
    "build_demo_kg",
    "candidate_analogs",
    "run_case_study",
]

#: The functional requirement of Section 6.3, in the controlled vocabulary.
FUNCTIONAL_QUERY = (
    "maximize bending stiffness per unit mass of a slender cantilevered member "
    "under intermittent inertial load"
)

#: Sampled taxa versus accepted richness per clade, for Eq. (2).  SYNTHETIC.
CLADE_SAMPLING: Dict[str, Tuple[float, float]] = {
    "Aves": (180.0, 11000.0),
    "Bambusoideae": (60.0, 1600.0),
    "Echinoidea": (45.0, 1000.0),
}


def _prov(
    source: str,
    tag: ProvenanceTag,
    uri: str = "",
    u: float = 0.2,
    r: int = 0,
    method: str = "",
) -> Provenance:
    return Provenance(
        source=source,
        version="demo",
        license="CC0-1.0 (synthetic demonstration record)",
        tag=tag,
        uri=uri,
        u=u,
        r=r,
        method=method,
    )


def build_demo_kg() -> EvoKG:
    """The demonstration EE-KG of Fig. 5c.

    Three trait families in mutually distant lineages realise one mechanism —
    sandwich / cellular stiffening — which maps to the engineering parameter
    "core relative density".  They are linked by ``convergentWith`` rather than
    ``homologousTo``, so Eq. (3) counts three independent origins; the two
    avian traits are homologous to each other and therefore count once.
    """
    kg = EvoKG(name="EE-KG demo (SYNTHETIC)")

    kg.add_node("Aves.sp1", NodeType.ORGANISM, clade="Aves", label="flying bird (exemplar 1)")
    kg.add_node("Aves.sp2", NodeType.ORGANISM, clade="Aves", label="flying bird (exemplar 2)")
    kg.add_node("Bambusoideae.sp1", NodeType.ORGANISM, clade="Bambusoideae", label="bamboo")
    kg.add_node("Echinoidea.sp1", NodeType.ORGANISM, clade="Echinoidea", label="sea urchin")

    kg.add_node("aerial_intermittent_load", NodeType.ENVIRONMENT, label="aerial locomotion, intermittent inertial loading")
    kg.add_node("wind_loaded_stem", NodeType.ENVIRONMENT, label="wind-loaded terrestrial stem")
    kg.add_node("benthic_marine", NodeType.ENVIRONMENT, label="benthic marine, abrasive contact")

    kg.add_node("strutted_long_bone", NodeType.TRAIT, clade="Aves", label="thin-cortex internally strutted long bone")
    kg.add_node("strutted_long_bone_2", NodeType.TRAIT, clade="Aves", label="thin-cortex strutted long bone (second exemplar)")
    kg.add_node("diaphragmed_culm", NodeType.TRAIT, clade="Bambusoideae", label="hollow periodically diaphragmed culm")
    kg.add_node("stereom", NodeType.TRAIT, clade="Echinoidea", label="open-cell mineral foam (stereom)")

    kg.add_node("bending_stiffness_per_mass", NodeType.FUNCTION, label="bending stiffness per unit mass")
    kg.add_node("impact_tolerance", NodeType.FUNCTION, label="impact tolerance")

    kg.add_node("sandwich_stiffening", NodeType.MECHANISM,
                label="sandwich / cellular stiffening: thin stiff shell far from the neutral axis, low-density core")
    kg.add_node("core_relative_density", NodeType.ENG_PARAMETER,
                label="relative density rho of the cellular core (design variable)")

    measured = _prov("Gibson & Ashby, Cellular Solids (2nd ed.)", ProvenanceTag.MEASURED,
                     uri="https://doi.org/10.1017/CBO9781139878326", u=0.15)
    observed = _prov("MorphoBank demo matrix", ProvenanceTag.EXTERNAL, u=0.2)
    external = _prov("comparative literature (demo)", ProvenanceTag.EXTERNAL, u=0.25)
    reconstructed = _prov("ancestral state reconstruction (demo)", ProvenanceTag.MODELED,
                          u=0.4, r=1, method="ML under Brownian motion")
    dimensional = _prov("dimensional analysis (Buckingham pi)", ProvenanceTag.PROXY,
                        uri="https://doi.org/10.1103/PhysRev.4.345", u=0.3)

    kg.add_edge("Aves.sp1", "strutted_long_bone", EdgeType.HAS_TRAIT, 0.92, observed)
    kg.add_edge("Aves.sp2", "strutted_long_bone_2", EdgeType.HAS_TRAIT, 0.88, observed)
    kg.add_edge("Bambusoideae.sp1", "diaphragmed_culm", EdgeType.HAS_TRAIT, 0.90, observed)
    kg.add_edge("Echinoidea.sp1", "stereom", EdgeType.HAS_TRAIT, 0.85, observed)

    kg.add_edge("Aves.sp1", "aerial_intermittent_load", EdgeType.LIVES_IN, 0.9, external)
    kg.add_edge("Bambusoideae.sp1", "wind_loaded_stem", EdgeType.LIVES_IN, 0.9, external)
    kg.add_edge("Echinoidea.sp1", "benthic_marine", EdgeType.LIVES_IN, 0.9, external)

    for trait, support in (
        ("strutted_long_bone", 0.80),
        ("strutted_long_bone_2", 0.74),
        ("diaphragmed_culm", 0.78),
        ("stereom", 0.62),
    ):
        kg.add_edge(trait, "bending_stiffness_per_mass", EdgeType.PERFORMS, support, external)
    kg.add_edge("stereom", "impact_tolerance", EdgeType.PERFORMS, 0.70, external)

    kg.add_edge("bending_stiffness_per_mass", "sandwich_stiffening", EdgeType.EXPLAINED_BY, 0.86, measured)
    kg.add_edge("impact_tolerance", "sandwich_stiffening", EdgeType.EXPLAINED_BY, 0.55, external)
    kg.add_edge("sandwich_stiffening", "core_relative_density", EdgeType.MAPS_TO, 0.72, dimensional)

    # Mass-specific stiffness trades off against impact tolerance under selection.
    kg.add_edge("bending_stiffness_per_mass", "impact_tolerance", EdgeType.TRADES_OFF_WITH, 0.60, external)

    # Homology within Aves; convergence between the three distant lineages.
    kg.add_edge("strutted_long_bone", "strutted_long_bone_2", EdgeType.HOMOLOGOUS_TO, 0.95, observed)
    kg.add_edge("strutted_long_bone", "diaphragmed_culm", EdgeType.CONVERGENT_WITH, 0.80, external)
    kg.add_edge("strutted_long_bone", "stereom", EdgeType.CONVERGENT_WITH, 0.75, external)
    kg.add_edge("diaphragmed_culm", "stereom", EdgeType.CONVERGENT_WITH, 0.70, external)

    # An ancestral-state change, flagged as a reconstruction (r = 1).
    kg.add_edge("strutted_long_bone_2", "strutted_long_bone", EdgeType.DERIVED_FROM, 0.55, reconstructed)
    return kg


def candidate_analogs(kg: Optional[EvoKG] = None) -> List[AnalogCandidate]:
    """The three candidate analogs of Section 6.3, scored by Eq. (8).

    ``N^w_conv`` comes from the graph (Eq. 3 with the sampling weights of
    Eq. 2), so the count of independent origins is a derived property, not an
    assumption.  The characteristic lengths, material classes and load regimes
    reproduce Section 6.3: the scale term contributes weakly (the two lengths
    are within one decade) and the material term more strongly (hierarchical
    biological composites versus a monolithic printed alloy).
    """
    kg = kg or build_demo_kg()
    n_conv_w = kg.weighted_independent_origins("sandwich_stiffening", CLADE_SAMPLING)
    chain = kg.best_chain("core_relative_density")
    measured_fraction = chain.measured_fraction if chain else 0.0

    common = dict(
        n_conv_weighted=n_conv_w,
        length_engineering=0.050,          # bracket section height, m
        material_engineering="monolithic_isotropic",   # AlSi10Mg, LPBF
        load_biological="intermittent_inertial",
        load_engineering="intermittent_inertial",
        mechanism="sandwich_stiffening",
        provenance=_prov("evoproto.casestudy (demonstration)", ProvenanceTag.SYNTHETIC, u=0.3),
    )
    return [
        AnalogCandidate(
            identifier="bamboo_culm",
            name="hollow periodically diaphragmed bamboo culm",
            functional_match=0.86,
            mechanism_evidence=measured_fraction,
            length_biological=0.023,
            material_biological="hierarchical_composite",
            clade="Bambusoideae",
            citations=("10.1017/CBO9781139878326",),
            **common,
        ),
        AnalogCandidate(
            identifier="avian_long_bone",
            name="thin-cortex internally strutted avian long bone",
            functional_match=0.84,
            mechanism_evidence=measured_fraction,
            length_biological=0.012,
            material_biological="hierarchical_composite",
            clade="Aves",
            citations=("10.1017/CBO9781139878326",),
            **common,
        ),
        AnalogCandidate(
            identifier="echinoid_stereom",
            name="open-cell mineral foam (echinoid stereom)",
            functional_match=0.74,
            mechanism_evidence=measured_fraction,
            length_biological=0.004,
            material_biological="mineralised_foam",
            clade="Echinoidea",
            citations=("10.1017/CBO9781139878326",),
            **common,
        ),
    ]


def _verify(design_vector: np.ndarray, spec: design_module.BracketSpec, margin: float = 1.15) -> Dict[str, Any]:
    """Stand-in for the numerical verification stage of Section 4.6.

    A real deployment re-evaluates the candidate with linear-elastic and
    linear-buckling FE under certified properties, the actual scale, the load
    spectrum and the process constraints.  Here the analytic surrogate is
    re-run with the constraints tightened by ``margin``, which is a *proxy* for
    the fidelity gap and is tagged as such: it can only reject candidates that
    sit on a constraint boundary, never discover what FE would discover.
    """
    tightened = design_module.BracketSpec(
        L=spec.L,
        payload=spec.payload * margin,
        acceleration=spec.acceleration,
        delta_max=spec.delta_max,
        safety_factor=spec.safety_factor * margin,
        mass_max=spec.mass_max,
        t_min=spec.t_min,
        material=spec.material,
        C1_gibson_ashby=spec.C1_gibson_ashby,
        bounds_lo=spec.bounds_lo,
        bounds_hi=spec.bounds_hi,
    )
    result = design_module.evaluate(design_vector, tightened)
    return {
        "verified": bool(result["feasible"]),
        "margin": margin,
        "constraints": result["constraints"],
        "tag": ProvenanceTag.PROXY.value,
        "note": "surrogate stand-in for the FE stage; replace with a certified solver",
    }


def run_case_study(
    population_size: int = 40,
    generations: int = 25,
    replicate: int = 0,
    thresholds: GateThresholds = GateThresholds(),
    retrieval_weights: RetrievalWeights = RetrievalWeights(),
    transfer_weights: TransferWeights = TransferWeights(),
    evidence_weights: EvidenceWeights = EvidenceWeights(),
    spec: Optional[design_module.BracketSpec] = None,
    n_prototypes: int = 3,
) -> Dict[str, Any]:
    """Run the full case study and return the deliverable of Section 6.4.

    For every prototype the bundle holds the design vector, the analytic
    predictions (MODELED), the traceability chain with its four provenance
    records, ``E`` and ``U``, and the decision.  All prototypes are reported —
    recommended, abstained and rejected — so that the abstention rate is itself
    a measured quantity of the framework (Section 7.8).
    """
    spec = spec or design_module.EOAT_BRACKET
    kg = build_demo_kg()
    analogs = candidate_analogs(kg)
    ranked = rank_analogs(analogs, retrieval_weights, transfer_weights)
    best = ranked[0]
    best_candidate = next(a for a in analogs if a.identifier == best["identifier"])

    chain = kg.best_chain("core_relative_density", weights=evidence_weights.w)
    if chain is None:
        raise RuntimeError("the demonstration graph exposes no traceability chain")
    n_conv_w = kg.weighted_independent_origins("sandwich_stiffening", CLADE_SAMPLING)

    lo, hi = design_module.design_bounds(spec)
    seed = stable_seed("T1", "C", replicate)

    def evaluator(X: np.ndarray) -> Tuple[np.ndarray, np.ndarray]:
        out = design_module.evaluate_population(X, spec)
        return out["F"], out["G"]

    def sampler(n: int, rng: np.random.Generator) -> np.ndarray:
        return design_module.analog_prior(n, spec, rng)

    search_result = optimize_module.search(
        evaluator, sampler, lo, hi,
        population_size=population_size, generations=generations, seed=seed, arm="C",
    )

    # Pick the prototypes to carry forward: the extremes and the knee of the front.
    archive = search_result.archive
    objectives = search_result.archive_objectives
    if archive.shape[0] == 0:
        prototypes_idx: List[int] = []
    else:
        order = np.argsort(objectives[:, 0], kind="stable")
        picks = {int(order[0]), int(order[-1]), int(order[len(order) // 2])}
        prototypes_idx = sorted(picks)[:n_prototypes]

    prototypes: List[Dict[str, Any]] = []
    for rank, index in enumerate(prototypes_idx):
        vector = archive[index]
        analysis = design_module.evaluate(vector, spec)
        verification = _verify(vector, spec)
        U, components = best_candidate.transfer_uncertainty(transfer_weights)
        gate_result: GateResult = decide(
            chain=chain,
            U=U,
            n_conv_weighted=n_conv_w,
            verified=verification["verified"],
            uncertainty_components=components,
            thresholds=thresholds,
            weights=evidence_weights,
        )
        prototypes.append(
            {
                "rank": rank,
                "design": analysis["design"],
                "predictions_modeled": {
                    "mass_kg": float(analysis["mass"]),
                    "deflection_m": float(analysis["deflection"]),
                    "stress_Pa": float(analysis["stress"]),
                    "buckling_stress_Pa": float(analysis["stress_buckling"]),
                    "cost_proxy": float(analysis["cost"]),
                    "tag": ProvenanceTag.MODELED.value,
                },
                "measured": {
                    "mass_kg": None,
                    "stiffness_N_per_m": None,
                    "note": "populated by the physical test of Section 7.5 (tag MEASURED)",
                },
                "verification": verification,
                "analog": best,
                "gate": gate_result.as_dict(),
            }
        )

    snapshot = CorpusSnapshot(
        name="EOAT bracket case study (SYNTHETIC demonstration)",
        payload={
            "query": FUNCTIONAL_QUERY,
            "kg": kg.to_dict(),
            "specification": spec.as_dict(),
            "retrieval_weights": retrieval_weights.as_dict(),
            "transfer_weights": transfer_weights.as_dict(),
            "evidence_weights": evidence_weights.as_dict(),
            "thresholds": thresholds.as_dict(),
        },
    )

    decisions = [p["gate"]["decision"] for p in prototypes]
    return {
        "tag": ProvenanceTag.SYNTHETIC.value,
        "query": FUNCTIONAL_QUERY,
        "snapshot_hash": snapshot.hash,
        "seed": seed,
        "independent_origins": kg.independent_origins("sandwich_stiffening"),
        "independent_origins_weighted": n_conv_w,
        "analogs": ranked,
        "chain": chain.as_dict(),
        "search": {
            "evaluations": search_result.evaluations,
            "pareto_size": int(archive.shape[0]),
            "feasible_solution_rate": search_result.feasible_solution_rate,
            "iterations_to_specification": search_result.iterations_to_specification,
            "normalized_hypervolume": (
                optimize_module.normalized_hypervolume(objectives, spec.reference_point)
                if archive.shape[0] else 0.0
            ),
        },
        "prototypes": prototypes,
        "abstention_rate": (
            float(sum(d == "ABSTAIN" for d in decisions) / len(decisions)) if decisions else 0.0
        ),
        "note": (
            "engineer approval is required before any prototype is released; "
            "the graph, its support weights and the verification stand-in are SYNTHETIC"
        ),
    }
