#!/usr/bin/env python3
"""Portable source entry point. Usage: python run.py demo."""
import sys

if sys.version_info < (3,10):
    raise SystemExit('Python 3.10 or newer is required.')
try:
    from satqkd_sentinel.cli import main
except ModuleNotFoundError as exc:
    raise SystemExit(f'Missing dependency: {exc.name}. Run: python -m pip install -r requirements.txt') from exc

if __name__ == '__main__':
    raise SystemExit(main())
