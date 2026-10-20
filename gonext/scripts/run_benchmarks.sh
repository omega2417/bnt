#!/usr/bin/env bash
# Runs the micro-experiments of Section 2.6 (Experiments 1-4).
#   results/raw/environment.txt  Go version, GOOS/GOARCH, CPU, kernel
#   results/raw/bench.txt        raw `go test -bench` output (10 runs)
#   results/raw/pointervis.csv   Experiment 4, one line per trial
# Packages are run one at a time (-p 1) so that benchmarks of different
# packages never compete for the two benchmark CPUs.
set -euo pipefail
cd "$(dirname "$0")/.."
GO=${GO:-go}
COUNT=${COUNT:-10}
mkdir -p results/raw

{
  echo "date: $(date -u +%Y-%m-%dT%H:%M:%SZ)"
  echo "go version: $($GO version)"
  echo "GOOS GOARCH: $($GO env GOOS GOARCH | tr '\n' ' ')"
  echo "cpu model: $(grep -m1 'model name' /proc/cpuinfo | cut -d: -f2- | sed 's/^ *//')"
  echo "cpus online: $(nproc)"
  echo "memory: $(grep MemTotal /proc/meminfo | awk '{printf "%.1f GiB", $2/1048576}')"
  echo "kernel: $(uname -srm)"
  echo "GOMAXPROCS (benchmarks): 2"
  echo "GOGC: ${GOGC:-default}"
  echo "command: GOMAXPROCS=2 $GO test -p 1 -run='^\$' -bench=. -benchmem -count=$COUNT ./bench/..."
} > results/raw/environment.txt
cat results/raw/environment.txt

echo "== equivalence tests"
$GO test -count=1 ./bench/...

echo "== benchmarks (count=$COUNT), this takes several minutes"
GOMAXPROCS=2 $GO test -p 1 -run='^$' -bench=. -benchmem -count="$COUNT" ./bench/... \
  | tee results/raw/bench.txt

echo "== Experiment 4 (pointer visibility)"
GOMAXPROCS=2 $GO run ./bench/pointervis/cmd/pointervis -trials 10 -nodes 10000 -cycles 5 \
  | tee results/raw/pointervis.csv
