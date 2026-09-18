.PHONY: help install test lint dryrun figures dois all zenodo clean

VERSION := 0.1.0
PY ?= python3

help:
	@echo "install  install the package with development extras"
	@echo "test     run the test suite"
	@echo "lint     run ruff"
	@echo "dryrun   run the protocol dry run (Section 7.7)"
	@echo "figures  regenerate Figures 1-8"
	@echo "dois     check every DOI of the reference list (needs network)"
	@echo "all      test + dryrun + figures"
	@echo "zenodo   build dist-zenodo/evoproto-v$(VERSION).zip"

install:
	$(PY) -m pip install -e ".[dev]"

test:
	$(PY) -m pytest

lint:
	$(PY) -m ruff check src tests scripts

dryrun:
	$(PY) -m evoproto.cli dryrun --output results/dry_run

figures:
	$(PY) -m evoproto.cli figures --output figures

dois:
	$(PY) -m evoproto.cli verify-dois --references docs/references/references.json

all: test dryrun figures

zenodo: all
	$(PY) scripts/make_zenodo_archive.py

clean:
	rm -rf build dist dist-zenodo .pytest_cache .coverage htmlcov
	find . -name __pycache__ -type d -prune -exec rm -rf {} +
