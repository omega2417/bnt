"""High-level convenience API tying the whole platform together.

Intended for notebooks, examples and tests.  A single call builds the demo
site, radiomap and digital twin, samples an incident under a chosen scenario,
runs the full agent pipeline and returns the populated context (including the
SAR).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

import numpy as np

from .agents import default_orchestrator
from .agents.context import AgentContext
from .config import PlatformConfig
from .digital_twin.twin import DigitalTwin, Scenario
from .localization.grid import Grid
from .localization.radiomap import RadioMap
from .site import Site, demo_site


@dataclass
class Environment:
    cfg: PlatformConfig
    site: Site
    grid: Grid
    radiomap: RadioMap
    twin: DigitalTwin


def build_environment(
    cfg: Optional[PlatformConfig] = None,
    seed: int = 0,
    drift_bias_db: Optional[np.ndarray] = None,
) -> Environment:
    """Assemble the reproducible demo environment (site + radiomap + twin)."""
    cfg = cfg or PlatformConfig()
    site = demo_site()
    grid = Grid(cfg.grid)
    radiomap = RadioMap.build(site, grid, cfg.path_loss)
    twin = DigitalTwin(site, cfg.path_loss, seed=seed, drift_bias_db=drift_bias_db)
    return Environment(cfg=cfg, site=site, grid=grid, radiomap=radiomap,
                       twin=twin)


def run_incident(
    env: Environment,
    true_xy,
    incident_id: str = "INC-0001",
    scenario: Scenario = Scenario.CLEAN_LOS,
    seed: Optional[int] = 12345,
) -> AgentContext:
    """Sample one incident and run the full agent pipeline end-to-end.

    ``seed`` reseeds the twin so a given (true_xy, scenario, seed) always
    yields the same incident, independent of call order (reproducibility).
    """
    sample = env.twin.sample(
        np.asarray(true_xy, float), incident_id, scenario, seed=seed
    )
    ctx = AgentContext(
        cfg=env.cfg,
        site=env.site,
        grid=env.grid,
        radiomap=env.radiomap,
        twin=env.twin,
        sample=sample,
    )
    default_orchestrator().run(ctx)
    return ctx
