"""bircpg -- Bio-Inspired Resource-Constrained Potential Games.

A reference implementation of the formal model, equilibrium analysis and
prospective evaluation protocol of

    "Bio-Inspired Resource-Constrained Potential Games for Adaptive
     Coordination in Autonomous Multi-Agent Systems"

Scope of claims, restated from the manuscript and enforced by this package:

* The Level I layer is **exact**.  Equations (1)-(6), (12)-(15) are computed in
  rational arithmetic and verified, not approximated.
* The Level II layer is a **synthetic harness with declared generative
  assumptions**.  Synthetic task success is not robot validation, and a
  modelled energy proxy is not a measured power saving.
* Level III (trained controllers, physical platforms, measured latency and
  energy) is **not implemented and not claimed**.  No experiment reported in
  the manuscript has been executed.
* Nothing here demonstrates energy savings, superior coordination, or robust
  real-world autonomy.  Those remain hypotheses.

Module map
----------
``game``          Section 4: actions, feasibility, payoffs, welfare, potential
``equilibria``    Section 5.1: Proposition 1, Corollary 1, enumeration, PoA
``estimation``    Section 5.2: Equation (7), Proposition 2, Equation (8)
``traces``        Section 5.3: Equation (9), Equation (10)
``logit``         Section 5.3: Equation (11), Proposition 3, Corollary 2
``protocol``      Section 5.4: Algorithm 1, the outer physical loop
``section6``      Section 6: the constructed two-agent example, exact
``level1``        Section 7.1: exact verification sweep
``environments``  Section 7.2: Level II synthetic generator
``baselines``     Section 7.3: the two proposed branches and B1-B5
``metrics``       Section 7.4-7.5: endpoints, paired bootstrap, Holm
``study``         Level II study driver and the preregistered design
``figures``       Figure 3, regenerated from the code
"""

from __future__ import annotations

__version__ = "1.0.0"

from .game import (
    Action,
    CONTROLLER_MODES,
    CostModel,
    OUTSIDE,
    ResourceCaps,
    ResourceVector,
    Task,
    TaskAllocationGame,
    harmonic,
    linear_congestion,
    zero_congestion,
)
from .equilibria import (
    improvement_path,
    potential_maximiser,
    price_of_anarchy,
    pure_nash_equilibria,
    verify_exact_potential,
    welfare_maximiser,
)
from .estimation import (
    BoundedNoiseEstimator,
    ExactEstimator,
    approximate_equilibrium_certificate,
    coverage_report,
    uncertainty_gated_sweep,
)
from .traces import TraceField, reference_distribution
from .logit import (
    detailed_balance_residual,
    logit_choice_probabilities,
    potential_loss_bound,
    stationary_distribution,
    transition_matrix,
)
from .protocol import run_epoch, run_trial
from .environments import EnvironmentConfig, make_environment

__all__ = [
    "__version__",
    "Action",
    "CONTROLLER_MODES",
    "CostModel",
    "OUTSIDE",
    "ResourceCaps",
    "ResourceVector",
    "Task",
    "TaskAllocationGame",
    "harmonic",
    "linear_congestion",
    "zero_congestion",
    "improvement_path",
    "potential_maximiser",
    "price_of_anarchy",
    "pure_nash_equilibria",
    "verify_exact_potential",
    "welfare_maximiser",
    "BoundedNoiseEstimator",
    "ExactEstimator",
    "approximate_equilibrium_certificate",
    "coverage_report",
    "uncertainty_gated_sweep",
    "TraceField",
    "reference_distribution",
    "detailed_balance_residual",
    "logit_choice_probabilities",
    "potential_loss_bound",
    "stationary_distribution",
    "transition_matrix",
    "run_epoch",
    "run_trial",
    "EnvironmentConfig",
    "make_environment",
]
