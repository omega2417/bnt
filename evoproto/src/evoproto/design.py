"""Parametric EOAT bracket and its analytic evaluator (Section 6).

The bracket is idealised as a cantilever of length ``L`` under a tip load
``P = m_p a`` (Table 6).  The section is a rectangular shell of outer width
``b``, height ``h`` and wall thickness ``t``, filled with a cellular core of
relative density ``rho``.  Design vector ``d = (b, h, t, rho)``.

Implemented equations:

* Eq. (15)  second moments of area of shell and core;
* Eq. (16)  section flexural rigidity with the Gibson-Ashby open-cell scaling
  ``E* = C1 E_s rho^2`` (``C1 ~ 1``);
* Eq. (17)  tip deflection, outer-fibre bending stress and the elastic
  local-buckling stress of the compression flange;
* Eq. (18)  mass and the cost proxy;
* Eq. (19)  the constraint-margin vector ``g >= 0``.

The analytic model is a surrogate: it ignores shear deformation, stress
concentration at the flange, anisotropy of the LPBF material and the
discreteness of a real lattice.  Its role is to make the protocol executable
end to end; the FE stage of Section 4.6 replaces it before any physical build.
Every result therefore carries the tag MODELED.

The material and specification values are the illustrative assumptions A1-A7 of
Table 6 and are marked NEEDS_INPUT where the paper requires the industrial
partner's certified data.
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from typing import Any, Dict, List, Mapping, Optional, Sequence, Tuple

import numpy as np

from .data import Provenance, ProvenanceTag

__all__ = [
    "Material",
    "ALSI10MG",
    "BracketSpec",
    "EOAT_BRACKET",
    "DESIGN_VARIABLES",
    "design_bounds",
    "evaluate",
    "evaluate_population",
    "objective_names",
    "constraint_names",
    "feasible_fraction_uniform",
    "uniform_prior",
    "analog_prior",
    "template_ratio_prior",
    "template_projection",
    "PRIORS",
]

#: Names of the four design variables of Table 6.
DESIGN_VARIABLES: Tuple[str, str, str, str] = ("b", "h", "t", "rho")

#: Wall thickness as a fraction of the section width in the arm-A template
#: family, and the lowest core relative density a catalogue-style transfer
#: considers (a solid or coarsely filled core).  These bound the human stand-in
#: of Section 7.2; they are not a model of how engineers actually work.
WALL_FRACTION: Tuple[float, float] = (0.02, 0.08)
CORE_DENSITY_LO: float = 0.25

#: Marker for a value that the protocol requires from the industrial partner.
NEEDS_INPUT = "NEEDS INPUT: certified datasheet value required before the physical build"


@dataclass(frozen=True)
class Material:
    """Bulk material properties (assumption A7 of Table 6).

    The AlSi10Mg values are order-of-magnitude figures taken from the paper and
    must be replaced by certified data before any build.
    """

    name: str
    E_s: float          # Young's modulus of the solid [Pa]
    sigma_y: float      # yield strength [Pa]
    rho_s: float        # density of the solid [kg m^-3]
    nu: float = 0.33    # Poisson's ratio
    cost_per_kg: float = 1.0  # cost proxy c_kg [currency kg^-1]
    note: str = NEEDS_INPUT

    def as_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name, "E_s": self.E_s, "sigma_y": self.sigma_y,
            "rho_s": self.rho_s, "nu": self.nu, "cost_per_kg": self.cost_per_kg,
            "note": self.note,
        }


#: AlSi10Mg as printed by laser powder-bed fusion (Table 6, A7).
ALSI10MG = Material(
    name="AlSi10Mg (LPBF)",
    E_s=70e9,
    sigma_y=230e6,
    rho_s=2670.0,
    nu=0.33,
    cost_per_kg=1.0,
)


@dataclass(frozen=True)
class BracketSpec:
    """Illustrative specification of the EOAT bracket task (Table 6).

    All values are design assumptions A1-A7 of the proposed experiment, to be
    replaced by the industrial partner's certified data before the experiment
    is run; they are not measurements.
    """

    L: float = 0.180             # A1 cantilever length [m]
    payload: float = 2.0         # A2 moving payload [kg]
    acceleration: float = 5 * 9.81   # A3 peak acceleration [m s^-2]
    delta_max: float = 0.15e-3   # A4 allowable tip deflection [m]
    safety_factor: float = 2.0   # A5 safety factor on yield
    mass_max: float = 0.120      # A6 mass cap [kg]
    t_min: float = 0.4e-3        # minimum printable wall [m]
    material: Material = ALSI10MG
    C1_gibson_ashby: float = 1.0  # open-cell scaling constant of Eq. (16)
    bounds_lo: Tuple[float, float, float, float] = (0.010, 0.010, 0.0004, 0.05)
    bounds_hi: Tuple[float, float, float, float] = (0.060, 0.080, 0.0040, 1.00)

    @property
    def tip_load(self) -> float:
        """``P = m_p a`` [N] (Table 6, A2 and A3)."""
        return float(self.payload * self.acceleration)

    @property
    def sigma_allow(self) -> float:
        """``sigma_y / SF`` [Pa]."""
        return float(self.material.sigma_y / self.safety_factor)

    @property
    def reference_point(self) -> Tuple[float, float]:
        """``r = (m_max, delta_max)`` — the hypervolume reference of Eq. (21)."""
        return (self.mass_max, self.delta_max)

    def as_dict(self) -> Dict[str, Any]:
        return {
            "L": self.L, "payload": self.payload, "acceleration": self.acceleration,
            "tip_load": self.tip_load, "delta_max": self.delta_max,
            "safety_factor": self.safety_factor, "mass_max": self.mass_max,
            "t_min": self.t_min, "C1_gibson_ashby": self.C1_gibson_ashby,
            "bounds_lo": list(self.bounds_lo), "bounds_hi": list(self.bounds_hi),
            "material": self.material.as_dict(),
            "assumptions": "A1-A7 of Table 6; illustrative, not measured",
        }


#: The task T1 specification used by the protocol.
EOAT_BRACKET = BracketSpec()


def design_bounds(spec: BracketSpec = EOAT_BRACKET) -> Tuple[np.ndarray, np.ndarray]:
    """Lower and upper bounds of the design space ``D`` (Table 6)."""
    return np.asarray(spec.bounds_lo, dtype=float), np.asarray(spec.bounds_hi, dtype=float)


def objective_names() -> Tuple[str, str]:
    """The two minimised objectives of the protocol: mass and tip deflection."""
    return ("mass", "deflection")


def constraint_names() -> Tuple[str, str, str, str, str]:
    """The five constraint margins of Eq. (19), in order."""
    return ("strength", "deflection", "buckling", "wall_thickness", "mass_cap")


def _as_population(d: np.ndarray) -> Tuple[np.ndarray, bool]:
    arr = np.asarray(d, dtype=float)
    single = arr.ndim == 1
    if single:
        arr = arr.reshape(1, -1)
    if arr.shape[1] != 4:
        raise ValueError("a design vector is (b, h, t, rho)")
    return arr, single


def evaluate_population(X: np.ndarray, spec: BracketSpec = EOAT_BRACKET) -> Dict[str, np.ndarray]:
    """Vectorised analytic evaluator (Eqs. 15-19).

    Returns arrays for every quantity of Section 6.4, plus the objective matrix
    ``F`` (minimised) and the constraint-margin matrix ``G`` (``>= 0`` feasible).
    Geometrically impossible designs (a wall thicker than half the section) are
    reported as infeasible through the ``wall_thickness`` margin rather than
    raising, so that a search can sample the whole box.
    """
    X, _ = _as_population(X)
    b, h, t, rho = X[:, 0], X[:, 1], X[:, 2], X[:, 3]
    mat = spec.material
    C1 = spec.C1_gibson_ashby
    P, L = spec.tip_load, spec.L

    b_i = np.clip(b - 2.0 * t, 0.0, None)
    h_i = np.clip(h - 2.0 * t, 0.0, None)

    # Eq. (15)
    I_shell = (b * h ** 3 - b_i * h_i ** 3) / 12.0
    I_core = (b_i * h_i ** 3) / 12.0
    # Eq. (16): E* = C1 E_s rho^2 for the open-cell core
    I_eff = I_shell + C1 * rho ** 2 * I_core
    EI = mat.E_s * I_eff

    # Eq. (17)
    with np.errstate(divide="ignore", invalid="ignore"):
        delta = P * L ** 3 / (3.0 * EI)
        sigma = P * L * (h / 2.0) / I_eff
        sigma_cr = (4.0 * np.pi ** 2 * mat.E_s / (12.0 * (1.0 - mat.nu ** 2))) * (t / b) ** 2
    delta = np.where(np.isfinite(delta), delta, np.inf)
    sigma = np.where(np.isfinite(sigma), sigma, np.inf)

    # Eq. (18)
    solid_volume = L * ((b * h - b_i * h_i) + rho * b_i * h_i)
    mass = mat.rho_s * solid_volume
    cost = mat.cost_per_kg * mass + 0.5 * mat.cost_per_kg * mat.rho_s * solid_volume

    # Eq. (19): g = (sigma_y/SF - sigma, delta_max - delta, sigma_cr - sigma,
    #               t - t_min, m_max - m) >= 0
    G = np.column_stack(
        [
            spec.sigma_allow - sigma,
            spec.delta_max - delta,
            sigma_cr - sigma,
            t - spec.t_min,
            spec.mass_max - mass,
        ]
    )
    # A section whose walls meet or overlap is not a shell at all.
    degenerate = (b_i <= 0) | (h_i <= 0)
    if np.any(degenerate):
        G[degenerate, 3] = -np.abs(t[degenerate])

    F = np.column_stack([mass, delta])
    return {
        "I_shell": I_shell,
        "I_core": I_core,
        "I_effective": I_eff,
        "EI": EI,
        "deflection": delta,
        "stress": sigma,
        "stress_buckling": sigma_cr,
        "mass": mass,
        "cost": cost,
        "F": F,
        "G": G,
        "feasible": np.all(G >= 0.0, axis=1),
        "violation": np.sum(np.clip(-G, 0.0, None), axis=1),
    }


def evaluate(d: Sequence[float], spec: BracketSpec = EOAT_BRACKET) -> Dict[str, Any]:
    """Evaluate a single design vector ``d = (b, h, t, rho)``.

    The returned dictionary carries the provenance tag of its evaluator, so a
    MODELED analytic result cannot be confused with a MEASURED one when tables
    are assembled (Section 5).
    """
    out = evaluate_population(np.asarray(d, dtype=float).reshape(1, -1), spec)
    result: Dict[str, Any] = {k: (v[0] if isinstance(v, np.ndarray) else v) for k, v in out.items()}
    result["design"] = dict(zip(DESIGN_VARIABLES, [float(x) for x in d]))
    result["objectives"] = dict(zip(objective_names(), [float(x) for x in result["F"]]))
    result["constraints"] = dict(zip(constraint_names(), [float(x) for x in result["G"]]))
    result["feasible"] = bool(result["feasible"])
    result["tag"] = ProvenanceTag.MODELED.value
    result["provenance"] = Provenance.modeled(
        source="evoproto.design.evaluate (analytic cantilever surrogate, Eqs. 15-19)",
        u=0.2,
    )
    return result


def feasible_fraction_uniform(
    spec: BracketSpec = EOAT_BRACKET,
    n_samples: int = 20000,
    seed: int = 0,
) -> float:
    """Fraction of uniformly sampled designs that satisfy every constraint.

    Section 6.2 reports about 1 % under the assumptions of Table 6 (MODELED,
    20 000 samples), which is why the constraints bind and the task
    discriminates between search strategies.
    """
    lo, hi = design_bounds(spec)
    rng = np.random.default_rng(seed)
    X = lo + rng.random((int(n_samples), 4)) * (hi - lo)
    return float(np.mean(evaluate_population(X, spec)["feasible"]))


# ---------------------------------------------------------------- priors p_c
def uniform_prior(n: int, spec: BracketSpec, rng: np.random.Generator) -> np.ndarray:
    """Arm B: uniform sampling prior on ``D``, no knowledge-graph access."""
    lo, hi = design_bounds(spec)
    return lo + rng.random((int(n), 4)) * (hi - lo)


def analog_prior(
    n: int,
    spec: BracketSpec,
    rng: np.random.Generator,
    centre: Sequence[float] = (0.45, 0.80, 0.25, 0.20),
    spread: Sequence[float] = (0.20, 0.15, 0.15, 0.12),
) -> np.ndarray:
    """Arm C: analog-shaped prior ``p_c`` concentrated where the mechanism predicts.

    The mechanism retrieved for "high bending stiffness per unit mass in a
    slender, intermittently loaded member" is sandwich / cellular stiffening:
    a thin shell placed far from the neutral axis with a low-density core.  The
    prior is therefore a truncated Gaussian in the normalised design box,
    centred on a tall section with thin walls and a light core.

    ``centre`` and ``spread`` are expressed in normalised coordinates and are
    free parameters of the arm-C prior; they are fixed before the experiment
    and reported (Section 8.3 records that pre-registration prevents post hoc
    tuning but does not guarantee the pre-registered values are sensible).
    """
    lo, hi = design_bounds(spec)
    centre = np.asarray(centre, dtype=float)
    spread = np.asarray(spread, dtype=float)
    Z = np.clip(rng.normal(centre, spread, size=(int(n), 4)), 0.0, 1.0)
    return lo + Z * (hi - lo)


def template_ratio_prior(
    n: int,
    spec: BracketSpec,
    rng: np.random.Generator,
    ratios: Sequence[float] = (1.0, 1.5, 2.0),
) -> np.ndarray:
    """Arm A: a template-ratio sampler standing in for the human designers.

    Catalogue-style biomimetic practice transfers a remembered proportion: a
    section height fixed as a multiple of the width, a wall thickness taken
    from a handbook fraction of the width, and a solid or nearly solid core.
    This is a stand-in, not a model of human designers, and the dry run of
    Section 7.7 reports its numbers as SYNTHETIC for that reason.
    """
    lo, hi = design_bounds(spec)
    b = rng.uniform(lo[0], hi[0], size=int(n))
    ratio = np.asarray(ratios, dtype=float)[rng.integers(0, len(ratios), size=int(n))]
    h = np.clip(b * ratio, lo[1], hi[1])
    t = np.clip(b * rng.uniform(*WALL_FRACTION, size=int(n)), lo[2], hi[2])
    rho = np.clip(rng.uniform(CORE_DENSITY_LO, 1.0, size=int(n)), lo[3], hi[3])
    return np.column_stack([b, h, t, rho])


def template_projection(X: np.ndarray, spec: BracketSpec = EOAT_BRACKET,
                        ratios: Sequence[float] = (1.0, 1.5, 2.0)) -> np.ndarray:
    """Snap designs back onto the arm-A template family.

    The human stand-in of arm A works with remembered proportions rather than
    with the full four-dimensional box: the section height is a catalogue
    multiple of the width, the wall a handbook fraction of it, and the core is
    solid or nearly so.  Projecting every offspring back onto that family is
    what makes arm A a *template* baseline: it is matched in wall-clock time,
    not in the volume of design space it can reach (Section 7.2).
    """
    lo, hi = design_bounds(spec)
    X = np.atleast_2d(np.asarray(X, dtype=float)).copy()
    ratio_grid = np.sort(np.asarray(ratios, dtype=float))
    b = np.clip(X[:, 0], lo[0], hi[0])
    # A section taller than the box allows would be clipped, which would take the
    # design off the template family; shrink the width instead so that the
    # smallest catalogue ratio still fits.  The projection is then idempotent.
    b = np.minimum(b, hi[1] / ratio_grid[0])
    current = X[:, 1] / b
    feasible_ratio = np.where(
        b[:, None] * ratio_grid[None, :] <= hi[1] + 1e-12, ratio_grid[None, :], np.nan
    )
    distance = np.abs(current[:, None] - feasible_ratio)
    distance = np.where(np.isnan(distance), np.inf, distance)
    nearest = ratio_grid[np.argmin(distance, axis=1)]
    X[:, 0] = b
    X[:, 1] = np.clip(b * nearest, lo[1], hi[1])
    X[:, 2] = np.clip(np.clip(X[:, 2] / b, *WALL_FRACTION) * b, lo[2], hi[2])
    X[:, 3] = np.clip(X[:, 3], CORE_DENSITY_LO, 1.0)
    return X


#: The three samplers used by the three arms of Section 7.2.
PRIORS = {
    "A": template_ratio_prior,
    "B": uniform_prior,
    "C": analog_prior,
}
