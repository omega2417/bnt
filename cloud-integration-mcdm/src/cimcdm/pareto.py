"""Dominance filtering and Pareto-front utilities for minimization problems."""

from __future__ import annotations

import numpy as np


def nondominated_mask(F: np.ndarray) -> np.ndarray:
    """Boolean mask of the nondominated rows of ``F`` (all objectives minimized).

    Uses the standard sort-and-sweep filter: rows are visited in lexicographic
    order, so once a row survives it can only be dominated by an earlier survivor.
    """
    F = np.atleast_2d(np.asarray(F, dtype=float))
    if len(F) == 0:
        return np.zeros(0, dtype=bool)

    order = np.lexsort(F.T[::-1])
    ordered = F[order]
    keep = np.ones(len(ordered), dtype=bool)

    for i in range(len(ordered)):
        if not keep[i]:
            continue
        rest = ordered[i + 1 :]
        if len(rest) == 0:
            break
        dominated = np.all(ordered[i] <= rest, axis=1) & np.any(ordered[i] < rest, axis=1)
        keep[i + 1 :][dominated] = False

    mask = np.zeros(len(F), dtype=bool)
    mask[order[keep]] = True
    return mask


def nondominated_sort(F: np.ndarray) -> list[np.ndarray]:
    """Partition rows of ``F`` into successive nondominated fronts."""
    F = np.atleast_2d(np.asarray(F, dtype=float))
    remaining = np.arange(len(F))
    fronts: list[np.ndarray] = []
    while len(remaining):
        mask = nondominated_mask(F[remaining])
        fronts.append(remaining[mask])
        remaining = remaining[~mask]
    return fronts


def unique_rows(X: np.ndarray, F: np.ndarray, decimals: int = 12):
    """Drop duplicate decision vectors, keeping the first occurrence."""
    X = np.atleast_2d(X)
    _, index = np.unique(np.round(X, decimals), axis=0, return_index=True)
    index = np.sort(index)
    return X[index], np.atleast_2d(F)[index]


class ParetoArchive:
    """Persistent nondominated archive, updated once per generation.

    Keeps decision vectors alongside objective vectors and removes duplicates,
    so that archive size is a meaningful diversity statistic.
    """

    def __init__(self) -> None:
        self.X: np.ndarray | None = None
        self.F: np.ndarray | None = None

    def update(self, X: np.ndarray, F: np.ndarray) -> "ParetoArchive":
        X = np.atleast_2d(np.asarray(X, dtype=float))
        F = np.atleast_2d(np.asarray(F, dtype=float))
        if len(X) == 0:
            return self
        if self.X is None:
            merged_X, merged_F = X, F
        else:
            merged_X = np.vstack([self.X, X])
            merged_F = np.vstack([self.F, F])
        merged_X, merged_F = unique_rows(merged_X, merged_F)
        mask = nondominated_mask(merged_F)
        self.X, self.F = merged_X[mask], merged_F[mask]
        return self

    def __len__(self) -> int:
        return 0 if self.F is None else len(self.F)

    @property
    def front(self) -> np.ndarray:
        return np.zeros((0, 3)) if self.F is None else self.F
