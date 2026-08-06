.PHONY: help install test quickstart suite campaign clean

PY ?= python3
export PYTHONPATH := src
export MPLBACKEND := Agg

help:
	@echo "UST-Fuse Cyber Range digital twin"
	@echo "  make install     install the package (editable) + dev deps"
	@echo "  make test        run the test suite"
	@echo "  make quickstart  run one mission + report -> out/quickstart"
	@echo "  make suite       run all scenarios -> out/suite"
	@echo "  make campaign    run a 20-mission paired campaign -> out/campaign_S04"
	@echo "  make clean       remove generated outputs"

install:
	$(PY) -m pip install -e ".[dev]"

test:
	$(PY) -m pytest tests/ -q

quickstart:
	$(PY) examples/quickstart.py

suite:
	$(PY) scripts/run_suite.py --out out/suite

campaign:
	$(PY) scripts/run_campaign.py S04_sensor_dropout -n 20 --out out/campaign_S04

clean:
	rm -rf out runs **/__pycache__ .pytest_cache
