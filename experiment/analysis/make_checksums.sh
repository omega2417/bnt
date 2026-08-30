#!/usr/bin/env bash
# Rebuild checksums/SHA256SUMS over every deposited artefact.
set -euo pipefail
cd "$(dirname "$0")/.."
mkdir -p checksums
find . -type f \
  ! -path './checksums/*' \
  ! -name '*.pyc' \
  ! -path '*/__pycache__/*' \
  -print0 | sort -z | xargs -0 sha256sum > checksums/SHA256SUMS
echo "  $(wc -l < checksums/SHA256SUMS) files hashed -> checksums/SHA256SUMS"
