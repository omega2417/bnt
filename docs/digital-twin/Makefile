# UMSF cyber-range digital twin - reference implementation
# Standard library only: no virtualenv or package installation is required.

PY ?= python3
CONFIG ?= umsf_twin/config/inventory/demo.json
OUT ?= runs

.PHONY: help test validate run verify report doe mc scenarios clean

help:
	@echo "make test        - run the full zero-dependency test suite"
	@echo "make validate    - validate the demo inventory and print the evidence table"
	@echo "make run         - run the demo scenario and write a run directory"
	@echo "make verify      - check determinism and seed separation"
	@echo "make scenarios   - run every scenario in umsf_twin/config/scenarios"
	@echo "make doe         - Latin-hypercube factor sweep"
	@echo "make mc          - Monte Carlo with sequential stopping"
	@echo "make clean       - remove generated runs and caches"

test:
	$(PY) tests/run_tests.py

validate:
	$(PY) -m umsf_twin validate --config $(CONFIG)

run:
	$(PY) -m umsf_twin run --config $(CONFIG) --output $(OUT) --replicates 1 --report

verify:
	$(PY) -m umsf_twin verify --config $(CONFIG)

scenarios:
	@for f in umsf_twin/config/scenarios/*.json; do \
		name=$$(basename $$f .json); \
		echo "== $$name"; \
		$(PY) -m umsf_twin run --config $$f --output $(OUT) --run-id $$name --report || exit 1; \
	done

doe:
	$(PY) -m umsf_twin doe --config $(CONFIG) \
		--factors umsf_twin/config/policies/factors.json \
		--output $(OUT) --count 8 --method lhs --run-id doe

mc:
	$(PY) -m umsf_twin mc --config $(CONFIG) \
		--metric network.site_a.rtt_p95_ms --replicates 10 --half-width 2.0

clean:
	rm -rf $(OUT) .pytest_cache
	find . -name __pycache__ -type d -prune -exec rm -rf {} +
