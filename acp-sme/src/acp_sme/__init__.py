"""ACP-SME - Adaptive Cybersecurity Protector for SMEs (reference prototype).

Reference implementation accompanying:

    Prokopovych-Tkachenko D. "A Metadata-Driven Adaptive Cybersecurity Protector
    for SMEs in Metaverse-Enabled Ecosystems: Resource-Aware Tailoring of
    NIST CSF 2.0, ISO/IEC 27001:2022, and CIS Controls v8.1."

Claims boundary
---------------
ACP-SME is a governance decision-support artifact.  It is not an anti-malware
packer, vulnerability scanner, SIEM, autonomous enforcement engine, actuarial
loss model or certification system.  A standards reference states why a
recommendation is relevant; it does not prove conformity.  Every number this
package produces is model output over explicitly synthetic traces: it verifies
internal behaviour under encoded assumptions and demonstrates neither
real-world incident reduction nor standards conformity nor certification
readiness.
"""

__version__ = "0.1.0"
__author__ = "Dmytro Prokopovych-Tkachenko"
__license__ = "MIT"

from .capabilities import CAPABILITIES, CODES, Capability  # noqa: F401
from .selector import Selection, select  # noqa: F401

__all__ = ["CAPABILITIES", "CODES", "Capability", "Selection", "select", "__version__"]
