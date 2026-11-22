#!/usr/bin/env bash
# Build the Zenodo archives: ebaw-soc-2.0.0.zip (software + data + notebook) and
# ebaw-soc-synth-1.0.0.zip (dataset only, for a separate dataset record).
set -euo pipefail
cd "$(dirname "$0")/.."
python3 tools/build_notebook.py
(cd notebooks && jupyter nbconvert --to notebook --execute --inplace EBAW_Colab.ipynb --ExecutePreprocessor.timeout=1800)
rm -rf notebooks/ebaw_colab notebooks/ebaw_results.zip .pytest_cache tests/__pycache__ ebaw/__pycache__ scripts/__pycache__
mkdir -p "${1:-..}"; OUT=$(cd "${1:-..}" && pwd)
NAME=$(basename "$PWD")
(cd .. && rm -f "$OUT/$NAME.zip" && zip -qrX "$OUT/$NAME.zip" "$NAME" -x "*/__pycache__/*" "*.pyc")
(cd data && rm -f "$OUT/ebaw-soc-synth-1.0.0.zip" && cp ../zenodo/dataset.zenodo.json ebaw-soc-synth-1.0.0/.zenodo.json \
  && zip -qrX "$OUT/ebaw-soc-synth-1.0.0.zip" ebaw-soc-synth-1.0.0 && rm ebaw-soc-synth-1.0.0/.zenodo.json)
echo "archives written to $OUT"
