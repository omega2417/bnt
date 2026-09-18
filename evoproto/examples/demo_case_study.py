#!/usr/bin/env python3
"""Worked example: the EOAT bracket, and what an abstention looks like.

Run with ``python examples/demo_case_study.py``.  It prints the retrieval
ranking, the traceability chain, the prototypes with their decisions, and then
repeats the gate on a deliberately thin corpus to show the abstention branch —
the outcome the framework is built to be able to produce.
"""

from __future__ import annotations

from evoproto.casestudy import build_demo_kg, candidate_analogs, run_case_study
from evoproto.data import Provenance, ProvenanceTag
from evoproto.gate import GateThresholds, decide, evidence_score
from evoproto.kg import EvidenceChain
from evoproto.retrieval import rank_analogs


def main() -> None:
    kg = build_demo_kg()
    print(f"EE-KG: {kg!r}")
    print(
        "independent origins of 'sandwich_stiffening': "
        f"{kg.independent_origins('sandwich_stiffening')} homology classes "
        "(the two avian traits are homologous and count once)\n"
    )

    print("retrieval ranking (Eq. 8):")
    for row in rank_analogs(candidate_analogs(kg)):
        print(
            f"  {row['name']:<52} S = {row['score']:+.3f}   U = {row['U']:.3f}   "
            f"u_scale = {row['U_components']['u_scale']:.2f}  "
            f"u_mat = {row['U_components']['u_mat']:.2f}  "
            f"u_load = {row['U_components']['u_load']:.2f}"
        )

    result = run_case_study()
    print("\nprototypes (the deliverable of Section 6.4):")
    for prototype in result["prototypes"]:
        d = prototype["design"]
        p = prototype["predictions_modeled"]
        g = prototype["gate"]
        print(
            f"  b = {d['b'] * 1e3:5.1f} mm  h = {d['h'] * 1e3:5.1f} mm  "
            f"t = {d['t'] * 1e3:4.2f} mm  rho = {d['rho']:.3f}  ->  "
            f"{p['mass_kg'] * 1e3:6.1f} g, {p['deflection_m'] * 1e6:6.1f} um  "
            f"[{p['tag']}]  E = {g['E']:.3f}  U = {g['U']:.3f}  {g['decision']}"
        )
    print(f"  abstention rate: {result['abstention_rate']:.2f}")

    # ------------------------------------------------------------------ abstain
    print("\nthe same design, but the mechanism has no measured support:")
    thin = Provenance("thin corpus", "demo", "CC0", ProvenanceTag.EXTERNAL, u=0.6)
    weak_chain = EvidenceChain(
        nodes=("Aves.sp1", "strutted_long_bone", "bending_stiffness_per_mass",
               "sandwich_stiffening", "core_relative_density"),
        supports=(0.62, 0.48, 0.08, 0.40),
        provenance=(thin, thin, thin, thin),
    )
    decision = decide(
        chain=weak_chain,
        U=0.38,
        n_conv_weighted=0.10,
        verified=True,
        uncertainty_components={"u_scale": 0.29, "u_mat": 0.80, "u_load": 0.0},
        thresholds=GateThresholds(),
    )
    print(f"  E = {decision.E:.3f} (threshold {decision.thresholds.tau_E})  -> {decision.decision.value}")
    print(f"  weakest edge : {decision.report.weakest_edge} (s = {decision.report.weakest_support})")
    print(f"  next step    : {decision.report.suggested_experiment}")

    print("\nand with a transfer that is too uncertain rather than too weakly evidenced:")
    strong_chain = EvidenceChain(
        nodes=weak_chain.nodes, supports=(0.92, 0.80, 0.86, 0.72),
        provenance=weak_chain.provenance,
    )
    decision = decide(
        chain=strong_chain,
        U=0.71,
        n_conv_weighted=0.10,
        verified=True,
        uncertainty_components={"u_scale": 0.86, "u_mat": 0.80, "u_load": 0.35},
    )
    print(f"  E = {decision.E:.3f}, U = {decision.U:.3f}  -> {decision.decision.value}")
    print(f"  dominant term: {decision.report.dominant_uncertainty_term}")
    print(f"  next step    : {decision.report.suggested_experiment}")

    print(
        f"\nevidence score of a perfect chain with no convergence support: "
        f"{evidence_score((1.0, 1.0, 1.0, 1.0), 0.0):.2f}"
    )


if __name__ == "__main__":
    main()
