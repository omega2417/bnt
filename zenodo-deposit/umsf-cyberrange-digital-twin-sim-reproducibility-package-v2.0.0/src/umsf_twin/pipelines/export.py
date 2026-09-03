"""Artifact writers with atomic publication and no silent overwrite."""

from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any, Iterable, Sequence

from ..core.contracts import validate_strict_json

__all__ = ["write_csv", "write_json", "write_jsonl", "ensure_run_dir"]


def ensure_run_dir(root: str | Path, run_id: str) -> Path:
    path = Path(root) / run_id
    if path.exists() and any(path.iterdir()):
        raise FileExistsError(f"run directory {path} already exists and is not empty")
    path.mkdir(parents=True, exist_ok=True)
    return path


def _publish(staging: Path, target: Path) -> Path:
    staging.replace(target)
    return target


def write_csv(path: str | Path, rows: Sequence[dict[str, Any]],
              fieldnames: Sequence[str] | None = None) -> Path:
    path = Path(path)
    names = list(fieldnames or (rows[0].keys() if rows else []))
    staging = path.with_suffix(path.suffix + ".partial")
    with staging.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=names, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow(row)
    return _publish(staging, path)


def write_json(path: str | Path, payload: Any) -> Path:
    validate_strict_json(payload)
    path = Path(path)
    staging = path.with_suffix(path.suffix + ".partial")
    staging.write_text(json.dumps(payload, indent=2, ensure_ascii=False,
                                  allow_nan=False), encoding="utf-8")
    return _publish(staging, path)


def write_jsonl(path: str | Path, records: Iterable[dict[str, Any]]) -> Path:
    path = Path(path)
    staging = path.with_suffix(path.suffix + ".partial")
    with staging.open("w", encoding="utf-8") as handle:
        for record in records:
            validate_strict_json(record)
            handle.write(json.dumps(record, ensure_ascii=False, allow_nan=False) + "\n")
    return _publish(staging, path)
