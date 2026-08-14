#!/usr/bin/env bash
# Reproduce the full publication campaign (paper_v1) from scratch.
# All tables and figures are written under artifacts/<kind>/paper_v1/.
set -euo pipefail

cd "$(dirname "$0")/.."

echo "[aegis] installing package (editable)..."
python -m pip install -e . >/dev/null

echo "[aegis] running full paper_v1 campaign (this is slow: 20 seeds)..."
aegis campaign --config configs/experiments/paper_v1.yaml

echo "[aegis] done. Artifacts:"
echo "  tables : artifacts/tables/paper_v1/"
echo "  figures: artifacts/figures/paper_v1/"
echo "  metrics: artifacts/metrics/paper_v1/"
echo "  manifests: artifacts/manifests/"
