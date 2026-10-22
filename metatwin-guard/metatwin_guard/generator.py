"""Deterministic synthetic telemetry generator (evidence level B, Section 3.9).

Labels come from the generator, not from physical logs. Every parameter below
is a modelling assumption of the synthetic benchmark, not a field measurement.
"""
from __future__ import annotations

import copy
import hashlib
import random
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any

from . import config
from .crypto import deterministic_private_key
from .events import SoftwareSensor, tamper_features
from .topology import SENSORS

START_TIME = datetime(2026, 8, 23, 0, 0, 0, tzinfo=timezone.utc)

# Sensors whose node is affected by each operational scenario.
AFFECTED = {
    "wan_failover": ("sA-edge", "sB-edge"),
    "vpn_degradation": ("s-vpn",),
    "wifi_auth_surge": ("sA-wifi", "sB-wifi"),
    "power_transition": ("sA-power", "sA-edge"),
}
# Generator transport-delay model (ms): scenario-level offset of ingest time.
INGEST_DELAY_MS = {
    "wan_failover": (155.0, 12.0),
    "vpn_degradation": (160.0, 12.0),
}
DEFAULT_INGEST_DELAY_MS = (46.0, 6.0)
BENIGN_TRANSIENT_P = 0.065


def run_seed(master_seed: int, scenario: str, rep: int) -> int:
    h = hashlib.sha256(f"{master_seed}/{scenario}/{rep}".encode()).digest()
    return int.from_bytes(h[:8], "big")


def normal_features(rng: random.Random, transients: bool = True) -> dict[str, float]:
    """Ordinary operation, optionally with occasional benign transients (unlabelled)."""
    return ordinary(rng, transients)[0]


def ordinary(rng: random.Random, transients: bool = True) -> tuple[dict[str, float], bool]:
    """Returns (features, had_benign_transient)."""
    x = {
        "rtt_ms": max(1.0, rng.gauss(42.0, 7.0)),
        "jitter_ms": max(0.1, rng.gauss(6.0, 2.0)),
        "loss_pct": max(0.0, rng.gauss(0.3, 0.2)),
        "throughput_mbps": max(1.0, rng.gauss(92.0, 11.0)),
        "auth_failures": float(sum(rng.random() < 0.3 for _ in range(10))),
        "vpn_status": 1.0,
        "power_status": 1.0,
    }
    transient = transients and rng.random() < BENIGN_TRANSIENT_P
    if transient:
        kind = rng.choice(("congestion", "throughput_dip", "auth_burst", "loss_burst"))
        if kind == "congestion":
            x["rtt_ms"] += rng.uniform(40, 170)
            x["jitter_ms"] += rng.uniform(5, 40)
        elif kind == "throughput_dip":
            x["throughput_mbps"] = rng.uniform(3, 45)
            x["rtt_ms"] += rng.uniform(5, 40)
        elif kind == "auth_burst":
            x["auth_failures"] += rng.randint(8, 22)
        else:
            x["loss_pct"] += rng.uniform(1.5, 7.0)
            x["jitter_ms"] += rng.uniform(3, 25)
    return x, transient


def inject(scenario: str, x: dict[str, float], rng: random.Random) -> list[str]:
    """Applies a labelled operational disturbance in place; returns changed features."""
    if scenario == "wan_failover":
        x["rtt_ms"] += rng.uniform(70, 230)
        x["jitter_ms"] += rng.uniform(8, 60)
        x["loss_pct"] += rng.uniform(0.5, 9.0)
        x["throughput_mbps"] *= rng.uniform(0.03, 0.45)
        return ["rtt_ms", "jitter_ms", "loss_pct", "throughput_mbps"]
    if scenario == "vpn_degradation":
        x["rtt_ms"] += rng.uniform(60, 220)
        x["jitter_ms"] += rng.uniform(15, 85)
        x["loss_pct"] += rng.uniform(0.5, 12.0)
        changed = ["rtt_ms", "jitter_ms", "loss_pct"]
        if rng.random() < 0.3:
            x["vpn_status"] = 0.0
            changed.append("vpn_status")
        return changed
    if scenario == "wifi_auth_surge":
        x["auth_failures"] += float(rng.randint(9, 36))
        x["rtt_ms"] += rng.uniform(0, 25)
        return ["auth_failures"]
    if scenario == "power_transition":
        x["power_status"] = 0.0
        changed = ["power_status"]
        if rng.random() < 0.05:
            x["rtt_ms"] += rng.uniform(40, 120)
            x["throughput_mbps"] *= rng.uniform(0.2, 0.6)
            changed += ["rtt_ms", "throughput_mbps"]
        return changed
    raise ValueError(scenario)


def tamper_changes(x: dict[str, float], rng: random.Random) -> dict[str, float]:
    """Adversarial post-signature modification: fake an outage/degradation."""
    choice = rng.choice(("outage", "degradation", "mask_power"))
    if choice == "outage":
        return {"throughput_mbps": rng.uniform(0.0, 4.0), "loss_pct": rng.uniform(15, 60), "rtt_ms": rng.uniform(250, 600)}
    if choice == "degradation":
        return {"rtt_ms": rng.uniform(260, 700), "jitter_ms": rng.uniform(60, 150)}
    return {"power_status": 0.0, "vpn_status": 0.0, "loss_pct": rng.uniform(10, 40)}


@dataclass
class GeneratedRun:
    scenario: str
    rep: int
    seed: int
    registry: dict[str, Any]
    n_baseline: int = config.N_BASELINE
    events: list[dict[str, Any]] = field(default_factory=list)
    labels: list[int] = field(default_factory=list)          # 1 = injected (eval only)
    changed: list[list[str]] = field(default_factory=list)   # manipulated features


def generate_run(scenario: str, rep: int, master_seed: int = config.MASTER_SEED,
                 n_baseline: int = config.N_BASELINE, n_eval: int = config.N_EVAL,
                 n_injected: int = config.N_INJECTED) -> GeneratedRun:
    seed = run_seed(master_seed, scenario, rep)
    rng = random.Random(seed)
    sensors = {
        sid: SoftwareSensor(sid, site, node, deterministic_private_key(sid, master_seed))
        for sid, (site, node) in SENSORS.items()
    }
    run = GeneratedRun(scenario, rep, seed, {sid: s.private_key.public_key() for sid, s in sensors.items()}, n_baseline)
    sensor_ids = list(SENSORS)
    t = START_TIME + timedelta(hours=config.SCENARIOS.index(scenario) * 24 + rep)
    d_mu, d_sd = INGEST_DELAY_MS.get(scenario, DEFAULT_INGEST_DELAY_MS)

    def emit(sid: str, x: dict[str, float], phase: str) -> dict[str, Any]:
        nonlocal t
        t += timedelta(milliseconds=rng.uniform(800, 1200))
        return sensors[sid].emit(x, t, max(5.0, rng.gauss(d_mu, d_sd)), scenario, phase)

    # Healthy-looking past events: what a replay adversary resubmits to mask
    # the current state (feature values are ordinary by construction).
    healthy: list[dict[str, Any]] = []
    for _ in range(n_baseline):
        x, transient = ordinary(rng)
        ev = emit(rng.choice(sensor_ids), x, "baseline")
        run.events.append(ev)
        run.labels.append(0)
        run.changed.append([])
        if not transient:
            healthy.append(ev)

    # Injection window: contiguous block of evaluation slots. For telemetry
    # modification every injected slot is followed by the untampered original,
    # so the window spans 2 * n_injected slots.
    if scenario == "telemetry_modification":
        start = rng.randint(20, n_eval - 2 * n_injected - 20)
        inj_slots = set(range(start, start + 2 * n_injected, 2))
    else:
        start = rng.randint(20, n_eval - n_injected - 20)
        inj_slots = set(range(start, start + n_injected))
    pending_original: dict[str, Any] | None = None

    for slot in range(n_eval):
        injected = slot in inj_slots
        if scenario in AFFECTED:
            sid = rng.choice(AFFECTED[scenario] if injected else sensor_ids)
            x = normal_features(rng, transients=not injected)
            changed = inject(scenario, x, rng) if injected else []
            ev = emit(sid, x, "evaluation")
        elif scenario == "telemetry_modification" and injected:
            # An on-path adversary intercepts a fresh signed event and delivers a
            # modified copy ahead of the original: identifier, sequence and chain
            # are still valid, so only the payload-hash/signature checks can reject it.
            x, transient = ordinary(rng)
            pending_original = emit(rng.choice(sensor_ids), x, "evaluation")
            ch = tamper_changes(pending_original["features"], rng)
            ev = tamper_features(pending_original, ch, fix_payload_hash=rng.random() < 0.5)
            changed = sorted(ch)
        elif pending_original is not None:
            ev, pending_original = pending_original, None
            changed = []
        elif scenario == "replay" and injected:
            ev = copy.deepcopy(rng.choice(healthy[: max(1, len(healthy) - 10)]))
            changed = []
        else:
            x, transient = ordinary(rng)
            ev = emit(rng.choice(sensor_ids), x, "evaluation")
            changed = []
            if not transient:
                healthy.append(ev)
        run.events.append(ev)
        run.labels.append(int(injected))
        run.changed.append(changed)
    return run
