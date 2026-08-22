"""Deterministic archive builder for the Zenodo deposition.

Zenodo mints a DOI for the exact bytes it receives, so the archive is
built reproducibly: entries are sorted, timestamps are pinned, and the
compression level is fixed.  Building the archive twice from the same
tree yields the same SHA-256.
"""

from __future__ import annotations

import json
import zipfile
from pathlib import Path
from typing import Iterable, List

from . import __version__

#: Fixed DOS timestamp (1980-01-01) so archive bytes do not depend on when
#: the archive was built.
_FIXED_TIME = (1980, 1, 1, 0, 0, 0)

#: Directories and files always included, in deposition order.
INCLUDE: List[str] = [
    "README.md",
    "README_UK.md",
    "LICENSE",
    "LICENSE-DATA",
    "CITATION.cff",
    ".zenodo.json",
    "requirements.txt",
    "Makefile",
    "pyproject.toml",
    "src",
    "notebooks",
    "protocol",
    "contracts",
    "deploy",
    "scripts",
    "tests",
    "docs",
    "results",
]

RAW_DATA = "data"

_SKIP_PARTS = {
    "__pycache__", ".git", ".ipynb_checkpoints", ".pytest_cache", "build",
    "dist", ".mypy_cache", ".venv",
}


def _collect(root: Path, names: Iterable[str]) -> List[Path]:
    out: List[Path] = []
    for name in names:
        target = root / name
        if not target.exists():
            continue
        if target.is_file():
            out.append(target)
            continue
        for path in sorted(target.rglob("*")):
            if path.is_file() and not any(p in _SKIP_PARTS for p in path.parts):
                out.append(path)
    return out


def build_archive(
    root: Path,
    out_path: Path,
    include_raw: bool = True,
    top_level: str | None = None,
) -> Path:
    """Write the deposition archive and its checksum sidecar."""
    root = Path(root).resolve()
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    prefix = top_level or f"avalanche-latency-experiment-{__version__}"

    names = list(INCLUDE) + ([RAW_DATA] if include_raw else [])
    files = _collect(root, names)

    with zipfile.ZipFile(out_path, "w", compression=zipfile.ZIP_DEFLATED,
                         compresslevel=6) as zf:
        for path in files:
            arcname = f"{prefix}/{path.relative_to(root).as_posix()}"
            info = zipfile.ZipInfo(arcname, date_time=_FIXED_TIME)
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o644 << 16
            zf.writestr(info, path.read_bytes())

    from .manifest import sha256_file

    digest = sha256_file(out_path)
    sidecar = out_path.with_suffix(out_path.suffix + ".sha256")
    sidecar.write_text(f"{digest}  {out_path.name}\n", encoding="utf-8")

    listing = out_path.with_suffix(".contents.json")
    listing.write_text(
        json.dumps(
            {
                "archive": out_path.name,
                "sha256": digest,
                "bytes": out_path.stat().st_size,
                "n_entries": len(files),
                "includes_raw_dataset": include_raw,
                "top_level_directory": prefix,
                "entries": [p.relative_to(root).as_posix() for p in files],
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    return out_path
