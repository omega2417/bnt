"""Build the Zenodo archive dist/crtm-ois-<version>.zip (English release)."""
from __future__ import annotations

import hashlib
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
VERSION = "1.0.0"
INCLUDE = ["crtm_ois", "tests", "data", "results", "figures", "scripts", "notebooks/CRTM_OIS_demo.ipynb",
           "README.md", "CHANGELOG.md", "CITATION.cff", ".zenodo.json", "LICENSE", "LICENSE-DATA",
           "pyproject.toml", "requirements.txt", ".gitignore"]
EXCLUDE_NAMES = {"__pycache__", ".pytest_cache", ".ipynb_checkpoints", "build_notebook_ua.py", "make_release.py"}


def files():
    for item in INCLUDE:
        p = ROOT / item
        if p.is_file():
            yield p
        else:
            for f in sorted(p.rglob("*")):
                if f.is_file() and not (set(f.relative_to(ROOT).parts) & EXCLUDE_NAMES) and f.suffix != ".pyc":
                    yield f


def main():
    out = ROOT / "dist"
    out.mkdir(exist_ok=True)
    zp = out / f"crtm-ois-{VERSION}.zip"
    top = f"crtm-ois-{VERSION}"
    n = 0
    with zipfile.ZipFile(zp, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as z:
        for f in files():
            z.write(f, f"{top}/{f.relative_to(ROOT).as_posix()}")
            n += 1
    md5 = hashlib.md5(zp.read_bytes()).hexdigest()
    print(f"{zp}  files={n}  size={zp.stat().st_size/1e6:.2f} MB  md5={md5}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
