# Reproduction pipeline for the DTCR deposit.
#
#   make all         regenerate data, statistics, NRI, figures and the report
#   make data        (re)generate the SYNTHETIC reference dataset - see PROVENANCE.md
#   make analysis    statistics + NRI recomputation from whatever is in data/
#   make figures     regenerate every manuscript figure
#   make verify      check the deposit for internal consistency and submission readiness
#   make clean       remove generated results and figures
#
# Replacing data/ with real measurement exports and running `make analysis figures`
# reproduces the whole Results section without editing any analysis code.

PY ?= python3
DATA ?= data
RESULTS ?= results
FIGURES ?= figures
CONFIG ?= configs/framework_parameters.yaml

.PHONY: all data analysis figures verify report clean

all: analysis figures verify

data:
	$(PY) analysis/simulate_reference_dataset.py --out $(DATA)

analysis:
	$(PY) analysis/statistics.py --data $(DATA) --out $(RESULTS)
	$(PY) analysis/calculate_nri.py --data $(DATA) --configs $(CONFIG) --out $(RESULTS) --strict

figures:
	$(PY) analysis/generate_figures.py --data $(DATA) --results $(RESULTS) --out $(FIGURES)

verify:
	$(PY) analysis/verify_repository.py --root .

clean:
	rm -rf $(RESULTS) $(FIGURES)
