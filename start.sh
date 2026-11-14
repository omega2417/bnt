#!/usr/bin/env sh
set -eu
cd "$(CDPATH='' cd -- "$(dirname -- "$0")" && pwd)"
PYTHON=${PYTHON:-python3}
if [ ! -x .venv/bin/python ]; then
    "$PYTHON" -m venv .venv
fi
if [ ! -f .venv/.satqkd-ready ]; then
    .venv/bin/python -m pip install -r requirements.txt
    touch .venv/.satqkd-ready
fi
exec .venv/bin/python run.py "$@"
