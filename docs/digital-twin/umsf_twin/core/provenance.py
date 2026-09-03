"""Run identity, hashing and the manifest of section 10.8.

A run is only citable if someone else can recreate it. This module produces
the identifiers and digests that make that possible: canonical config hash,
engine source hash, runtime fingerprint and per-artifact SHA-256.
"""

from __future__ import annotations

import hashlib
import json
import platform
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

__all__ = ["canonical_hash", "file_sha256", "source_tree_hash", "runtime_fingerprint",
           "RunManifest", "utc_now_iso"]


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def canonical_hash(value: Any) -> str:
    """SHA-256 over a canonical JSON serialisation (sorted keys, no spaces)."""

    blob = json.dumps(value, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=False, allow_nan=False).encode("utf-8")
    return hashlib.sha256(blob).hexdigest()


def file_sha256(path: Path, chunk: int = 1 << 20) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for block in iter(lambda: handle.read(chunk), b""):
            digest.update(block)
    return digest.hexdigest()


def source_tree_hash(root: Path, patterns: Iterable[str] = ("*.py",)) -> str:
    """Digest of the engine source, so results can be tied to the code."""

    root = Path(root)
    files: list[Path] = []
    for pattern in patterns:
        files.extend(sorted(root.rglob(pattern)))
    digest = hashlib.sha256()
    for path in sorted(set(files)):
        if "__pycache__" in path.parts:
            continue
        digest.update(str(path.relative_to(root)).encode("utf-8"))
        digest.update(file_sha256(path).encode("utf-8"))
    return digest.hexdigest()


def runtime_fingerprint() -> dict[str, Any]:
    return {
        "python_version": sys.version.split()[0],
        "implementation": platform.python_implementation(),
        "platform": platform.platform(),
        "machine": platform.machine(),
        "hash_randomization_disabled": sys.flags.hash_randomization == 0,
    }


class RunManifest:
    """Collects everything needed to reproduce and audit one run."""

    def __init__(self, run_id: str, experiment_id: str, mode: str,
                 seed: int, engine_version: str) -> None:
        self.data: dict[str, Any] = {
            "schema_version": "2.0.0",
            "run_id": run_id,
            "experiment_id": experiment_id,
            "mode": mode,
            "seed": seed,
            "engine_version": engine_version,
            "created_utc": utc_now_iso(),
            "runtime": runtime_fingerprint(),
            "hashes": {},
            "artifacts": {},
            "parameters": {},
            "policy": {},
            "gates": {},
            "notes": [],
        }

    def set_hash(self, key: str, value: str) -> None:
        self.data["hashes"][key] = value

    def set_policy(self, policy: dict[str, Any]) -> None:
        self.data["policy"] = policy

    def set_parameters(self, histogram: dict[str, int], unknowns: list[str]) -> None:
        self.data["parameters"] = {
            "evidence_histogram": histogram,
            "unknown_count": len(unknowns),
            "unknown_sample": unknowns[:20],
        }

    def set_gates(self, gates: dict[str, Any]) -> None:
        self.data["gates"] = gates

    def note(self, text: str) -> None:
        self.data["notes"].append(text)

    def add_artifact(self, path: Path) -> None:
        path = Path(path)
        self.data["artifacts"][path.name] = {
            "bytes": path.stat().st_size,
            "sha256": file_sha256(path),
        }

    def finalize(self, path: Path) -> Path:
        """Write the manifest atomically, refusing a silent overwrite."""

        path = Path(path)
        if path.exists():
            raise FileExistsError(f"refusing to overwrite existing manifest {path}")
        self.data["manifest_hash"] = canonical_hash(
            {k: v for k, v in self.data.items() if k != "manifest_hash"}
        )
        staging = path.with_suffix(path.suffix + ".partial")
        staging.write_text(json.dumps(self.data, indent=2, ensure_ascii=False,
                                      allow_nan=False), encoding="utf-8")
        staging.replace(path)
        return path
