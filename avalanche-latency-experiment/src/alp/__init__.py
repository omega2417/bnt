"""ALP — Avalanche Latency Protocol toolkit.

Reproducible field-experiment package for the study

    "A Blockchain Solution for Reducing Confirmed-State Access Latency
     in an Avalanche Network: An Experimental Study"

The package implements the full pipeline described in the experimental
protocol: randomized schedule generation, immutable workload traces,
the client-side measurement core, a documented reference simulator,
metric derivation, the statistical plan (paired bootstrap), the
stability rules, tables and figures, and SHA-256 manifests.

Every artefact carries a provenance label.  ``MEASURED`` records come
from a real campaign on the cyber range; ``SIMULATED`` records come from
the reference model in :mod:`alp.simulate` and must never be reported as
measurements.
"""

__version__ = "1.0.0"

PROVENANCE_MEASURED = "MEASURED"
PROVENANCE_SIMULATED = "SIMULATED"

__all__ = ["__version__", "PROVENANCE_MEASURED", "PROVENANCE_SIMULATED"]
