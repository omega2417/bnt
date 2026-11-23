.PHONY: help install dev test test-all checks example reproduce verify figures supplement release clean

PYTHON ?= python3
export PYTHONPATH := src

help:
	@echo "make install     - install the package (NumPy only)"
	@echo "make dev         - install with pytest and matplotlib"
	@echo "make checks      - the 27 implementation checks of Section 4.6"
	@echo "make example     - the worked example of Section 3.4"
	@echo "make test        - test suite without the slow regeneration tests"
	@echo "make test-all    - full test suite"
	@echo "make reproduce   - regenerate every log, table and figure and compare with SHA256SUMS.txt"
	@echo "make verify      - compare the files in results/ with SHA256SUMS.txt"
	@echo "make supplement  - build dist/Supplementary_Material_S1.zip (journal e-component)"
	@echo "make release     - build dist/recovery-evidence-<version>.zip (archive deposit, full logs)"

install:
	$(PYTHON) -m pip install -e .

dev:
	$(PYTHON) -m pip install -e ".[dev]"

checks:
	$(PYTHON) -m recovery_evidence checks

example:
	$(PYTHON) -m recovery_evidence example
	$(PYTHON) supplementary/worked_example.py

test:
	$(PYTHON) -m pytest -m "not slow"

test-all:
	$(PYTHON) -m pytest

reproduce:
	$(PYTHON) -m recovery_evidence reproduce --check

verify:
	$(PYTHON) -m recovery_evidence verify

figures:
	$(PYTHON) -m recovery_evidence figures

supplement:
	$(PYTHON) tools/build_archives.py supplement

release:
	$(PYTHON) tools/build_archives.py release

clean:
	rm -rf build *.egg-info src/*.egg-info .pytest_cache dist/*/
	find . -name __pycache__ -type d -exec rm -rf {} +
