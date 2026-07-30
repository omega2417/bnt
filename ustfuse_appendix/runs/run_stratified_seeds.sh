#!/usr/bin/env bash
set -euo pipefail
BUILD=/home/user/bnt/ustfuse_appendix/build
OUT=/home/user/bnt/ustfuse_appendix/runs/strat
SRC=/home/user/bnt/ustfuse_appendix/src
rm -f "$OUT"/*.csv
WORK=$(mktemp -d); cd "$WORK"
for seed in $(seq 20260730 20260759); do
  "$BUILD/radartwin" "$seed" 400 >/dev/null
  "$BUILD/ustfuse" radartwin_measurements.csv >/dev/null
  python3 "$SRC/analyze_stratified.py" "$WORK" "$seed" "$OUT" >/dev/null
  echo "seed $seed stratified done"
done
rm -rf "$WORK"; echo "STRAT ALL DONE"
