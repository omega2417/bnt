"""CRTM-OIS: staged method and system for the integral cyber resilience of a
critical infrastructure object, with an agent layer and neural components."""
from .levels import level, LEVEL_CODES, LEVEL_NAMES, BREAKPOINTS
from .model import Metric, BasicAction, Configuration, GOALS, GOAL_NAMES
from .scenarios import bnk_pay, e1_values, generate_state, five_states, STATES, REFERENCE_E1
from .system import assess, AssessmentError, Result, BUSES, BLOCKS, SOFTWARE_VERSION

__version__ = "1.0.0"
