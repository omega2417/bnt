"""dtcr - reference implementation of the digital-twin cyber-resilience framework.

Every module implements exactly one block of the manuscript's mathematical model.
The implementation is normative: where the manuscript text and this code disagree,
the code is the specification and the manuscript must be corrected (see
docs/manuscript_corrections.md).
"""

__version__ = "2.0.0-experiment"

from . import audit, trust, anomaly, graph_risk, orchestrator, resilience, stats  # noqa: F401
