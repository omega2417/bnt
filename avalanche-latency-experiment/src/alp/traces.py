"""Immutable workload traces (protocol section 4.2).

For each ``load x repeat`` pair the campaign pre-computes one arrival
trace: inter-arrival times, the owning client, the probe key and the
monotonic sequence number.  Every configuration and topology replays the
*same* trace, which is what allows the paired bootstrap of section 11.

Traces are stochastic but pre-generated: a client replays timestamps, it
never draws new random intervals while a run is in flight.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd

from .config import N_CLIENTS, derive_seed

TRACE_COLUMNS = [
    "seq",
    "client_id",
    "t_offset_s",
    "key_hex",
    "value",
]


@dataclass(frozen=True)
class TraceSpec:
    """Identity of one immutable trace."""

    load_tps: int
    repeat: int
    duration_s: int
    n_clients: int = N_CLIENTS

    @property
    def trace_id(self) -> str:
        return f"L{self.load_tps}-R{self.repeat:02d}"


def build_trace(spec: TraceSpec) -> pd.DataFrame:
    """Generate the arrival trace for one ``load x repeat`` pair.

    Arrivals are a homogeneous Poisson process of rate ``load_tps``,
    thinned to exactly ``load_tps * duration_s`` scheduled transactions so
    that the denominator of the availability metric (equation 10) is a
    protocol constant rather than a random variable.  Transactions are
    dealt round-robin to the ``n_clients`` generators, so every client has
    its own account and a conflict-free local nonce range.
    """
    n_total = int(spec.load_tps * spec.duration_s)
    rng = np.random.default_rng(
        derive_seed("trace", spec.load_tps, spec.repeat, spec.duration_s)
    )

    # Poisson arrivals, then rescale onto the window so the count is exact.
    gaps = rng.exponential(scale=1.0 / spec.load_tps, size=n_total)
    t = np.cumsum(gaps)
    t = t * (spec.duration_s / t[-1]) if t[-1] > 0 else t
    t = np.clip(t - t[0], 0.0, spec.duration_s)

    seq = np.arange(1, n_total + 1, dtype=np.int64)
    client = seq % spec.n_clients  # 0..n_clients-1, deterministic round robin

    # The probe key is per client: monotonicity of `seq` is enforced by the
    # contract per key, so keys must not be shared between generators.
    key_hex = np.array(
        [
            "0x" + hashlib.blake2b(
                f"{spec.trace_id}|client{c:02d}".encode("utf-8"), digest_size=32
            ).hexdigest()
            for c in range(spec.n_clients)
        ]
    )[client]

    value = rng.integers(1, 2**31 - 1, size=n_total, dtype=np.int64)

    return pd.DataFrame(
        {
            "seq": seq,
            "client_id": [f"K{c:02d}" for c in client],
            "t_offset_s": t,
            "key_hex": key_hex,
            "value": value,
        }
    )[TRACE_COLUMNS]


def trace_sha256(trace: pd.DataFrame) -> str:
    """Content hash of a trace, independent of file formatting."""
    payload = trace.to_csv(index=False, lineterminator="\n", float_format="%.9f")
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def write_trace(spec: TraceSpec, out_dir: Path) -> Path:
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    trace = build_trace(spec)
    path = out_dir / f"{spec.trace_id}.csv"
    trace.to_csv(path, index=False, lineterminator="\n", float_format="%.9f")
    return path


def build_all_traces(profile, out_dir: Path | None = None) -> pd.DataFrame:
    """Build (and optionally persist) every trace required by a profile.

    Returns the trace registry: one row per trace with its SHA-256, which
    goes into the run manifest so a reviewer can prove that the same
    workload was replayed under every configuration.
    """
    rows = []
    for load in profile.loads_tps:
        for repeat in range(1, profile.repeats + 1):
            spec = TraceSpec(load, repeat, profile.measure_s)
            trace = build_trace(spec)
            digest = trace_sha256(trace)
            if out_dir is not None:
                path = write_trace(spec, out_dir)
            else:
                path = None
            rows.append(
                {
                    "trace_id": spec.trace_id,
                    "load_tps": load,
                    "repeat": repeat,
                    "duration_s": spec.duration_s,
                    "n_tx": len(trace),
                    "n_clients": spec.n_clients,
                    "sha256": digest,
                    "path": str(path) if path else "",
                }
            )
    return pd.DataFrame(rows)
