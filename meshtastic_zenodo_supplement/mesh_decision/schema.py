"""Explicit CSV contract. Features must exist before the decision timestamp."""
import csv
import math
from datetime import datetime, timezone, timedelta
from pathlib import Path

RANGES = {
    "rssi_dbm": (-150, -20), "snr_db": (-30, 30),
    "pdr_5m": (0, 1), "latency_p95_5m_s": (0, 600),
    "aoi_s": (0, 7200), "battery_pct": (0, 100),
    "backup_minutes": (0, 1440), "queue_depth": (0, 100),
    "hop_count": (0, 7), "terminal_available": (0, 1),
    "s0_available": (0, 1), "external_connectivity": (0, 1),
    "deadline_remaining_s": (0, 300),
}
FEATURES = list(RANGES)
BINARY = {"terminal_available", "s0_available", "external_connectivity"}
INTEGER = BINARY | {"queue_depth", "hop_count"}
META = ["event_id", "group_id", "run_id", "node_id", "scenario", "provenance",
        "decision_time", "feature_window_end"]
TARGET = "completed_on_time"
COLUMNS = META + FEATURES

def timestamp(value):
    x = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    if x.tzinfo is None:
        raise ValueError("timestamps require an explicit UTC offset")
    return x.astimezone(timezone.utc)

def validate_row(row, training=False):
    out = dict(row)
    for key in META:
        if not str(row.get(key, "")).strip():
            raise ValueError(f"missing field: {key}")
    if row["node_id"] not in {"M1", "M2", "S0"}:
        raise ValueError("node_id must be M1, M2 or S0")
    if row["scenario"] not in {f"E{i}" for i in range(9)}:
        raise ValueError("scenario must be E0 through E8")
    if row["provenance"] not in {"synthetic", "measured"}:
        raise ValueError("provenance must be synthetic or measured")
    for key, (lo, hi) in RANGES.items():
        try:
            v = float(row[key])
        except (KeyError, TypeError, ValueError) as exc:
            raise ValueError(f"missing or nonnumeric field: {key}") from exc
        if not math.isfinite(v) or not lo <= v <= hi:
            raise ValueError(f"{key} outside [{lo}, {hi}] or nonfinite")
        if key in INTEGER and v != int(v):
            raise ValueError(f"{key} must be an integer")
        out[key] = v
    decision = timestamp(row["decision_time"])
    window = timestamp(row["feature_window_end"])
    if window > decision:
        raise ValueError("future feature_window_end would leak outcome information")
    out["snapshot_age_s"] = (decision-window).total_seconds()
    if training:
        if str(row.get(TARGET)) not in {"0", "1"}:
            raise ValueError("completed_on_time must be 0 or 1 for training")
        observed = timestamp(row.get("outcome_observed_at", ""))
        if observed < decision + timedelta(seconds=out["deadline_remaining_s"]):
            raise ValueError("outcome must be finalized after the decision deadline")
        out[TARGET] = int(row[TARGET])
    return out

def read_csv(path, training=False, strict=True):
    with open(path, encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        if not reader.fieldnames or len(reader.fieldnames) != len(set(reader.fieldnames)):
            raise ValueError("CSV needs a unique header")
        required = set(COLUMNS) | ({TARGET, "outcome_observed_at"} if training else set())
        if required-set(reader.fieldnames):
            raise ValueError("missing columns: " + ", ".join(sorted(required-set(reader.fieldnames))))
        rows = list(reader)
    if not rows:
        raise ValueError("CSV contains no observations")
    seen = set()
    for line, row in enumerate(rows, 2):
        key = (row.get("run_id"), row.get("event_id"))
        if key in seen:
            raise ValueError(f"line {line}: duplicate run_id/event_id; aggregate retransmissions first")
        seen.add(key)
        if strict:
            try:
                validate_row(row, training)
            except (ValueError, TypeError) as exc:
                raise ValueError(f"line {line}: {exc}") from exc
    return rows

def write_csv(path, rows, columns):
    path = Path(path); path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=columns, extrasaction="ignore")
        w.writeheader(); w.writerows(rows)
