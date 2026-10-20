#!/usr/bin/env bash
# One command that regenerates every number and figure of the
# reproducibility package: checks, tests, benchmarks, analysis, figures.
set -euo pipefail
cd "$(dirname "$0")/.."
GO=${GO:-go}
PY=${PYTHON:-python3}

echo "== gofmt"
unformatted=$(gofmt -l bench)
if [ -n "$unformatted" ]; then echo "gofmt needed: $unformatted"; exit 1; fi
echo "== go vet"
$GO vet ./bench/...
echo "== go test"
$GO test -count=1 ./bench/...

bash scripts/run_benchmarks.sh

echo "== platform ranking (Figure 2)"
$PY scripts/platform_ranking.py
$PY scripts/figure2.py
echo "== benchmark analysis (Tables 6 and 7, Figure 4)"
$PY scripts/analyze_bench.py
$PY scripts/figure4.py
echo "done: see results/ and figures/"
