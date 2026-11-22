"""Small helpers shared by analysis scripts."""
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from ebaw.model import scenario_params  # noqa: E402


def scenario_rate(key):
    """Relevant policy-change rate (per second) of a scenario."""
    return scenario_params(key)["pol_rate_rel_per_h"] / 3600.0
