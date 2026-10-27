"""Class tables and level-consistent normalization (Section 5).

Implements
  * Definition 6  – class table xi, quality anchors eta = sigma * xi,
                    tabulated level lambda_xi (eq. 9);
  * eq. (10)      – two-anchor linear normalization n_{c,h};
  * Theorem 1     – existence test for a consistent clipped affine map;
  * Corollary 1   – interval of class-4 values sent to the band "high";
  * Definition 7  – anchored piecewise-linear normalization nu_xi (eq. 12);
  * a numerical grid check of consistency (Section 7.1).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable, Sequence

import numpy as np

from .scale import Y, level


class ClassTableError(ValueError):
    """Raised when a class table violates the ordering condition (8)."""


@dataclass(frozen=True)
class ClassTable:
    """Class table xi in R^6 of a metric (Definition 6).

    Parameters
    ----------
    xi : six anchors (xi_0, ..., xi_5) in physical units.
    sigma : polarity, +1 if larger values mean more resilience, -1 otherwise.
        If omitted it is inferred from the order of xi_0 and xi_4.
    """

    xi: tuple[float, ...]
    sigma: int | None = None
    eta: np.ndarray = field(init=False, repr=False, compare=False)

    def __post_init__(self):
        xi = tuple(float(v) for v in self.xi)
        if len(xi) != 6:
            raise ClassTableError("a class table has exactly six anchors")
        sigma = self.sigma
        if sigma is None:
            sigma = 1 if xi[4] > xi[0] else -1
        if sigma not in (1, -1):
            raise ClassTableError("polarity must be +1 or -1")
        eta = sigma * np.asarray(xi)
        object.__setattr__(self, "xi", xi)
        object.__setattr__(self, "sigma", int(sigma))
        object.__setattr__(self, "eta", eta)
        self.validate()

    # ------------------------------------------------------------------ checks
    def validate(self) -> None:
        """Check condition (8): eta0 <= eta1 < eta2 < eta3 < eta4 <= eta5."""
        e = self.eta
        ok = e[0] <= e[1] < e[2] < e[3] < e[4] <= e[5]
        if not ok:
            raise ClassTableError(
                f"anchors violate (8): eta = {tuple(np.round(e, 6))}")

    # --------------------------------------------------------- tabulated level
    def tabulated_level(self, x):
        """Level lambda_xi(x) that the class table assigns to x (eq. 9)."""
        u = self.sigma * np.asarray(x, dtype=float)
        e = self.eta
        r = np.searchsorted(e[1:5], u, side="right") + 1
        r = np.where(np.isnan(u), 0, r)
        return int(r) if np.ndim(r) == 0 else r.astype(int)

    # ---------------------------------------------------------- normalizations
    def linear(self, x):
        """Two-anchor linear normalization n_{c,h} with c = xi_0, h = xi_4 (eq. 10)."""
        c, h = self.xi[0], self.xi[4]
        out = np.clip((np.asarray(x, dtype=float) - c) / (h - c), 0.0, 1.0)
        return float(out) if out.ndim == 0 else out

    def anchored(self, x):
        """Anchored piecewise-linear normalization nu_xi (Definition 7, eq. 12).

        Degenerate segments (eta_r = eta_{r+1}, possible for r = 0 and r = 4)
        are skipped. At a degenerate critical anchor eta_0 = eta_1 the value
        at u = eta_1 is y_1, so that nu_xi is consistent with xi on all of R
        (Theorem 2a).
        """
        u = self.sigma * np.atleast_1d(np.asarray(x, dtype=float))
        e = self.eta
        out = np.full(u.shape, np.nan)
        out[u <= e[0]] = 0.0
        for r in range(5):
            if e[r] < e[r + 1]:
                m = (u >= e[r]) & (u < e[r + 1])
                out[m] = Y[r] + (Y[r + 1] - Y[r]) * (u[m] - e[r]) / (e[r + 1] - e[r])
        out[u >= e[5]] = 1.0
        if e[4] == e[5]:
            out[u >= e[4]] = 1.0
        out[np.isnan(u)] = np.nan
        return float(out[0]) if np.ndim(x) == 0 else out

    def normalize(self, x, method: str = "anchored"):
        """Dispatch to ``linear`` or ``anchored``."""
        if method == "linear":
            return self.linear(x)
        if method == "anchored":
            return self.anchored(x)
        raise ValueError(f"unknown normalization {method!r}")

    # ---------------------------------------------------------- theory checks
    def affine_consistent(self, rtol: float = 1e-9) -> tuple[bool, float | None, float | None]:
        """Theorem 1: does a consistent clipped affine map a*u + b exist?

        Returns (exists, a, b). Condition (11): equal consecutive slopes
        (eta_{r+1} - eta_r) / (y_{r+1} - y_r) for r = 1, 2, 3.
        """
        e = self.eta
        slopes = [(e[r + 1] - e[r]) / (Y[r + 1] - Y[r]) for r in (1, 2, 3)]
        exists = bool(np.allclose(slopes, slopes[0], rtol=rtol, atol=0.0))
        if not exists:
            return False, None, None
        a = 1.0 / slopes[0]
        b = Y[1] - a * e[1]
        return True, float(a), float(b)

    def corollary1_interval(self) -> dict:
        """Corollary 1: class-4 values that n_{c,h} maps into the band 'high'.

        Returns the interval in quality coordinates u = sigma*x, the same
        interval in physical units and its length
        min{eta4 - eta3, (1 - y4)(eta4 - eta0)}.
        """
        e = self.eta
        lo = max(e[3], e[0] + Y[4] * (e[4] - e[0]))
        hi = e[4]
        length = min(e[4] - e[3], (1 - Y[4]) * (e[4] - e[0]))
        if self.sigma == 1:
            phys = {"from": float(lo), "to": float(hi), "closed": "[from, to)"}
        else:
            phys = {"from": float(-hi), "to": float(-lo), "closed": "(from, to]"}
        return {"u_interval": (float(lo), float(hi)), "x_interval": phys,
                "length": float(length)}

    def anchors_with_neighbours(self, eps: float = 1e-9) -> np.ndarray:
        """Physical anchors and points within eps of them (for grid checks)."""
        pts = []
        for v in self.xi:
            pts += [v - eps, v, v + eps]
        return np.asarray(pts)


# ---------------------------------------------------------------- utilities
def is_consistent(table: ClassTable, norm: Callable, xs: Sequence[float]) -> np.ndarray:
    """Boolean array: lambda(n(x)) == lambda_xi(x) for each x in xs."""
    xs = np.asarray(xs, dtype=float)
    return level(norm(xs)) == table.tabulated_level(xs)


def grid_check(table: ClassTable, method: str = "anchored", n: int = 20001,
               margin: float = 0.25, eps: float = 1e-9) -> dict:
    """Numerical consistency check on a dense grid plus all anchors ± eps.

    The grid covers [min xi - margin*span, max xi + margin*span].
    """
    lo, hi = min(table.xi), max(table.xi)
    span = hi - lo
    xs = np.concatenate([np.linspace(lo - margin * span, hi + margin * span, n),
                         table.anchors_with_neighbours(eps)])
    ok = is_consistent(table, lambda v: table.normalize(v, method), xs)
    return {"points": int(xs.size), "violations": int((~ok).sum()),
            "worst_x": xs[~ok].tolist()[:10]}
