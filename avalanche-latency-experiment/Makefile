# Reproduction entry points.  PROFILE selects the campaign size:
#   full   the pre-registered 750-run protocol
#   demo   every factor level, shortened window (Colab default)
#   smoke  a two-minute continuous-integration campaign
PROFILE ?= demo
PY      ?= python3
DATA    ?= data/raw
RESULTS ?= results
DIST    ?= dist/avalanche-latency-experiment.zip

export PYTHONPATH := src

.PHONY: help install info pipeline analyze figures verify reproduce test package clean

help:
	@grep -E '^[a-z-]+:.*?## ' $(MAKEFILE_LIST) | sed 's/:.*## /\t/'

install: ## install the analysis dependencies
	$(PY) -m pip install -r requirements.txt

info: ## print the campaign arithmetic, equations (1)-(4)
	$(PY) -m alp info --profile $(PROFILE)

pipeline: ## schedule + traces + reference dataset + statistics + report
	$(PY) -m alp pipeline --profile $(PROFILE) --data $(DATA) --results $(RESULTS) --clean

analyze: ## re-run the statistics on an existing dataset
	$(PY) -m alp analyze --profile $(PROFILE) --data $(DATA) --results $(RESULTS)

measured: ## analyse real campaign logs already present in $(DATA)
	$(PY) -m alp pipeline --profile full --skip-simulation --data $(DATA) \
		--results $(RESULTS) --provenance MEASURED

verify: ## re-hash every artefact and compare to its manifest
	$(PY) -m alp verify $(DATA) $(RESULTS)

reproduce: ## regenerate everything and diff the derived tables
	$(PY) -m alp reproduce --profile $(PROFILE) --results $(RESULTS)

test: ## run the test suite
	$(PY) -m pytest -q

package: ## build the deterministic Zenodo archive
	$(PY) -m alp package --out $(DIST)

clean: ## remove generated artefacts
	rm -rf $(DATA) $(RESULTS) dist build .pytest_cache
	find . -name __pycache__ -type d -prune -exec rm -rf {} +
