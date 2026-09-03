# UMSF cyber-range digital twin - reproducibility package v2.0.0
# Standard library only: no virtualenv, no package installation, no network.
#
# Layout of this deposit differs from the upstream reference tree in one way:
# the package lives in src/ and the JSON configuration lives in configs/ and
# scenarios/ so that every machine-readable input has exactly one canonical
# copy. Nothing else was changed; engine_source_hash is computed over *.py
# only and is therefore unaffected by the move.

PY        ?= python3
export PYTHONPATH := src
INVENTORY ?= configs/inventory/demo.json
POLICIES  ?= configs/policies
SCENARIOS ?= scenarios
OUT       ?= results

.PHONY: help all test validate verify demo scenarios doe mc refcheck index manifests clean

help:
	@echo "make test       - 40 automated software checks"
	@echo "make validate   - inventory + evidence histogram (expect 194 SYNTHETIC_DEMO, 4 UNKNOWN)"
	@echo "make verify     - determinism and seed-stream separation"
	@echo "make demo       - three-replicate demonstration run"
	@echo "make scenarios  - the five executed SIM scenarios"
	@echo "make doe        - eight-point exploratory Latin-hypercube sweep"
	@echo "make mc         - demonstration Monte Carlo with sequential stopping"
	@echo "make refcheck   - compare this reproduction against the specification values"
	@echo "make index      - rebuild results/run_index.csv from run artifacts"
	@echo "make manifests  - rebuild manifests/ and SHA256SUMS.txt"
	@echo "make all        - full campaign in the documented order"
	@echo "make clean      - remove generated results (destructive)"

all: test validate verify demo scenarios doe mc refcheck index manifests

test:
	@mkdir -p $(OUT)/verification
	$(PY) tests/run_tests.py | tee $(OUT)/verification/tests.txt

validate:
	@mkdir -p $(OUT)/verification
	$(PY) -m umsf_twin validate --config $(INVENTORY) \
	    --policy $(POLICIES)/safety.json | tee $(OUT)/verification/validate.json

verify:
	@mkdir -p $(OUT)/verification
	$(PY) -m umsf_twin verify --config $(INVENTORY) \
	    --policy $(POLICIES)/safety.json | tee $(OUT)/verification/verify.json

demo:
	$(PY) -m umsf_twin run --config $(INVENTORY) --policy $(POLICIES)/safety.json \
	    --output $(OUT) --run-id demo --replicates 3 --report

scenarios:
	@for f in $(SCENARIOS)/*.json; do \
		name=$$(basename $$f .json); \
		echo "== $$name"; \
		$(PY) -m umsf_twin run --config $$f --policy $(POLICIES)/safety.json \
		    --output $(OUT)/scenarios --run-id $$name --report || exit 1; \
	done

doe:
	$(PY) -m umsf_twin doe --config $(INVENTORY) --policy $(POLICIES)/safety.json \
	    --factors $(POLICIES)/factors.json \
	    --output $(OUT)/doe --count 8 --method lhs --run-id doe

mc:
	@mkdir -p $(OUT)/monte_carlo
	$(PY) -m umsf_twin mc --config $(INVENTORY) --policy $(POLICIES)/safety.json \
	    --metric network.site_a.rtt_p95_ms --replicates 10 --half-width 2.0 \
	    | tee $(OUT)/monte_carlo/monte_carlo.json

refcheck:
	$(PY) scripts/check_reference_values.py --results $(OUT)

index:
	$(PY) scripts/build_run_index.py --results $(OUT) --output $(OUT)/run_index.csv

manifests:
	$(PY) scripts/build_manifests.py --root .

clean:
	rm -rf $(OUT)
	find . -name __pycache__ -type d -prune -exec rm -rf {} +
