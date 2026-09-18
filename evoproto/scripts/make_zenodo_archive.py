#!/usr/bin/env python3
"""Build the Zenodo upload archive for evoproto.

The archive contains the package, its tests, documentation and examples, plus
the generated artefacts a reviewer would otherwise have to produce themselves:
the eight figures of the paper and the JSON outputs of the dry run, the case
study and the ablation, each carrying the corpus snapshot hash that produced it.

Usage
-----
    python scripts/make_zenodo_archive.py [--outdir dist] [--skip-artifacts]

The build is deterministic apart from file timestamps: all generated numbers are
derived from content-addressed seeds, so re-running it on another machine
produces byte-identical JSON and identical figures.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import zipfile
from pathlib import Path
from typing import Iterable, List

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "src"

#: Files and directories that go into the archive, relative to the project root.
INCLUDE = [
    "README.md",
    "LICENSE",
    "CITATION.cff",
    "CHANGELOG.md",
    ".zenodo.json",
    "pyproject.toml",
    "requirements.txt",
    "Makefile",
    "src",
    "tests",
    "docs",
    "examples",
    "scripts",
]

EXCLUDE_PARTS = {"__pycache__", ".pytest_cache", ".git", ".ipynb_checkpoints", ".mypy_cache"}
EXCLUDE_SUFFIXES = {".pyc", ".pyo", ".orig", ".rej"}


def _keep(path: Path) -> bool:
    if any(part in EXCLUDE_PARTS for part in path.parts):
        return False
    return path.suffix not in EXCLUDE_SUFFIXES


def _iter_files(entries: Iterable[str]) -> List[Path]:
    files: List[Path] = []
    for entry in entries:
        target = ROOT / entry
        if not target.exists():
            continue
        if target.is_file():
            if _keep(target):
                files.append(target)
        else:
            files.extend(sorted(p for p in target.rglob("*") if p.is_file() and _keep(p)))
    return files


def build_artifacts(destination: Path) -> List[Path]:
    """Regenerate the figures and the JSON results shipped with the archive."""
    sys.path.insert(0, str(SRC))
    from evoproto.casestudy import run_case_study          # noqa: E402
    from evoproto.data import PACKAGE_VERSION              # noqa: E402
    from evoproto.experiment import ablation, dry_run      # noqa: E402
    from evoproto.figures import generate_all              # noqa: E402

    figures_dir = destination / "figures"
    results_dir = destination / "results"
    figures_dir.mkdir(parents=True, exist_ok=True)
    results_dir.mkdir(parents=True, exist_ok=True)

    produced = [Path(p) for p in generate_all(str(figures_dir))]

    payloads = {
        "dry_run.json": dry_run(),
        "case_study.json": run_case_study(),
        "ablation.json": ablation(),
    }
    for name, payload in payloads.items():
        path = results_dir / name
        path.write_text(json.dumps(payload, indent=2, default=str) + "\n", encoding="utf-8")
        produced.append(path)

    readme = results_dir / "README.md"
    readme.write_text(
        "# Generated artefacts\n\n"
        f"Produced by evoproto {PACKAGE_VERSION} with\n\n"
        "    evoproto figures --outdir figures\n"
        "    evoproto dry-run --out results/dry_run.json\n"
        "    evoproto case-study --out results/case_study.json\n"
        "    evoproto ablation --out results/ablation.json\n\n"
        "Every number in these files is tagged `SYNTHETIC`: they validate the\n"
        "pipeline, not the hypotheses H1-H3 of the paper. Each file carries the\n"
        "content-addressed corpus snapshot hash under which it was produced, so\n"
        "a re-run on any machine can be compared against it directly.\n",
        encoding="utf-8",
    )
    produced.append(readme)
    return produced


def run_tests() -> bool:
    """Run the test suite; the archive should never ship a failing build."""
    environment = dict(os.environ, PYTHONPATH=str(SRC))
    completed = subprocess.run(
        [sys.executable, "-m", "pytest", "-q", str(ROOT / "tests")],
        cwd=str(ROOT), env=environment, capture_output=True, text=True,
    )
    sys.stdout.write(completed.stdout[-2000:])
    if completed.returncode != 0:
        sys.stderr.write(completed.stderr[-2000:])
    return completed.returncode == 0


def main(argv: List[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--outdir", default=str(ROOT / "dist"))
    parser.add_argument("--version", default=None, help="override the version in the file name")
    parser.add_argument("--skip-artifacts", action="store_true",
                        help="do not regenerate figures and results")
    parser.add_argument("--skip-tests", action="store_true", help="do not run the test suite first")
    args = parser.parse_args(argv)

    sys.path.insert(0, str(SRC))
    from evoproto.data import PACKAGE_VERSION  # noqa: E402

    version = args.version or PACKAGE_VERSION
    outdir = Path(args.outdir)
    outdir.mkdir(parents=True, exist_ok=True)
    stage = outdir / f"evoproto-{version}"
    if stage.exists():
        shutil.rmtree(stage)
    stage.mkdir(parents=True)

    if not args.skip_tests:
        print("running the test suite ...")
        if not run_tests():
            print("tests failed; refusing to build the archive", file=sys.stderr)
            return 1

    for path in _iter_files(INCLUDE):
        relative = path.relative_to(ROOT)
        target = stage / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(path, target)

    if not args.skip_artifacts:
        print("regenerating figures and results ...")
        build_artifacts(stage)

    archive = outdir / f"evoproto-{version}.zip"
    if archive.exists():
        archive.unlink()
    with zipfile.ZipFile(archive, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as handle:
        for path in sorted(p for p in stage.rglob("*") if p.is_file()):
            handle.write(path, path.relative_to(outdir))

    size_mb = archive.stat().st_size / 1e6
    with zipfile.ZipFile(archive) as handle:
        count = len(handle.namelist())
        broken = handle.testzip()
    if broken is not None:  # pragma: no cover - defensive
        print(f"archive is corrupt at {broken}", file=sys.stderr)
        return 1

    print(f"\n{archive}  ({count} files, {size_mb:.2f} MB)")
    print("upload this file to Zenodo; .zenodo.json inside it carries the record metadata")
    return 0


if __name__ == "__main__":
    sys.exit(main())
