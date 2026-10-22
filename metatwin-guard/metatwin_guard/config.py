"""Reference configuration of MetaTwin-Guard.

All constants were fixed before any benchmark execution (Sections 3.6-3.9 of
the accompanying article). They are artifact configuration values, not vendor
limits or validated field thresholds.
"""
from __future__ import annotations

SCHEMA_VERSION = "1.0"

# Deterministic benchmark (Section 3.9)
MASTER_SEED = 20260823
SCENARIOS = (
    "wan_failover",
    "vpn_degradation",
    "wifi_auth_surge",
    "power_transition",
    "telemetry_modification",
    "replay",
)
SCENARIO_LABELS = {
    "wan_failover": "WAN failover",
    "vpn_degradation": "VPN degradation",
    "wifi_auth_surge": "Wi-Fi authentication surge",
    "power_transition": "Power transition",
    "telemetry_modification": "Telemetry modification",
    "replay": "Replay",
}
REPETITIONS = 8
N_BASELINE = 120
N_EVAL = 240
N_INJECTED = 40  # of the N_EVAL evaluation events

# Feature vector (Section 3.6), p = 7
FEATURES = (
    "rtt_ms",
    "jitter_ms",
    "loss_pct",
    "throughput_mbps",
    "auth_failures",
    "vpn_status",
    "power_status",
)
BINARY_FEATURES = ("vpn_status", "power_status")

# Robust explainable detector, Equations (3)-(6); median/MAD after
# Rousseeuw & Croux (1993), doi:10.1080/01621459.1993.10476408
MAD_CONSISTENCY = 1.4826
DISPERSION_FLOOR = 0.25
Z_CLIP = 20.0
SCORE_THRESHOLD = 3.20
TOP_K = 3

# Static operational rules (Section 3.7): feature, operator, threshold
STATIC_RULES = (
    ("rtt_ms", ">", 180.0),
    ("jitter_ms", ">", 50.0),
    ("loss_pct", ">", 5.0),
    ("throughput_mbps", "<", 8.0),
    ("auth_failures", ">", 18.0),
    ("vpn_status", "<", 0.5),
    ("power_status", "<", 0.5),
)

# Quorum-signed evidence chain (Section 3.8)
N_VALIDATORS = 4
QUORUM = 3

# Freshness bounds for the interface contract (Section 3.5); field-protocol
# values, not exercised by the synthetic benchmark.
TAU_FRESH_S = 30.0
TAU_LOST_S = 120.0
