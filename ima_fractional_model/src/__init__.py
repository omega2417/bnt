"""Delayed Fractional-Order Graph Dynamics for Integrated Modular Avionics.

Synthetic reproducibility model accompanying the manuscript
"Delayed Fractional-Order Graph Dynamics for Cascade Escalation and
Reconfiguration Failure in Integrated Modular Avionics".

This is a SYNTHETIC, mechanism-oriented research model. Parameters are NOT
derived from any real Airbus/Boeing or certified IMA platform and the model is
not certification software.
"""
from .graph_model import IMAGraph, load_graph
from .ima_dynamics import IMADynamics, ScenarioParams, compute_nominal_backlog
from .fractional_solver import solve_gl, solve_abm, gl_weights, SolverResult
from .cascade_threshold import cascade_threshold, ThresholdResult, critical_delay_scalar
from .scenarios import (run_scenario, ScenarioResult, mean_field_trajectory,
                        mean_field_fixed_points, tipping_sweep, priority_sweep,
                        delay_memory_grid)

__version__ = "1.0.0"

__all__ = [
    "IMAGraph", "load_graph", "IMADynamics", "ScenarioParams",
    "compute_nominal_backlog", "solve_gl", "solve_abm", "gl_weights",
    "SolverResult", "cascade_threshold", "ThresholdResult",
    "critical_delay_scalar", "run_scenario", "ScenarioResult",
    "mean_field_trajectory", "mean_field_fixed_points", "tipping_sweep",
    "priority_sweep", "delay_memory_grid", "__version__",
]
