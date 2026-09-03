#!/bin/sh
# Rebuild the distributable ZIP of this deposit.
#
# Run from the package root. The archive is written one directory above, so the
# ZIP is not hashed into itself. Byte-code caches are removed first; manifests
# and checksums are regenerated last, so SHA256SUMS.txt always describes the
# files that are actually shipped.
#
# Re-run this after inserting the reserved Zenodo DOI into README.md,
# CITATION.cff, CHANGELOG.md and zenodo/zenodo_metadata.json.

set -eu

name="umsf-cyberrange-digital-twin-sim-reproducibility-package-v2.0.0"
root="$(pwd)"
base="$(basename "$root")"

if [ "$base" != "$name" ]; then
    echo "run this from the package root ($name)" >&2
    exit 1
fi

find . -name '__pycache__' -type d -prune -exec rm -rf {} + 2>/dev/null || true
find . -name '*.pyc' -delete 2>/dev/null || true

python3 scripts/build_run_index.py --results results --output results/run_index.csv
python3 scripts/build_manifests.py --root .

cd ..
rm -f "$name.zip"
zip -q -r -X "$name.zip" "$name" \
    -x "*/__pycache__/*" "*.pyc" "*/.DS_Store" "*/.git/*"
echo "built $(pwd)/$name.zip"
cd "$name"
sha256sum -c SHA256SUMS.txt > /dev/null && echo "checksums verify"
