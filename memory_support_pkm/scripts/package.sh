#!/usr/bin/env bash
# Run everything, execute the Colab notebook and build dist/pgmem_project.zip
set -euo pipefail
cd "$(dirname "$0")/.."
python3 -m pytest -q tests
python3 scripts/run_all.py --boot 300
python3 scripts/build_notebook.py
python3 scripts/execute_notebook.py notebooks/PGMem_Colab.ipynb
rm -rf dist && mkdir -p dist
cp notebooks/PGMem_Colab.ipynb dist/
(cd .. && zip -qr memory_support_pkm/dist/pgmem_project.zip memory_support_pkm \
    -x 'memory_support_pkm/dist/*' '*/__pycache__/*' '*/.pytest_cache/*')
ls -la dist
