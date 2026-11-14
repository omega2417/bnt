.PHONY: all test tables figures notebook clean

PY ?= python3
export PYTHONPATH := $(CURDIR)

all: test tables figures notebook

test:
	$(PY) -m pytest -q

tables:
	$(PY) scripts/reproduce_link_numbers.py
	$(PY) scripts/table_geo.py results/geo_table.json

figures:
	mkdir -p figures
	$(PY) scripts/fig_schemes.py figures
	$(PY) scripts/fig_constellation.py figures/fig_constellation.png
	$(PY) scripts/fig_sky.py figures/fig_sky.png
	$(PY) scripts/fig_geo_results.py figures

notebook:
	$(PY) -m jupyter nbconvert --to notebook --execute --ExecutePreprocessor.timeout=600 notebooks/demo_satqkd_sentinel.ipynb --output demo_satqkd_sentinel_executed.ipynb

clean:
	rm -rf figures/*.png results/*.json __pycache__ */__pycache__ .pytest_cache
