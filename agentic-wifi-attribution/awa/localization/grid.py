"""Inference grid: maps between (x, y) metres and flattened cell indices."""

from __future__ import annotations

import numpy as np

from ..config import GridConfig


class Grid:
    """Regular 2-D grid of candidate source locations.

    Cell centres are exposed as flat arrays ``xs``/``ys`` (length ``n_cells``)
    so likelihoods and posteriors are simple 1-D vectors that always sum to 1.
    """

    def __init__(self, cfg: GridConfig):
        self.cfg = cfg
        self.ny, self.nx = cfg.shape()
        xs = cfg.x_min + (np.arange(self.nx) + 0.5) * cfg.resolution
        ys = cfg.y_min + (np.arange(self.ny) + 0.5) * cfg.resolution
        self.gx, self.gy = np.meshgrid(xs, ys)  # shape (ny, nx)
        self.xs = self.gx.ravel()
        self.ys = self.gy.ravel()
        self.n_cells = self.xs.size

    @property
    def cell_area(self) -> float:
        return self.cfg.cell_area

    def coords(self) -> np.ndarray:
        """(n_cells, 2) array of cell-centre coordinates."""
        return np.column_stack([self.xs, self.ys])

    def distances_to(self, point: np.ndarray) -> np.ndarray:
        """Euclidean distance from every cell centre to ``point`` (2,)."""
        return np.hypot(self.xs - point[0], self.ys - point[1])

    def as_image(self, flat: np.ndarray) -> np.ndarray:
        """Reshape a flat per-cell vector back to (ny, nx) for plotting."""
        return flat.reshape(self.ny, self.nx)

    def nearest_index(self, x: float, y: float) -> int:
        return int(np.argmin(np.hypot(self.xs - x, self.ys - y)))
