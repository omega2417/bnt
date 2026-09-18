"""Parametric EOAT bracket and its analytic evaluator (Section 6).

The case study is an end-of-arm-tool bracket connecting a vacuum gripper to the
flange of a four-axis pick-and-place robot, produced by laser powder-bed fusion
of AlSi10Mg.  The bracket is idealized as a cantilever of length ``L`` under a
tip load ``P = m_p a``; its section is a rectangular shell of outer width ``b``,
height ``h`` and wall thickness ``t``, filled with a cellular core of relative
density ``rho`` (Fig. 5).

Every number this module returns is MODELED: the analytic evaluator ignores
shear deformation, the stress concentration at the flange, the anisotropy of
LPBF material and the discreteness of a real lattice.  Its role is to make the
protocol executable end to end; the FE stage of Section 4.6 replaces it before
any physical build.  The specification values of Table 6 are design assumptions
A1-A7, to be replaced by the industrial partner's certified data.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import asdict, dataclass, field
from typing import Any

import numpy as np

from evoproto.data import Tag

__all__ = [
    "BracketSpec",
    "DESIGN_VARIABLES",
    "analog_prior_sampler",
    "bounds_array",
    "constraint_names",
    "evaluate",
    "evaluate_population",
    "feasible_fraction_uniform",
    "objective_names",
    "template_ratio_sampler",
    "uniform_sampler",
]

#: Design variables of the parametric family, in evaluation order (Table 6).
DESIGN_VARIABLES: tuple[str, ...] = ("b", "h", "t", "rho")

GIBSON_ASHBY_EXPONENT = 2.0
"""Exponent ``n`` of the Gibson-Ashby open-cell modulus scaling [43]."""

PLATE_BUCKLING_COEFFICIENT = 4.0
"""Buckling coefficient ``k`` of a simply supported compression flange."""

POISSON_RATIO = 0.33
"""Poisson's ratio of AlSi10Mg used in the plate-buckling expression."""


@dataclass(frozen=True)
class BracketSpec:
    """Illustrative specification of the EOAT bracket task (Table 6).

    All values are **assumptions** of the proposed experiment (A1-A7), not
    measurements.  ``NEEDS INPUT``: replace ``E``, ``sigma_y`` and ``rho_solid``
    with the certified LPBF AlSi10Mg datasheet of the industrial partner, and
    ``payload``, ``acceleration``, ``delta_max`` and ``mass_max`` with the line's
    own motion profile and accuracy budget, before running the protocol.
    """

    length: float = 0.180                 # A1, m (flange-to-gripper axis)
    payload: float = 2.0                  # A2, kg (gripper + product)
    acceleration: float = 5 * 9.81        # A3, m/s^2 (5 g from the motion profile)
    delta_max: float = 0.15e-3            # A4, m (placement accuracy budget)
    safety_factor: float = 2.0            # A5, - (on yield)
    mass_max: float = 0.120               # A6, kg (feasibility gate)
    modulus: float = 70e9                 # A7, Pa
    yield_strength: float = 230e6         # A7, Pa
    rho_solid: float = 2670.0             # A7, kg/m^3
    t_min: float = 0.4e-3                 # process constraint, m
    bounds: dict[str, tuple[float, float]] = field(
        default_factory=lambda: {
            "b": (10e-3, 60e-3),
            "h": (10e-3, 80e-3),
            "t": (0.4e-3, 4.0e-3),
            "rho": (0.05, 1.0),
        }
    )
    assumptions: tuple[str, ...] = (
        "A1 cantilever length 180 mm",
        "A2 moving payload 2.0 kg",
        "A3 peak acceleration 5 g",
        "A4 allowable tip deflection 0.15 mm",
        "A5 safety factor on yield 2.0",
        "A6 mass cap 120 g",
        "A7 AlSi10Mg order-of-magnitude properties [NEEDS INPUT: certified datasheet]",
    )

    @property
    def tip_load(self) -> float:
        """Tip load ``P = m_p a`` in newtons (98.2 N under Table 6)."""
        return self.payload * self.acceleration

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["tip_load_N"] = self.tip_load
        d["provenance_tag"] = Tag.MODELED.value
        return d


def objective_names() -> tuple[str, ...]:
    """Objectives of the two-objective protocol: mass and tip deflection."""
    return ("mass_kg", "deflection_m")


def constraint_names() -> tuple[str, ...]:
    """Constraint margins ``g >= 0`` of Eq. (19)."""
    return ("deflection", "yield", "buckling", "mass", "wall_fit")


def bounds_array(spec: BracketSpec | None = None) -> tuple[np.ndarray, np.ndarray]:
    """Lower and upper bounds of the design space ``D`` as arrays."""
    spec = spec or BracketSpec()
    lo = np.array([spec.bounds[v][0] for v in DESIGN_VARIABLES], dtype=float)
    hi = np.array([spec.bounds[v][1] for v in DESIGN_VARIABLES], dtype=float)
    return lo, hi


def _section_properties(
    b: np.ndarray, h: np.ndarray, t: np.ndarray, rho: np.ndarray, spec: BracketSpec
) -> dict[str, np.ndarray]:
    """Second moments, flexural rigidity and mass of the section (Eqs. 15-16, 18)."""
    b_i = np.maximum(b - 2.0 * t, 0.0)
    h_i = np.maximum(h - 2.0 * t, 0.0)
    i_shell = (b * h**3 - b_i * h_i**3) / 12.0
    i_core = (b_i * h_i**3) / 12.0
    e_core = spec.modulus * rho**GIBSON_ASHBY_EXPONENT   # Gibson-Ashby, n = 2 [43]
    ei = spec.modulus * i_shell + e_core * i_core        # Eq. (16)
    i_equiv = i_shell + (e_core / spec.modulus) * i_core
    area_shell = b * h - b_i * h_i
    area_core = b_i * h_i
    mass = spec.rho_solid * (area_shell + rho * area_core) * spec.length   # Eq. (18)
    cost_proxy = spec.rho_solid * (area_shell + rho * area_core) * spec.length
    return {
        "b_i": b_i,
        "h_i": h_i,
        "I_shell": i_shell,
        "I_core": i_core,
        "I_equiv": i_equiv,
        "E_core": e_core,
        "EI": ei,
        "mass": mass,
        "cost_proxy": cost_proxy,
    }


def evaluate_population(
    x: np.ndarray, spec: BracketSpec | None = None
) -> tuple[np.ndarray, np.ndarray, dict[str, np.ndarray]]:
    """Vectorized analytic evaluator (Eqs. 15-19).

    Parameters
    ----------
    x:
        ``(n, 4)`` array of design vectors ``(b, h, t, rho)`` in SI units.
    spec:
        Task specification; :class:`BracketSpec` by default.

    Returns
    -------
    (F, G, extras)
        ``F`` is the ``(n, 2)`` objective matrix ``(mass, deflection)``, both
        minimized.  ``G`` is the ``(n, 5)`` matrix of constraint margins, each
        non-negative when satisfied and normalized by its limit so that the
        total violation of Algorithm 1 sums comparable quantities.  ``extras``
        carries stress, buckling stress, rigidity and the cost proxy.

    Notes
    -----
    All outputs are tagged MODELED; ``extras["provenance_tag"]`` records it, so
    an analytic result cannot be mistaken for a MEASURED one when tables are
    assembled (Section 5).
    """
    spec = spec or BracketSpec()
    x = np.atleast_2d(np.asarray(x, dtype=float))
    if x.shape[1] != len(DESIGN_VARIABLES):
        raise ValueError(f"design vectors must have {len(DESIGN_VARIABLES)} components")
    b, h, t, rho = x[:, 0], x[:, 1], x[:, 2], x[:, 3]
    props = _section_properties(b, h, t, rho, spec)
    p, length = spec.tip_load, spec.length

    with np.errstate(divide="ignore", invalid="ignore"):
        deflection = p * length**3 / (3.0 * props["EI"])                     # Eq. (17)
        stress = p * length * (h / 2.0) / props["I_equiv"]                   # Eq. (17)
    sigma_cr = (
        PLATE_BUCKLING_COEFFICIENT
        * np.pi**2
        * spec.modulus
        / (12.0 * (1.0 - POISSON_RATIO**2))
        * (t / np.maximum(b, 1e-12)) ** 2
    )                                                                        # Eq. (17)
    deflection = np.where(np.isfinite(deflection), deflection, np.inf)
    stress = np.where(np.isfinite(stress), stress, np.inf)
    allowable = spec.yield_strength / spec.safety_factor

    g = np.column_stack(
        [
            1.0 - deflection / spec.delta_max,          # tip deflection
            1.0 - stress / allowable,                   # yield with safety factor
            1.0 - stress / np.maximum(sigma_cr, 1e-12), # local buckling of the flange
            1.0 - props["mass"] / spec.mass_max,        # mass cap
            np.minimum(                                 # printable wall fits the section
                (t - spec.t_min) / spec.t_min,
                np.minimum(props["b_i"], props["h_i"]) / np.maximum(t, 1e-12) - 1.0,
            ),
        ]
    )                                                                        # Eq. (19)
    g = np.where(np.isfinite(g), g, -1e6)
    f = np.column_stack([props["mass"], deflection])
    extras = {
        "stress_Pa": stress,
        "sigma_cr_Pa": sigma_cr,
        "EI_Nm2": props["EI"],
        "cost_proxy_kg": props["cost_proxy"],
        "provenance_tag": Tag.MODELED.value,
    }
    return f, g, extras


def evaluate(d: Sequence[float], spec: BracketSpec | None = None) -> dict[str, Any]:
    """Evaluate a single design vector and return a labeled, tagged record."""
    f, g, extras = evaluate_population(np.asarray(d, dtype=float)[None, :], spec)
    record = {
        "design": dict(zip(DESIGN_VARIABLES, [float(v) for v in d])),
        "objectives": dict(zip(objective_names(), [float(v) for v in f[0]])),
        "constraints": dict(zip(constraint_names(), [float(v) for v in g[0]])),
        "feasible": bool(np.all(g[0] >= 0.0)),
        "violation": float(np.sum(np.maximum(0.0, -g[0]))),
        "provenance_tag": Tag.MODELED.value,
    }
    record.update(
        {
            "stress_Pa": float(extras["stress_Pa"][0]),
            "sigma_cr_Pa": float(extras["sigma_cr_Pa"][0]),
            "EI_Nm2": float(extras["EI_Nm2"][0]),
            "cost_proxy_kg": float(extras["cost_proxy_kg"][0]),
        }
    )
    return record


def feasible_fraction_uniform(
    spec: BracketSpec | None = None, n_samples: int = 20_000, seed: int = 0
) -> float:
    """Fraction of uniformly sampled designs that satisfy every constraint.

    Section 6.2 reports about 1 % under the assumptions of Table 6 (MODELED,
    20 000 samples): the constraints bind, so the task discriminates between
    search strategies rather than rewarding any sampler that stays in bounds.
    """
    spec = spec or BracketSpec()
    lo, hi = bounds_array(spec)
    rng = np.random.default_rng(seed)
    x = lo + rng.random((int(n_samples), len(DESIGN_VARIABLES))) * (hi - lo)
    _, g, _ = evaluate_population(x, spec)
    return float(np.mean(np.all(g >= 0.0, axis=1)))


def analog_prior_sampler(spec: BracketSpec | None = None):
    """Sampling prior ``p_c`` shaped by the sandwich-stiffening analog (Section 4.5).

    The mechanism "thin shell with a low-density cellular core" predicts a
    sub-region of the design space: walls near the process minimum, sections
    deep rather than wide, core relative density low.  The prior concentrates
    there; it does not constrain the objectives, which remain purely
    engineering quantities.  This is the *only* channel through which
    evolutionary data enter arm C's search, together with trade-off constraints.
    """
    spec = spec or BracketSpec()
    lo, hi = bounds_array(spec)

    def sample(n: int, rng: np.random.Generator) -> np.ndarray:
        b = rng.uniform(0.25, 0.75, n)
        h = rng.uniform(0.45, 1.00, n)
        t = rng.beta(1.6, 4.0, n)
        rho = rng.beta(1.3, 5.0, n)
        unit = np.column_stack([b, h, t, rho])
        return lo + np.clip(unit, 0.0, 1.0) * (hi - lo)

    return sample


def uniform_sampler(spec: BracketSpec | None = None):
    """Uniform prior on ``D`` - the sampler of arm B (Section 7.2)."""
    spec = spec or BracketSpec()
    lo, hi = bounds_array(spec)

    def sample(n: int, rng: np.random.Generator) -> np.ndarray:
        return lo + rng.random((n, len(DESIGN_VARIABLES))) * (hi - lo)

    return sample


def template_ratio_sampler(spec: BracketSpec | None = None):
    """Template-ratio sampler standing in for human designers (arm A, dry run).

    A SYNTHETIC stand-in only: it draws sections around a handful of
    textbook aspect ratios with plate-like wall thicknesses, which is how a
    catalog-driven designer would start.  It is *not* a model of human
    designers, and the dry run's arm A results say nothing about them.
    """
    spec = spec or BracketSpec()
    lo, hi = bounds_array(spec)
    templates = np.array([[0.35, 0.60], [0.50, 0.80], [0.20, 0.45], [0.60, 0.95]])

    def sample(n: int, rng: np.random.Generator) -> np.ndarray:
        pick = templates[rng.integers(0, len(templates), n)]
        jitter = rng.normal(0.0, 0.05, pick.shape)
        bh = np.clip(pick + jitter, 0.0, 1.0)
        t = np.clip(rng.normal(0.35, 0.15, n), 0.0, 1.0)
        rho = np.clip(rng.normal(0.55, 0.25, n), 0.0, 1.0)
        unit = np.column_stack([bh[:, 0], bh[:, 1], t, rho])
        return lo + unit * (hi - lo)

    return sample
