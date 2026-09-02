"""Benchmark instance: the 18 candidate distributed information-processing systems.

Two sources are supported.

``load_published_instance``
    Reads the exact realized values printed in Appendix A of the article.
    This is the canonical instance and the one that reproduces every published
    number, so it is the default everywhere in this package.

``generate_instance``
    A deterministic generator over the bounded ranges quoted in Section 2.4.
    It reproduces the *sampling protocol*, not the original draw order, so the
    instance it returns is a valid new scenario rather than a bit-identical copy
    of Appendix A. Use it to study how the conclusions behave on sibling
    instances, never to re-derive the published tables.
"""

from __future__ import annotations

import csv
from dataclasses import dataclass
from pathlib import Path

import numpy as np

from .config import GENERATOR_SEED

DATA_DIR = Path(__file__).resolve().parents[2] / "data"

# Bounded sampling ranges quoted in Section 2.4 of the article.
PARAMETER_RANGES: dict[str, tuple[float, float]] = {
    "p0": (0.35, 0.58),
    "delta_p": (0.20, 0.48),
    "alpha": (0.08, 0.42),
    "e0": (0.04, 0.16),
    "delta_e": (0.22, 0.60),
    "beta": (0.05, 0.32),
    "technical": (0.56, 0.95),
    "human": (0.48, 0.94),
    "reliability": (0.82, 0.99),
    "risk_initial": (0.34, 0.82),
    "risk_residual": (0.10, 0.30),
    "rho": (0.05, 0.22),
    "criticality": (0.45, 0.99),
}
COST_RANGE = (8, 26)
EFFORT_RANGE = (1, 6)


@dataclass(frozen=True)
class Instance:
    """One fully specified portfolio-selection instance.

    All array attributes have length ``n`` and are indexed consistently by
    system position.
    """

    names: tuple[str, ...]

    # Time-dependent business performance: P_i(t) = p0 + delta_p * (1 - exp(-alpha * t))
    p0: np.ndarray
    delta_p: np.ndarray
    alpha: np.ndarray

    # Time-dependent economic benefit: E_i(t) = e0 + delta_e * (1 - exp(-beta * t))
    e0: np.ndarray
    delta_e: np.ndarray
    beta: np.ndarray

    # Static per-system attributes.
    technical: np.ndarray
    human: np.ndarray
    reliability: np.ndarray
    criticality: np.ndarray
    cost: np.ndarray
    effort: np.ndarray

    # Residual risk: r_i(t) = risk_residual + (risk_initial - risk_residual) * exp(-rho * t)
    risk_initial: np.ndarray
    risk_residual: np.ndarray
    rho: np.ndarray

    source: str = "published"

    @property
    def n(self) -> int:
        return len(self.names)

    def __post_init__(self) -> None:
        n = len(self.names)
        for field_name in (
            "p0", "delta_p", "alpha", "e0", "delta_e", "beta", "technical",
            "human", "reliability", "criticality", "cost", "effort",
            "risk_initial", "risk_residual", "rho",
        ):
            array = getattr(self, field_name)
            if array.shape != (n,):
                raise ValueError(
                    f"{field_name} has shape {array.shape}, expected ({n},)"
                )
        if np.any(self.risk_residual > self.risk_initial):
            raise ValueError("Residual risk must not exceed initial risk")

    def to_frame(self):
        """Return the instance as a pandas DataFrame (one row per system)."""
        import pandas as pd

        return pd.DataFrame(
            {
                "system": self.names,
                "P0": self.p0,
                "dP": self.delta_p,
                "alpha": self.alpha,
                "E0": self.e0,
                "dE": self.delta_e,
                "beta": self.beta,
                "technical": self.technical,
                "human": self.human,
                "reliability": self.reliability,
                "risk_initial": self.risk_initial,
                "risk_residual": self.risk_residual,
                "rho": self.rho,
                "cost": self.cost,
                "effort": self.effort,
                "criticality": self.criticality,
            }
        )


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def load_published_instance(data_dir: Path | str | None = None) -> Instance:
    """Load the 18-system instance exactly as printed in Appendix A.

    Parameters
    ----------
    data_dir:
        Directory holding ``appendix_A1_benefit_parameters.csv`` and
        ``appendix_A2_system_parameters.csv``. Defaults to the packaged ``data/``.
    """
    directory = Path(data_dir) if data_dir is not None else DATA_DIR
    a1 = _read_csv(directory / "appendix_A1_benefit_parameters.csv")
    a2 = _read_csv(directory / "appendix_A2_system_parameters.csv")

    if [row["system"] for row in a1] != [row["system"] for row in a2]:
        raise ValueError("Appendix A1 and A2 list systems in different orders")

    column = lambda rows, key: np.array([float(row[key]) for row in rows], dtype=float)

    return Instance(
        names=tuple(row["system"] for row in a1),
        p0=column(a1, "P0"),
        delta_p=column(a1, "dP"),
        alpha=column(a1, "alpha"),
        e0=column(a1, "E0"),
        delta_e=column(a1, "dE"),
        beta=column(a1, "beta"),
        cost=column(a1, "cost"),
        technical=column(a2, "technical"),
        human=column(a2, "human"),
        reliability=column(a2, "reliability"),
        risk_initial=column(a2, "risk0"),
        risk_residual=column(a2, "risk_inf"),
        rho=column(a2, "rho"),
        effort=column(a2, "time"),
        criticality=column(a2, "criticality"),
        source="published",
    )


def generate_instance(seed: int = GENERATOR_SEED, n: int = 18) -> Instance:
    """Draw a fresh synthetic instance from the ranges quoted in Section 2.4.

    The generator is deterministic given ``seed``, but it does not reproduce the
    original draw order, so the returned values differ from Appendix A. Residual
    risk is clipped below the initial risk so that every system has a
    non-increasing risk trajectory.
    """
    rng = np.random.default_rng(seed)
    uniform = lambda key: rng.uniform(*PARAMETER_RANGES[key], size=n)

    risk_initial = uniform("risk_initial")
    risk_residual = np.minimum(uniform("risk_residual"), risk_initial)

    return Instance(
        names=tuple(f"S{i + 1:02d}" for i in range(n)),
        p0=uniform("p0"),
        delta_p=uniform("delta_p"),
        alpha=uniform("alpha"),
        e0=uniform("e0"),
        delta_e=uniform("delta_e"),
        beta=uniform("beta"),
        technical=uniform("technical"),
        human=uniform("human"),
        reliability=uniform("reliability"),
        criticality=uniform("criticality"),
        cost=rng.integers(COST_RANGE[0], COST_RANGE[1] + 1, size=n).astype(float),
        effort=rng.integers(EFFORT_RANGE[0], EFFORT_RANGE[1] + 1, size=n).astype(float),
        risk_initial=risk_initial,
        risk_residual=risk_residual,
        rho=uniform("rho"),
        source=f"generated(seed={seed})",
    )
