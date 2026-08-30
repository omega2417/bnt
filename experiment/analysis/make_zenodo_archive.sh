#!/usr/bin/env bash
# Build the Zenodo archive. Refuses to package unless the provenance audit passes.
set -euo pipefail
cd "$(dirname "$0")/.."
ROOT="$PWD"
export PYTHONPATH="$ROOT"

VERSION="2.0.0-experiment"
NAME="dtcr-umsf-cyberrange-${VERSION}"
OUT="${1:-$ROOT/..}"

echo "== gate: unit tests"
python3 tests/test_dtcr.py > /dev/null

echo "== gate: provenance and consistency audit"
if ! python3 analysis/audit_provenance.py > /dev/null; then
  echo "AUDIT FAILED - refusing to build the archive." >&2
  python3 analysis/audit_provenance.py || true
  exit 1
fi

echo "== refreshing checksums"
bash analysis/make_checksums.sh

echo "== packaging"
STAGE="$(mktemp -d)"
trap 'rm -rf "$STAGE"' EXIT
mkdir -p "$STAGE/$NAME"
tar -cf - \
  --exclude='__pycache__' --exclude='*.pyc' --exclude='.pytest_cache' \
  --exclude='data/_rerun_check' \
  . | (cd "$STAGE/$NAME" && tar -xf -)

ZIP="$OUT/${NAME}.zip"
rm -f "$ZIP"
(cd "$STAGE" && zip -qr "$ZIP" "$NAME")

echo
echo "  archive : $ZIP"
echo "  size    : $(du -h "$ZIP" | cut -f1)"
echo "  files   : $(unzip -l "$ZIP" | tail -1 | awk '{print $2}')"
echo "  sha256  : $(sha256sum "$ZIP" | cut -d' ' -f1)"
echo
echo "Upload this file to Zenodo using the fields in ZENODO_METADATA.md."
