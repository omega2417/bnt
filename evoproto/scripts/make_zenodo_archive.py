#!/usr/bin/env python3
"""Build the Zenodo deposit archive.

The archive is a self-contained snapshot of everything a reader needs to
reproduce the article: source, tests, documentation, notebooks, regenerated
figures, the dry-run results with their environment record, the exact dependency
pins, and the citation metadata.

Two things are generated on the way in:

* ``SHA256SUMS`` - one line per file, so a depositor can prove later that the
  uploaded bytes are the ones that were built here;
* ``ARCHIVE_MANIFEST.md`` - a human-readable inventory with sizes, checksums and
  the role of each part, which is what a reviewer actually reads.

Run ``make zenodo`` (which runs the tests, the dry run and the figures first) so
that the archive cannot contain stale results.
"""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT = ROOT / "dist-zenodo"

#: (path, required, description) - directories are taken whole.
CONTENTS: list[tuple[str, bool, str]] = [
    ("README.md", True, "overview, install, usage"),
    ("LICENSE", True, "MIT license for the software"),
    ("LICENSE-DOCS", True, "CC BY 4.0 for documentation and figures"),
    ("CITATION.cff", True, "citation metadata (software and article)"),
    ("codemeta.json", True, "CodeMeta software metadata"),
    (".zenodo.json", True, "Zenodo deposit metadata"),
    ("CHANGELOG.md", True, "release history"),
    ("CONTRIBUTING.md", False, "how to collaborate on the code"),
    ("CODE_OF_CONDUCT.md", False, "collaboration ground rules"),
    ("pyproject.toml", True, "build and packaging configuration"),
    ("requirements.txt", True, "runtime dependencies (loose bounds)"),
    ("requirements-lock.txt", True, "exact versions used to produce the archive"),
    ("Makefile", True, "one-command reproduction targets"),
    ("src", True, "the evoproto package"),
    ("tests", True, "test suite pinning every equation and rule"),
    ("docs", True, "datasheet, model card, pre-registration, reproducibility, checklists"),
    ("notebooks", True, "Colab-ready notebooks"),
    ("figures", True, "regenerated figures (PDF and PNG)"),
    ("results", True, "archived dry-run output with its environment record"),
    ("scripts", True, "this archive builder"),
    (".github", False, "continuous-integration workflow"),
]

EXCLUDE_PARTS = {"__pycache__", ".pytest_cache", ".ipynb_checkpoints", ".git",
                 "dist-zenodo", ".ruff_cache", "htmlcov"}
EXCLUDE_SUFFIXES = {".pyc", ".pyo"}


def _iter_files(path: Path) -> list[Path]:
    if path.is_file():
        return [path]
    files = []
    for candidate in sorted(path.rglob("*")):
        if not candidate.is_file():
            continue
        if EXCLUDE_PARTS & set(candidate.parts):
            continue
        if candidate.suffix in EXCLUDE_SUFFIXES:
            continue
        files.append(candidate)
    return files


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def _human(size: int) -> str:
    for unit in ("B", "KB", "MB", "GB"):
        if size < 1024 or unit == "GB":
            return f"{size:.0f} {unit}" if unit == "B" else f"{size:.1f} {unit}"
        size /= 1024.0
    return f"{size:.1f} GB"


def collect(strict: bool = True) -> tuple[list[Path], list[tuple[str, str]]]:
    """Return the files to archive and the (path, description) inventory."""
    files: list[Path] = []
    inventory: list[tuple[str, str]] = []
    missing: list[str] = []
    for name, required, description in CONTENTS:
        path = ROOT / name
        if not path.exists():
            if required:
                missing.append(name)
            continue
        found = _iter_files(path)
        if not found and required:
            missing.append(name)
            continue
        files.extend(found)
        inventory.append((name, description))
    if missing and strict:
        raise SystemExit(
            "cannot build the archive, these required items are missing: "
            + ", ".join(missing)
            + "\nrun 'make all' first (tests, dry run, figures)."
        )
    return files, inventory


def build(version: str, output_dir: Path, strict: bool = True) -> Path:
    files, inventory = collect(strict=strict)
    output_dir.mkdir(parents=True, exist_ok=True)
    stem = f"evoproto-v{version}"
    archive_path = output_dir / f"{stem}.zip"

    records = []
    for path in files:
        relative = path.relative_to(ROOT)
        records.append(
            {"path": str(relative), "size": path.stat().st_size, "sha256": _sha256(path)}
        )
    records.sort(key=lambda record: record["path"])

    checksums = "\n".join(f"{r['sha256']}  {r['path']}" for r in records) + "\n"
    manifest = _manifest(version, records, inventory)

    with zipfile.ZipFile(archive_path, "w", compression=zipfile.ZIP_DEFLATED,
                         compresslevel=9) as archive:
        for path in files:
            archive.write(path, arcname=f"{stem}/{path.relative_to(ROOT)}")
        archive.writestr(f"{stem}/SHA256SUMS", checksums)
        archive.writestr(f"{stem}/ARCHIVE_MANIFEST.md", manifest)

    (output_dir / "SHA256SUMS").write_text(checksums, encoding="utf-8")
    (output_dir / "ARCHIVE_MANIFEST.md").write_text(manifest, encoding="utf-8")

    total = sum(r["size"] for r in records)
    print(f"{archive_path}")
    print(f"  {len(records)} files, {_human(total)} uncompressed, "
          f"{_human(archive_path.stat().st_size)} compressed")
    print(f"  archive sha256: {_sha256(archive_path)}")
    return archive_path


def _manifest(version: str, records: list[dict], inventory: list[tuple[str, str]]) -> str:
    today = dt.date.today().isoformat()
    environment = "not recorded"
    results = ROOT / "results/dry_run/results.json"
    if results.exists():
        payload = json.loads(results.read_text(encoding="utf-8"))
        environment = json.dumps(payload.get("environment", {}), indent=2, sort_keys=True)

    lines = [
        f"# evoproto v{version} - archive manifest",
        "",
        f"Built {today} by `scripts/make_zenodo_archive.py`.",
        "",
        "## What this archive is",
        "",
        "The reference implementation of the evolution-informed, evidence-gated design",
        "framework described in the accompanying article, together with everything",
        "needed to reproduce its figures and its dry run: source, tests, documentation,",
        "notebooks, regenerated figures, archived results and exact dependency pins.",
        "",
        "**No biological records are included.** The demonstration pipeline runs in",
        "SYNTHETIC mode only; every number it produces carries a provenance tag and",
        "supports no empirical claim.",
        "",
        "## Contents",
        "",
        "| Item | Role |",
        "|---|---|",
    ]
    lines += [f"| `{name}` | {description} |" for name, description in inventory]
    lines += [
        "| `SHA256SUMS` | checksum of every file in this archive |",
        "| `ARCHIVE_MANIFEST.md` | this file |",
        "",
        "## Reproducing",
        "",
        "```bash",
        "pip install -r requirements-lock.txt && pip install -e .",
        "pytest            # the full test suite",
        "evoproto dryrun   # Section 7.7",
        "evoproto figures  # Figures 1-8",
        "```",
        "",
        "## Environment of the archived results",
        "",
        "```json",
        environment,
        "```",
        "",
        "## Licensing",
        "",
        "Software: MIT (`LICENSE`). Documentation and figures: CC BY 4.0",
        "(`LICENSE-DOCS`). Records retrieved from Open Tree of Life, MorphoBank and the",
        "Paleobiology Database remain under their own licenses and are not redistributed",
        "here; see `docs/datasheet.md`.",
        "",
        "## File inventory",
        "",
        "| File | Size | SHA-256 |",
        "|---|---|---|",
    ]
    lines += [
        f"| `{r['path']}` | {_human(r['size'])} | `{r['sha256'][:16]}…` |" for r in records
    ]
    lines += ["", f"{len(records)} files."]
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--version", default=None, help="defaults to evoproto.__version__")
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT))
    parser.add_argument("--allow-missing", action="store_true",
                        help="build even if required items are absent (for testing)")
    args = parser.parse_args(argv)

    version = args.version
    if version is None:
        sys.path.insert(0, str(ROOT / "src"))
        from evoproto import __version__ as version
    build(version, Path(args.output), strict=not args.allow_missing)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
