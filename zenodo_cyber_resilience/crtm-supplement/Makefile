PY ?= python3

.PHONY: all reproduce test notebook listing clean
all: reproduce test notebook listing

reproduce:
	$(PY) scripts/reproduce.py

test:
	$(PY) -m pytest -q

notebook:
	$(PY) tools/build_notebook.py

listing:
	$(PY) tools/build_listing.py

clean:
	rm -rf results/figures results/tables results/*.json results/*.csv .pytest_cache */__pycache__
