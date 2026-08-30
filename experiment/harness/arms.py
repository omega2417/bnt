"""Definition of the six compared configurations (A0-A5).

Every arm sees the SAME telemetry stream, the same injected ground truth, the same
node resources and the same candidate-action set for a given (scenario, repetition)
block. Arms differ only in which mechanisms are switched on. No arm-specific
latency, accuracy or cost constant exists anywhere in this file - all outcome
differences are produced by the mechanisms themselves.
"""
from __future__ import annotations

from dataclasses import dataclass

__all__ = ["ArmSpec", "ARMS"]


@dataclass(frozen=True)
class ArmSpec:
    code: str
    label: str
    ids: bool                  # traffic-only rule detector over IDS_FEATURES
    twin_anomaly: bool         # Mahalanobis over all p=9 features (Eq. 6-7)
    integrity: bool            # hash-challenge audit + provenance/sequence checks
    trust: bool                # dynamic trust model (Eq. 2-3) feeding Eq. (8)
    graph: bool                # dependency-risk propagation (Eq. 9-11)
    whatif: bool               # candidate-action simulation on the twin (Eq. 12)
    constraints: tuple[str, ...]   # subset of hard admissibility checks (Eq. 13)
    response: str              # manual | playbook | auto


ARMS: dict[str, ArmSpec] = {
    "A0": ArmSpec("A0", "IDS + manual response",
                  ids=True, twin_anomaly=False, integrity=False, trust=False,
                  graph=False, whatif=False, constraints=(), response="manual"),
    "A1": ArmSpec("A1", "IDS + automated playbook (no twin)",
                  ids=True, twin_anomaly=False, integrity=False, trust=False,
                  graph=False, whatif=False, constraints=(), response="playbook"),
    "A2": ArmSpec("A2", "Twin + IDS + automated response (no trust/provenance, no graph what-if)",
                  ids=True, twin_anomaly=True, integrity=False, trust=False,
                  graph=False, whatif=False, constraints=("capacity",), response="auto"),
    "A3": ArmSpec("A3", "Full system without integrity/trust/provenance",
                  ids=True, twin_anomaly=True, integrity=False, trust=False,
                  graph=True, whatif=True, constraints=("capacity", "security_label"),
                  response="auto"),
    "A4": ArmSpec("A4", "Full system without graph risk propagation and what-if",
                  ids=True, twin_anomaly=True, integrity=True, trust=True,
                  graph=False, whatif=False,
                  constraints=("capacity", "security_label", "host_trust"), response="auto"),
    "A5": ArmSpec("A5", "Full proposed system",
                  ids=True, twin_anomaly=True, integrity=True, trust=True,
                  graph=True, whatif=True,
                  constraints=("capacity", "security_label", "host_trust"), response="auto"),
}
