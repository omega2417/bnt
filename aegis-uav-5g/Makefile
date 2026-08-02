.PHONY: help install install-dev lint type test smoke paper clean docker-build docker-run

PY ?= python
RUN_GROUP ?= smoke

help:
	@echo "Aegis-UAV-5G - reproducible research pipeline"
	@echo ""
	@echo "  make install        Install the package"
	@echo "  make install-dev    Install with dev extras (pytest, ruff, mypy)"
	@echo "  make lint           Run ruff"
	@echo "  make type           Run mypy"
	@echo "  make test           Run pytest"
	@echo "  make smoke          Run the fast end-to-end smoke campaign (2-3 seeds)"
	@echo "  make paper          Run the full paper_v1 campaign (20+ seeds)"
	@echo "  make docker-build   Build the Docker image"
	@echo "  make docker-run     Run the smoke campaign inside Docker"
	@echo "  make clean          Remove generated artifacts and datasets"

install:
	$(PY) -m pip install -e .

install-dev:
	$(PY) -m pip install -e ".[dev]"

lint:
	ruff check src tests

type:
	mypy

test:
	pytest

# Full reproducible smoke campaign: one command -> all tables + figures.
smoke:
	aegis campaign --config configs/experiments/smoke.yaml

# Full publication campaign (slow).
paper:
	aegis campaign --config configs/experiments/paper_v1.yaml

report:
	aegis report --run-group $(RUN_GROUP)

docker-build:
	docker build -t aegis-uav-5g:latest .

docker-run:
	docker run --rm -v $(PWD)/artifacts:/app/artifacts -v $(PWD)/datasets:/app/datasets \
		aegis-uav-5g:latest aegis campaign --config configs/experiments/smoke.yaml

clean:
	rm -rf artifacts/tables/* artifacts/figures/* artifacts/metrics/* \
		artifacts/models/* artifacts/logs/* artifacts/manifests/* \
		datasets/raw/* datasets/interim/* datasets/processed/* datasets/manifests/*
	find artifacts datasets -type d -empty -exec touch {}/.gitkeep \; 2>/dev/null || true
