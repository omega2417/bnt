#!/usr/bin/env bash
# Reproduce every result of the article from a clean checkout.
#
# Usage:  bash scripts/reproduce_all.sh [output_dir]
#
# Exits non-zero if any validation check fails, so it can be used as a CI gate.

set -euo pipefail

OUTPUT="${1:-results}"
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

export PYTHONPATH="$ROOT/src:${PYTHONPATH:-}"
export MPLBACKEND=Agg

echo "=== environment ==="
python3 --version
python3 - <<'PY'
for name in ("numpy", "scipy", "pandas", "matplotlib"):
    module = __import__(name)
    print(f"{name} {module.__version__}")
PY

echo
echo "=== unit and reproduction tests ==="
python3 -m pytest tests -q

echo
echo "=== full study: enumeration, algorithms, statistics, sensitivity, figures ==="
python3 -m cimcdm all -o "$OUTPUT"

echo
echo "Results written to $OUTPUT/"
