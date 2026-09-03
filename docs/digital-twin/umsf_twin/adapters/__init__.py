"""Adapters translating vendor telemetry into the twin's data contracts.

In SIM they are pure parsers over recorded fixtures: no adapter opens a socket.
Live collection belongs to EMU/HIL and is gated by the safety policy.
"""
