#!/usr/bin/env bash
# Reproduce all simulation results, figures and tables of the article (steps 1-4, as in v1.0.0),
# then build, validate and benchmark the EBAW-SOC-Synth dataset (steps 5-6) and run the tests (7).
set -euo pipefail
cd "$(dirname "$0")"
python3 scripts/run_experiments.py
python3 scripts/extra_analyses.py > results/extra_log.txt
for f in fig1_sequence fig2_timing fig3_hasse fig4_upset fig5_cfd fig6_cd; do
  (cd scripts && python3 "$f.py" > /dev/null)
done
(cd scripts && python3 analyze.py > ../results/summary_log.txt)
python3 scripts/make_dataset.py
python3 scripts/benchmark_dataset.py > results/dataset_benchmark_log.txt
if python3 -c "import pytest" 2>/dev/null; then python3 -m pytest -q tests; fi
echo "done: see results/, figures/ and data/"
