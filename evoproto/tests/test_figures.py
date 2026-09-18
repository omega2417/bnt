"""Figure regeneration (every figure of the article is produced by code)."""

from __future__ import annotations

import matplotlib

matplotlib.use("Agg")

import pytest

from evoproto.figures import FIGURES, render_all


def test_every_article_figure_has_a_builder():
    assert sorted(FIGURES) == [f"fig{i}" for i in range(1, 9)]


@pytest.mark.parametrize("name", ["fig1", "fig2", "fig4", "fig5", "fig6", "fig8"])
def test_schematic_figures_render(tmp_path, name):
    paths = render_all(tmp_path, names=[name], formats=("png",))
    assert len(paths) == 1
    assert paths[0].exists() and paths[0].stat().st_size > 5_000


@pytest.mark.slow
def test_data_figures_render(tmp_path):
    paths = render_all(tmp_path, names=["fig3", "fig7"], formats=("png",))
    assert all(path.exists() for path in paths)
