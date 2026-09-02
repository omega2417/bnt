#!/usr/bin/env bash
# Build the ZIP that gets uploaded to Zenodo.
#
# Usage:  bash scripts/make_zenodo_archive.sh [version]
#
# Ships source, data, notebook, tests, scripts and metadata. Excludes generated
# results, caches and VCS state so the archive is a clean, self-contained
# snapshot that a reviewer can unzip and run.

set -euo pipefail

VERSION="${1:-1.0.0}"
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
NAME="cimcdm-${VERSION}"
BUILD="$(mktemp -d)"
STAGE="$BUILD/$NAME"

cleanup() { rm -rf "$BUILD"; }
trap cleanup EXIT

mkdir -p "$STAGE"
cd "$ROOT"

for item in src data notebooks tests scripts docs; do
    [ -e "$item" ] && cp -r "$item" "$STAGE/"
done
for item in README.md LICENSE CITATION.cff .zenodo.json pyproject.toml \
            requirements.txt requirements-colab.txt CHANGELOG.md; do
    [ -e "$item" ] && cp "$item" "$STAGE/"
done

# Strip anything generated or environment-specific.
find "$STAGE" -type d -name '__pycache__'   -prune -exec rm -rf {} +
find "$STAGE" -type d -name '.pytest_cache' -prune -exec rm -rf {} +
find "$STAGE" -type d -name '.ipynb_checkpoints' -prune -exec rm -rf {} +
find "$STAGE" -type f -name '*.pyc' -delete

# Clear notebook outputs so the archive ships a clean, re-runnable notebook.
python3 - "$STAGE" <<'PY'
import json, pathlib, sys

for path in pathlib.Path(sys.argv[1]).rglob("*.ipynb"):
    notebook = json.loads(path.read_text(encoding="utf-8"))
    for cell in notebook.get("cells", []):
        if cell.get("cell_type") == "code":
            cell["outputs"] = []
            cell["execution_count"] = None
    path.write_text(json.dumps(notebook, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"cleared outputs: {path.name}")
PY

cd "$BUILD"
zip -qr "$ROOT/$NAME.zip" "$NAME"
cd "$ROOT"

echo
echo "Built $NAME.zip"
unzip -l "$NAME.zip" | tail -1
echo
echo "Next steps:"
echo "  1. Upload $NAME.zip at https://zenodo.org/uploads/new"
echo "  2. Zenodo reads .zenodo.json from inside the archive for metadata."
echo "  3. Reserve a DOI, then add it to README.md and CITATION.cff before publishing."
