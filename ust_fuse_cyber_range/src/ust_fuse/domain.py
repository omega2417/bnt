"""Weather / domain modelling and domain randomisation (ЛР-6. Domain shift).

The proposal turns "один реальний політ" into "десятки варіантів" through
domain randomisation (section 9).  This module maps a human-readable weather
label to physical scaling factors, and provides a randomiser that perturbs a
scenario to create a family of related-but-different missions.
"""
from __future__ import annotations

import copy
from dataclasses import dataclass
from typing import Dict

import numpy as np

from .config import ScenarioConfig
from .rng import RNGHub


# weather -> (detection-prob scale, noise scale, clutter scale)
WEATHER_PROFILES: Dict[str, Dict[str, float]] = {
    "clear": dict(pd=1.00, noise=1.00, clutter=1.00),
    "haze": dict(pd=0.82, noise=1.35, clutter=1.20),
    "rain": dict(pd=0.65, noise=1.80, clutter=1.60),
    "night": dict(pd=0.72, noise=1.25, clutter=0.90),
    "wind": dict(pd=0.88, noise=1.50, clutter=1.10),
}


@dataclass
class DomainScales:
    pd_scale: float
    noise_scale: float
    clutter_scale: float

    def env_scale(self) -> float:
        """Combined multiplier applied to detection probability."""
        return self.pd_scale


def resolve_domain(scn: ScenarioConfig) -> DomainScales:
    prof = WEATHER_PROFILES.get(scn.weather, WEATHER_PROFILES["clear"])
    return DomainScales(
        pd_scale=prof["pd"] * scn.pd_scale,
        noise_scale=prof["noise"] * scn.noise_scale,
        clutter_scale=prof["clutter"] * scn.clutter_scale,
    )


def randomize_scenario(
    base: ScenarioConfig, rng_hub: RNGHub, index: int
) -> ScenarioConfig:
    """Produce a domain-randomised variant of ``base`` (replay family).

    Keeps the scientific structure (targets, trajectory kinds) but perturbs
    weather, clutter, noise and seed-relevant knobs.  Used by ЛР-6 and by the
    "one flight -> many variants" reuse metric (KPI section 13).
    """
    rng = rng_hub.spawn("domain_rand", index)
    scn = copy.deepcopy(base)
    scn.scenario_id = f"{base.scenario_id}__dr{index:02d}"
    scn.title = f"{base.title} (domain-rand #{index})"
    scn.weather = str(rng.choice(list(WEATHER_PROFILES)))
    scn.clutter_scale = float(np.clip(base.clutter_scale * rng.uniform(0.6, 1.8), 0.2, 3.0))
    scn.noise_scale = float(np.clip(base.noise_scale * rng.uniform(0.7, 1.6), 0.4, 2.5))
    scn.pd_scale = float(np.clip(base.pd_scale * rng.uniform(0.8, 1.15), 0.4, 1.2))
    scn.tags = list(set(base.tags + ["domain_rand"]))
    return scn
