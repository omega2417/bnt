"""UMSF cyber-range digital twin: modular reference implementation.

Behavioural surrogate for pre-experimental planning. It opens no sockets,
emits no real attack traffic and must never be used as a safety controller.
"""

__version__ = "2.0.0"
__evidence_class__ = "pre-experimental synthetic model"

MODES = ("SIM", "EMU", "REPLAY", "HIL")
