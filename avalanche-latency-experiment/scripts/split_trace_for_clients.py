#!/usr/bin/env python3
"""Split an immutable trace into the per-workstation slices.

Each of the 25 Kali generators replays only its own rows, so the union of
the slices is exactly the trace and no two generators ever share a probe
key or an account.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from alp.config import N_CLIENTS, get_profile  # noqa: E402
from alp.traces import TraceSpec, build_trace  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--profile", default="full")
    parser.add_argument("--load-tps", type=int, required=True)
    parser.add_argument("--repeat", type=int, required=True)
    parser.add_argument("--out", default="traces")
    args = parser.parse_args()

    profile = get_profile(args.profile)
    spec = TraceSpec(args.load_tps, args.repeat, profile.measure_s, N_CLIENTS)
    trace = build_trace(spec)
    out_dir = Path(args.out) / spec.trace_id
    out_dir.mkdir(parents=True, exist_ok=True)
    for client_id, group in trace.groupby("client_id"):
        path = out_dir / f"{client_id}.csv"
        group.to_csv(path, index=False, lineterminator="\n", float_format="%.9f")
    print(f"{spec.trace_id}: {len(trace)} tx split across "
          f"{trace.client_id.nunique()} clients -> {out_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
