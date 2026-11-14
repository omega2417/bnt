.PHONY: all demo test tables figures notebook clean
PY ?= python3
export PYTHONPATH := $(CURDIR)
all: test tables figures demo

demo:
	$(PY) run.py demo

test:
	$(PY) -m pytest -q

tables:
	$(PY) scripts/reproduce_link_numbers.py
	$(PY) scripts/table_geo.py results/geo_table.json

figures:
	$(PY) scripts/fig_schemes.py figures
	$(PY) scripts/fig_constellation.py figures/fig_constellation.png
	$(PY) scripts/fig_sky.py figures/fig_sky.png
	$(PY) scripts/fig_geo_results.py figures

notebook:
	$(PY) scripts/execute_notebook.py

clean:
	$(PY) scripts/clean.py
