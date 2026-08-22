"""SHA-256 manifests and reproducibility verification (protocol 14).

Every run, every derived table and every figure is hashed.  ``build``
writes ``MANIFEST.sha256`` (the machine-readable form) plus a JSON
sidecar carrying the environment, the seeds and the provenance label.
``verify`` re-hashes and reports additions, deletions and mismatches, so
a reviewer can prove that a regenerated dataset is bit-identical.
"""

from __future__ import annotations

import hashlib
import json
import platform
import sys
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Iterable, List, Optional

from . import __version__
from .config import (
    DATA_REQUIRED_FIELDS,
    MASTER_SEED,
    THRESHOLDS,
    TIMEZONE,
    get_profile,
)

MANIFEST_NAME = "MANIFEST.sha256"
SIDECAR_NAME = "MANIFEST.json"

#: Directories never hashed: caches and the manifest files themselves.
_SKIP_DIRS = {"__pycache__", ".git", ".ipynb_checkpoints", ".pytest_cache"}


def sha256_file(path: Path, chunk: int = 1 << 20) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        while True:
            block = fh.read(chunk)
            if not block:
                break
            h.update(block)
    return h.hexdigest()


def iter_files(root: Path) -> List[Path]:
    root = Path(root)
    out = []
    for path in sorted(root.rglob("*")):
        if not path.is_file():
            continue
        if any(part in _SKIP_DIRS for part in path.parts):
            continue
        if path.name in {MANIFEST_NAME, SIDECAR_NAME}:
            continue
        out.append(path)
    return out


def build(
    root: Path,
    profile_name: str,
    provenance: str,
    extra: Optional[Dict[str, object]] = None,
) -> Dict[str, object]:
    """Hash every file under ``root`` and write both manifest forms."""
    root = Path(root)
    files = iter_files(root)
    entries = [
        {"path": str(p.relative_to(root)), "sha256": sha256_file(p), "bytes": p.stat().st_size}
        for p in files
    ]
    lines = "".join(f"{e['sha256']}  {e['path']}\n" for e in entries)
    (root / MANIFEST_NAME).write_text(lines, encoding="utf-8")

    profile = get_profile(profile_name)
    sidecar: Dict[str, object] = {
        "generated_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "timezone_of_record": TIMEZONE,
        "package": f"alp {__version__}",
        "python": sys.version.split()[0],
        "platform": platform.platform(),
        "master_seed": MASTER_SEED,
        "campaign_profile": profile.as_dict(),
        "stability_thresholds": THRESHOLDS.as_dict(),
        "provenance": provenance,
        "n_files": len(entries),
        "total_bytes": sum(e["bytes"] for e in entries),
        "files": entries,
        "data_required_fields": DATA_REQUIRED_FIELDS,
    }
    if provenance != "MEASURED":
        sidecar["warning"] = (
            "This dataset is not a measurement of the cyber range. Values "
            "derived from it must not be reported as experimental results."
        )
    if extra:
        sidecar.update(extra)
    (root / SIDECAR_NAME).write_text(
        json.dumps(sidecar, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return sidecar


def verify(root: Path) -> Dict[str, object]:
    """Re-hash ``root`` and compare against its manifest."""
    root = Path(root)
    manifest_path = root / MANIFEST_NAME
    if not manifest_path.exists():
        raise FileNotFoundError(f"no {MANIFEST_NAME} under {root}")

    recorded = {}
    for line in manifest_path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        digest, rel = line.split("  ", 1)
        recorded[rel] = digest

    present = {str(p.relative_to(root)): sha256_file(p) for p in iter_files(root)}

    mismatched = sorted(k for k in recorded.keys() & present.keys() if recorded[k] != present[k])
    missing = sorted(recorded.keys() - present.keys())
    unexpected = sorted(present.keys() - recorded.keys())
    return {
        "root": str(root),
        "n_recorded": len(recorded),
        "n_present": len(present),
        "mismatched": mismatched,
        "missing": missing,
        "unexpected": unexpected,
        "ok": not (mismatched or missing or unexpected),
    }


def compare_trees(a: Path, b: Path, patterns: Iterable[str] = ("*.csv", "*.json")) -> Dict[str, object]:
    """Compare two result trees file by file.

    Used by ``alp verify --rerun`` to prove that a second execution of the
    pipeline reproduces the first one byte for byte.
    """
    a, b = Path(a), Path(b)
    names = set()
    for pattern in patterns:
        names |= {p.relative_to(a).as_posix() for p in a.rglob(pattern)}
        names |= {p.relative_to(b).as_posix() for p in b.rglob(pattern)}
    identical, differing, only_a, only_b = [], [], [], []
    for name in sorted(names):
        pa, pb = a / name, b / name
        if pa.exists() and pb.exists():
            (identical if sha256_file(pa) == sha256_file(pb) else differing).append(name)
        elif pa.exists():
            only_a.append(name)
        else:
            only_b.append(name)
    return {
        "identical": identical,
        "differing": differing,
        "only_in_first": only_a,
        "only_in_second": only_b,
        "ok": not (differing or only_a or only_b),
    }
