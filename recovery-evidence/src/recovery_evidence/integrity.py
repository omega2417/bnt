"""SHA-256 manifest of the released outputs (``SHA256SUMS.txt``)."""
from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Dict, List, Tuple

MANIFEST = "SHA256SUMS.txt"
EXCLUDED = {MANIFEST, "run_manifest.json", "README.md"}  # the run manifest stores the UTC time of the run


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for block in iter(lambda: fh.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def tracked(results: Path) -> List[Path]:
    return sorted(p for p in Path(results).rglob("*") if p.is_file() and p.name not in EXCLUDED)


def write_manifest(results: Path) -> int:
    results = Path(results)
    files = tracked(results)
    lines = [f"{sha256(p)}  {p.relative_to(results).as_posix()}" for p in files]
    (results / MANIFEST).write_text("\n".join(lines) + "\n", encoding="utf-8")
    return len(files)


def read_manifest(results: Path) -> Dict[str, str]:
    out = {}
    for line in (Path(results) / MANIFEST).read_text(encoding="utf-8").splitlines():
        digest, name = line.split("  ", 1)
        out[name] = digest
    return out


def verify(results: Path) -> Tuple[List[str], List[str], List[str]]:
    """Compare files with the manifest: (matching, differing, absent)."""
    results = Path(results)
    ok, bad, absent = [], [], []
    for name, digest in read_manifest(results).items():
        path = results / name
        if not path.exists():
            absent.append(name)
        elif sha256(path) == digest:
            ok.append(name)
        else:
            bad.append(name)
    return ok, bad, absent
