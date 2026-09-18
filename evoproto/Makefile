# Convenience targets for evoproto.
PYTHON ?= python3
export PYTHONPATH := src

.PHONY: help install test figures dry-run case-study ablation zenodo clean

help:
	@echo "install    install the package in editable mode with dev extras"
	@echo "test       run the test suite"
	@echo "figures    regenerate Figs. 1-8 into ./figures"
	@echo "dry-run    run the synthetic protocol dry run (Section 7.7)"
	@echo "case-study run the EOAT bracket case study (Section 6)"
	@echo "zenodo     build the Zenodo upload archive into ./dist"
	@echo "clean      remove build artefacts and caches"

install:
	$(PYTHON) -m pip install -e ".[dev]"

test:
	$(PYTHON) -m pytest -q

figures:
	$(PYTHON) -m evoproto.cli figures --outdir figures

dry-run:
	$(PYTHON) -m evoproto.cli dry-run

case-study:
	$(PYTHON) -m evoproto.cli case-study

ablation:
	$(PYTHON) -m evoproto.cli ablation --out results/ablation.json

zenodo:
	$(PYTHON) scripts/make_zenodo_archive.py

clean:
	rm -rf dist build figures results .pytest_cache
	find . -name '__pycache__' -type d -prune -exec rm -rf {} +
	find . -name '*.pyc' -delete
