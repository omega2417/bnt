#!/usr/bin/env python3
"""Build the two deliverables from the working tree.

    python tools/build_archives.py supplement   # journal e-component (compact)
    python tools/build_archives.py release      # archive deposit (complete logs)

Both archives are deterministic: sorted entries, fixed time stamps.
"""
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
VERSION = "1.0.0"
STAMP = (2026, 11, 23, 0, 0, 0)
CODE = ["README.md", "LICENSE", "CITATION.cff", "CHANGELOG.md", "codemeta.json", ".zenodo.json",
        "pyproject.toml", "Makefile", ".gitignore"]
SKIP = {"__pycache__", ".pytest_cache"}


def walk(base: Path):
    for p in sorted(base.rglob("*")):
        if p.is_file() and not (set(p.parts) & SKIP) and p.suffix != ".pyc" and ".egg-info" not in str(p):
            yield p


def add(zf: zipfile.ZipFile, src: Path, arc: str) -> None:
    info = zipfile.ZipInfo(arc, STAMP)
    info.compress_type = zipfile.ZIP_STORED if src.suffix in (".gz", ".png", ".zip") else zipfile.ZIP_DEFLATED
    info.external_attr = 0o644 << 16
    zf.writestr(info, src.read_bytes(), compresslevel=9)


def build(kind: str) -> Path:
    full = kind == "release"
    top = f"recovery-evidence-{VERSION}" if full else "Supplementary_Material_S1"
    out = ROOT / "dist" / f"{top}.zip"
    out.parent.mkdir(exist_ok=True)
    files = [(ROOT / f, f) for f in CODE]
    for folder in ("src", "tests", "docs", "supplementary", "tools"):
        files += [(p, p.relative_to(ROOT).as_posix()) for p in walk(ROOT / folder)]
    missing = []
    for p in walk(ROOT / "results"):
        rel = p.relative_to(ROOT).as_posix()
        if p.name == "run_manifest.json":
            continue
        if not full:
            bulky = p.suffix == ".gz" and "/logs/C0/" not in rel
            if bulky or p.suffix == ".png":
                continue
        files.append((p, rel))
    if full:
        names = {rel for _, rel in files}
        for line in (ROOT / "results" / "SHA256SUMS.txt").read_text().splitlines():
            rel = "results/" + line.split("  ", 1)[1]
            if rel not in names:
                missing.append(rel)
    if missing:
        raise SystemExit("release needs the complete results; run `recovery-evidence reproduce --check` first.\n"
                         "missing: " + ", ".join(missing[:5]))
    with zipfile.ZipFile(out, "w") as zf:
        for src, rel in sorted(files, key=lambda x: x[1]):
            add(zf, src, f"{top}/{rel}")
    print(f"{out.relative_to(ROOT)}  {out.stat().st_size / 1e6:.1f} MB  {len(files)} files")
    return out


if __name__ == "__main__":
    if len(sys.argv) != 2 or sys.argv[1] not in ("supplement", "release"):
        raise SystemExit(__doc__)
    build(sys.argv[1])
