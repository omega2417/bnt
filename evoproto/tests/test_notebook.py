"""The Colab walkthrough notebook is shipped, so it has to stay valid.

These checks are static: they do not execute the notebook, which takes about
half a minute.  Run it end to end with ``make notebook`` (or the nbclient
snippet in the Makefile) before releasing.
"""

import ast
import json
import pathlib

import pytest

NOTEBOOK = (
    pathlib.Path(__file__).resolve().parent.parent / "notebooks" / "evoproto_walkthrough.ipynb"
)


@pytest.fixture(scope="module")
def notebook():
    with open(NOTEBOOK, encoding="utf-8") as handle:
        return json.load(handle)


def test_notebook_is_shipped():
    assert NOTEBOOK.exists(), "the walkthrough notebook is part of the archive"


def test_notebook_is_valid_nbformat(notebook):
    nbformat = pytest.importorskip("nbformat")
    nbformat.validate(nbformat.reads(json.dumps(notebook), as_version=4))


def test_every_code_cell_parses(notebook):
    """A syntax error would only surface when a reader runs the cell."""
    for index, cell in enumerate(notebook["cells"]):
        if cell["cell_type"] != "code":
            continue
        source = "".join(cell["source"])
        try:
            ast.parse(source)
        except SyntaxError as error:  # pragma: no cover - failure path
            pytest.fail(f"cell {index} does not parse: {error}\n{source[:400]}")


def test_notebook_ships_without_stored_outputs(notebook):
    """Outputs are regenerated on run; storing them would bloat the archive."""
    for index, cell in enumerate(notebook["cells"]):
        if cell["cell_type"] == "code":
            assert cell.get("outputs") == [], f"cell {index} carries stored output"
            assert cell.get("execution_count") is None


def test_notebook_carries_a_colab_badge_and_the_right_paths(notebook):
    text = "".join("".join(cell["source"]) for cell in notebook["cells"])
    assert "colab.research.google.com" in text
    assert "evoproto_walkthrough.ipynb" in text
    # a notebook that only works from one machine is not a shareable notebook
    assert "/home/" not in text and "/Users/" not in text


def test_notebook_installs_the_package_when_it_is_missing(notebook):
    text = "".join("".join(cell["source"]) for cell in notebook["cells"])
    assert "pip" in text and "subdirectory=evoproto" in text


def test_notebook_states_that_the_data_are_synthetic(notebook):
    """A reader must not be able to mistake the demonstration for a result."""
    text = "".join("".join(cell["source"]) for cell in notebook["cells"])
    assert "SYNTHETIC" in text
    assert "proves nothing" in text
    assert "H1" in text  # the hypotheses are named as still open
