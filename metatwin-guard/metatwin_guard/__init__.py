"""MetaTwin-Guard: explainable, verifiable digital-twin assurance backend
for a two-site cyber range (reference artifact, evidence level B).

The package processes exported or synthetic telemetry only. It performs no
scanning, exploitation, credential attack or network reconfiguration.
"""
__version__ = "1.0.1"

from .crypto import deterministic_private_key  # noqa: E402
from .detector import RobustDetector, StaticRules, hybrid_decision  # noqa: E402
from .events import SoftwareSensor, tamper_features  # noqa: E402
from .gateway import IntegrityGateway  # noqa: E402
from .ledger import QuorumEvidenceLedger  # noqa: E402
from .pipeline import MetaTwinGuard  # noqa: E402
from .twin import TwinState  # noqa: E402

__all__ = [
    "IntegrityGateway", "MetaTwinGuard", "QuorumEvidenceLedger", "RobustDetector",
    "SoftwareSensor", "StaticRules", "TwinState", "deterministic_private_key",
    "hybrid_decision", "tamper_features", "__version__",
]
