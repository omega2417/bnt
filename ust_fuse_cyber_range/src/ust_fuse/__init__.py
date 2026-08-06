"""
UST-Fuse Cyber Range Digital Twin
=================================

A budget, virtual-first digital twin of the *UST-Fuse* hybrid multi-sensor
UAV detection / tracking range, described in the scientific-technical proposal
"Створення бюджетного гібридного навчально-наукового полігону UST-Fuse".

The package emulates:

* a physical range (radar / EO-IR / RF-SDR / acoustic sensors) as a **digital twin**;
* time synchronisation, network transport and fault injection;
* two fusion pipelines — a naive *Reference* mode and the *Full UST-Fuse* mode;
* a multi-target Kalman tracker with GNN / JPDA-style association;
* a metrics engine (detection, tracking, calibration, paired statistics);
* a rich visualisation suite and field-trial style reports;
* full experiment provenance for reproducibility (Colab / Zenodo friendly).

The public API is intentionally small; see :func:`ust_fuse.run` and
:mod:`ust_fuse.experiment`.
"""
from __future__ import annotations

__version__ = "1.0.0"
__author__ = "UST-Fuse Cyber Range contributors"
__license__ = "MIT"

from .config import (
    RangeConfig,
    SensorConfig,
    ScenarioConfig,
    ExperimentConfig,
    default_range,
)
from .datatypes import Detection, GroundTruth, Track, ScanFrame
from .experiment import Experiment, ExperimentResult, run
from .scenarios import SCENARIO_LIBRARY, build_scenario, list_scenarios

__all__ = [
    "__version__",
    "RangeConfig",
    "SensorConfig",
    "ScenarioConfig",
    "ExperimentConfig",
    "default_range",
    "Detection",
    "GroundTruth",
    "Track",
    "ScanFrame",
    "Experiment",
    "ExperimentResult",
    "run",
    "SCENARIO_LIBRARY",
    "build_scenario",
    "list_scenarios",
]
