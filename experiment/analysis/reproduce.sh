#!/usr/bin/env bash
# Full reproduction of every number, table and figure in this deposit.
#
#   bash analysis/reproduce.sh
#
# Runtime: about 2 minutes on 4 cores. Deterministic: every run's world is seeded
# from SHA-256("UMSF-DTCR|<scenario>|<repetition>"), so a rerun reproduces
# runs.csv byte for byte apart from the start_utc column.
set -euo pipefail
cd "$(dirname "$0")/.."
ROOT="$PWD"
export PYTHONPATH="$ROOT"

echo "== 0. environment"
python3 -c "import numpy,scipy,pandas,matplotlib,sys; print(
 'python', sys.version.split()[0], '| numpy', numpy.__version__,
 '| scipy', scipy.__version__, '| pandas', pandas.__version__,
 '| matplotlib', matplotlib.__version__)"

echo "== 1. unit tests of the reference implementation"
python3 -m pytest tests -q 2>/dev/null || python3 tests/test_dtcr.py

echo "== 2. pilot campaign (120 runs)"
python3 harness/campaign.py --phase pilot --reps 5 --outdir data/pilot

echo "== 3. Gate 3: calibration and power analysis -> freezes n per cell"
python3 analysis/pilot_calibration.py > /dev/null
python3 -c "
import json; r=json.load(open('analysis/pilot_report.json'))
print('   n per cell =', r['n_confirmatory_per_cell'],
      '| underpowered:', r['underpowered_contrasts'])"

echo "== 4. confirmatory campaign (1296 runs)"
python3 harness/campaign.py --phase confirmatory --reps 54 --outdir data/simulation

echo "== 5. statistical analysis"
python3 analysis/analyze.py

echo "== 6. data dictionary"
python3 analysis/make_data_dictionary.py

echo "== 7. figures"
python3 analysis/make_figures.py

echo "== 8. checksums"
bash analysis/make_checksums.sh

echo "== 9. provenance and consistency audit (must pass)"
python3 analysis/audit_provenance.py

echo
echo "Reproduction complete. Every figure and every number in"
echo "docs/EXPERIMENT_REPORT.md was regenerated from data/simulation/runs.csv."
