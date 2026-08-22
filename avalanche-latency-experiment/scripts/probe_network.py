#!/usr/bin/env python3
"""Active RTT/jitter/loss probes taken before, during and after a run.

Protocol Table 8 requires the realised network path to be recorded, not
only the netem target that was requested.  The script pings every peer
listed in ``PROBE_TARGETS`` and appends one JSON object per phase.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List

_STATS = re.compile(
    r"(?P<tx>\d+) packets transmitted, (?P<rx>\d+) received.*?"
    r"(?:(?P<loss>[\d.]+)% packet loss)", re.S
)
_RTT = re.compile(r"= ([\d.]+)/([\d.]+)/([\d.]+)/([\d.]+) ms")


def probe(target: str, count: int, interval: float) -> Dict[str, object]:
    try:
        out = subprocess.run(
            ["ping", "-n", "-q", "-c", str(count), "-i", str(interval), target],
            capture_output=True, text=True, timeout=count * interval + 15,
        ).stdout
    except (OSError, subprocess.TimeoutExpired) as exc:
        return {"target": target, "error": str(exc)}
    record: Dict[str, object] = {"target": target}
    stats = _STATS.search(out)
    if stats:
        record["loss_pct"] = float(stats.group("loss"))
        record["packets"] = int(stats.group("tx"))
    rtt = _RTT.search(out)
    if rtt:
        record.update(
            rtt_min_ms=float(rtt.group(1)),
            rtt_avg_ms=float(rtt.group(2)),
            rtt_max_ms=float(rtt.group(3)),
            jitter_ms=float(rtt.group(4)),
        )
    return record


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--phase", required=True, choices=["before", "during", "after"])
    parser.add_argument("--out", required=True)
    parser.add_argument("--append", action="store_true")
    parser.add_argument("--count", type=int, default=50)
    parser.add_argument("--interval", type=float, default=0.2)
    args = parser.parse_args()

    targets = [t for t in os.environ.get("PROBE_TARGETS", "").split(",") if t]
    if not targets:
        raise SystemExit(
            "set PROBE_TARGETS to a comma-separated list of validator and "
            "read-node addresses"
        )

    entry = {
        "phase": args.phase,
        "utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "netem": os.environ.get("NETEM_DESCRIPTION", "none"),
        "provenance": "MEASURED",
        "probes": [probe(t, args.count, args.interval) for t in targets],
    }

    path = Path(args.out)
    path.parent.mkdir(parents=True, exist_ok=True)
    existing: List[dict] = []
    if args.append and path.exists():
        existing = json.loads(path.read_text(encoding="utf-8"))
    existing.append(entry)
    path.write_text(json.dumps(existing, indent=2) + "\n", encoding="utf-8")
    print(f"{args.phase}: {len(entry['probes'])} targets -> {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
