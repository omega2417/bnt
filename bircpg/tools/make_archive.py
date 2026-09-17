#!/usr/bin/env python3
"""Build the Zenodo deposition archive.

    python tools/make_archive.py [--out dist]

Writes ``dist/bircpg-<version>.zip`` containing the sources, tests, notebook,
examples, metadata and documentation -- and nothing else: caches, build
artefacts and generated results are excluded, so the archive is reproducible
from a clean checkout.

The SHA-256 of the archive is printed.  Record it: it is what lets a reader
confirm that the archive they downloaded is the one that was deposited.
"""

from __future__ import annotations

import argparse
import hashlib
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

#: Files and directories to ship, relative to the project root.
INCLUDE = [
    "README.md",
    "ZENODO.md",
    "CHANGELOG.md",
    "LICENSE",
    "CITATION.cff",
    ".zenodo.json",
    "pyproject.toml",
    "requirements.txt",
    "src",
    "tests",
    "notebooks",
    "examples",
    "tools",
]

EXCLUDE_DIRS = {"__pycache__", ".pytest_cache", ".ipynb_checkpoints", "build", "dist", "results"}
EXCLUDE_SUFFIXES = {".pyc", ".pyo"}


def _version() -> str:
    sys.path.insert(0, str(ROOT / "src"))
    from bircpg import __version__

    return __version__


def _files() -> list[Path]:
    collected: list[Path] = []
    for entry in INCLUDE:
        path = ROOT / entry
        if not path.exists():
            raise FileNotFoundError(f"{entry} is listed for the archive but does not exist")
        if path.is_file():
            collected.append(path)
            continue
        for child in sorted(path.rglob("*")):
            if not child.is_file():
                continue
            if any(part in EXCLUDE_DIRS for part in child.relative_to(ROOT).parts):
                continue
            if child.suffix in EXCLUDE_SUFFIXES:
                continue
            collected.append(child)
    return collected


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", default="dist", help="output directory (default: dist)")
    args = parser.parse_args()

    version = _version()
    out_dir = ROOT / args.out
    out_dir.mkdir(parents=True, exist_ok=True)
    stem = f"bircpg-{version}"
    archive = out_dir / f"{stem}.zip"

    files = _files()
    # Deterministic member order and a fixed timestamp keep the archive
    # byte-identical across rebuilds from the same sources.
    with zipfile.ZipFile(archive, "w", zipfile.ZIP_DEFLATED) as zf:
        for path in files:
            arcname = Path(stem) / path.relative_to(ROOT)
            info = zipfile.ZipInfo(str(arcname), date_time=(2026, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o644 << 16
            zf.writestr(info, path.read_bytes())

    digest = hashlib.sha256(archive.read_bytes()).hexdigest()
    size_kb = archive.stat().st_size / 1024
    print(f"wrote {archive.relative_to(ROOT)}  ({len(files)} files, {size_kb:.0f} KiB)")
    print(f"sha256  {digest}")
    print()
    print("Before depositing, complete the placeholders listed in ZENODO.md:")
    print("  authors and ORCIDs, repository URL, the article's DOI, and funding.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
