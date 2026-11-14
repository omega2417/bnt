"""SatQKD-Sentinel: simulation, telemetry analytics and geostationary-backbone toolkit
for satellite QKD networks with optical phased arrays."""
__version__ = "2.0.0"

from . import linkmodel, finitekey, opa, geo, network
from . import telemetry, features, models, evaluation
from .linkmodel import Link
