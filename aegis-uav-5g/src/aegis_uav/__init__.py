"""Aegis-UAV-5G: reproducible agentic-AI testbed for detection, attribution and
containment of cyberattacks in 5G-enabled UAV networks."""

__version__ = "0.1.0"

# Canonical attack taxonomy (Section 3.5 of the manuscript).
ATTACK_CLASSES: tuple[str, ...] = ("T1", "T2", "T3", "T4", "T5", "T6")
BENIGN_LABEL = "benign"
ALL_LABELS: tuple[str, ...] = (BENIGN_LABEL, *ATTACK_CLASSES)

# Macro-class grouping for the hierarchical attribution agent (AAA).
MACRO_CLASSES: dict[str, str] = {
    "T1": "gnss",
    "T2": "session_behaviour",
    "T3": "network",
    "T4": "network",
    "T5": "session_behaviour",
    "T6": "session_behaviour",
}

MODALITIES: tuple[str, ...] = ("telemetry", "network", "behaviour")

__all__ = [
    "__version__",
    "ATTACK_CLASSES",
    "BENIGN_LABEL",
    "ALL_LABELS",
    "MACRO_CLASSES",
    "MODALITIES",
]
