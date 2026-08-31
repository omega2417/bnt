.PHONY: help install dev test reproduce demo selftest params figures clean

PYTHON ?= python3
export PYTHONPATH := src

help:
	@echo "make install    - install the package (no dependencies)"
	@echo "make dev        - install with pytest and matplotlib"
	@echo "make test       - run the full test suite"
	@echo "make selftest   - check selector, guard and reproducibility invariants"
	@echo "make demo       - worked end-to-end governance walkthrough"
	@echo "make reproduce  - regenerate every reported table and figure into results/"
	@echo "make params     - dump the parameter packs to results/parameters.json"
	@echo "make clean      - remove build and result artifacts"

install:
	$(PYTHON) -m pip install -e .

dev:
	$(PYTHON) -m pip install -e ".[dev]"

test:
	$(PYTHON) -m pytest

selftest:
	$(PYTHON) -m acp_sme selftest

demo:
	$(PYTHON) -m acp_sme demo

reproduce:
	$(PYTHON) -m acp_sme reproduce

params:
	@mkdir -p results
	$(PYTHON) -m acp_sme params -o results/parameters.json

figures:
	$(PYTHON) -m acp_sme reproduce

clean:
	rm -rf build dist *.egg-info src/*.egg-info .pytest_cache
	find . -name __pycache__ -type d -exec rm -rf {} +
	rm -rf results/figures results/*.csv results/*.json
