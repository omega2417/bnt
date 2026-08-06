"""UAV trajectory generation for the digital twin.

Trajectories are analytic so that a single reference mission can be turned into
"десятки варіантів" via domain randomisation and replay (proposal section 2,
"Один фізичний еталон — багато цифрових копій").
"""
from __future__ import annotations

from typing import List

import numpy as np

from .config import ScenarioConfig
from .datatypes import GroundTruth
from .rng import RNGHub

# Nominal kinematic envelope per training UAV class.
UAV_CLASSES = {
    "multirotor": dict(speed=(4, 12), alt=(40, 150), agility=1.0, rf=True),
    "fpv": dict(speed=(15, 32), alt=(20, 120), agility=2.2, rf=True),
    "fixedwing": dict(speed=(18, 30), alt=(80, 350), agility=0.5, rf=True),
    "silent_glider": dict(speed=(10, 20), alt=(60, 200), agility=0.7, rf=False),
}


def _smooth_orbit(t, cx, cy, alt, radius, omega, phase, climb):
    x = cx + radius * np.cos(omega * t + phase)
    y = cy + radius * np.sin(omega * t + phase)
    z = alt + climb * np.sin(0.25 * omega * t)
    return np.stack([x, y, z], axis=1)


def _lemniscate(t, cx, cy, alt, scale, omega, phase, climb):
    # figure-eight, useful to force crossings (ЛР-4)
    s = np.sin(omega * t + phase)
    c = np.cos(omega * t + phase)
    denom = 1 + s * s
    x = cx + scale * c / denom
    y = cy + scale * s * c / denom
    z = alt + climb * np.sin(0.3 * omega * t)
    return np.stack([x, y, z], axis=1)


def _ingress(t, x0, y0, alt, heading, speed, weave, omega):
    # straight ingress with lateral weave
    x = x0 + speed * t * np.sin(heading) + weave * np.sin(omega * t)
    y = y0 + speed * t * np.cos(heading) + weave * np.cos(omega * t)
    z = alt + 0.0 * t
    return np.stack([x, y, z], axis=1)


def _hover_dash(t, cx, cy, alt, dash_speed, period):
    # hovers, then dashes — stresses the constant-velocity tracker
    phase = (t % period) / period
    move = np.clip((phase - 0.5) * 2, 0, 1)
    x = cx + dash_speed * move * t * 0.05
    y = cy + dash_speed * (1 - move) * 3.0 * np.sin(0.1 * t)
    z = alt + 10 * np.sin(0.2 * t)
    return np.stack([x, y, z], axis=1)


def _velocity(t, pos):
    v = np.gradient(pos, t, axis=0)
    return v


def generate_ground_truth(scn: ScenarioConfig, rng_hub: RNGHub) -> List[GroundTruth]:
    """Create the list of :class:`GroundTruth` targets for a scenario."""
    rng = rng_hub.stream("truth")
    t = np.arange(0.0, scn.duration_s + 1e-9, 1.0 / scn.truth_rate_hz)
    targets: List[GroundTruth] = []

    kinds = scn.trajectory_kinds or ["orbit"]
    classes = scn.uav_classes or ["multirotor"]

    for i in range(scn.n_targets):
        kind = kinds[i % len(kinds)]
        uav_class = classes[i % len(classes)]
        spec = UAV_CLASSES.get(uav_class, UAV_CLASSES["multirotor"])
        speed = rng.uniform(*spec["speed"])
        alt = rng.uniform(*spec["alt"])

        if scn.crossing:
            # Place orbits/lemniscates so paths intersect near the origin.
            cx = rng.uniform(-120, 120)
            cy = rng.uniform(-120, 120)
        else:
            cx = rng.uniform(-600, 600)
            cy = rng.uniform(-600, 600)

        phase = rng.uniform(0, 2 * np.pi)
        climb = rng.uniform(5, 30)

        if kind == "orbit":
            radius = rng.uniform(150, 500)
            omega = speed / max(radius, 1.0)
            pos = _smooth_orbit(t, cx, cy, alt, radius, omega, phase, climb)
        elif kind == "lemniscate":
            scale = rng.uniform(250, 600)
            omega = speed / max(scale * 0.5, 1.0)
            pos = _lemniscate(t, cx, cy, alt, scale, omega, phase, climb)
        elif kind == "ingress":
            heading = rng.uniform(0, 2 * np.pi)
            x0 = cx + 700 * np.sin(heading + np.pi)
            y0 = cy + 700 * np.cos(heading + np.pi)
            weave = rng.uniform(10, 60) * spec["agility"]
            omega = rng.uniform(0.2, 0.8)
            pos = _ingress(t, x0, y0, alt, heading, speed, weave, omega)
        elif kind == "hover_dash":
            pos = _hover_dash(t, cx, cy, alt, speed, rng.uniform(15, 40))
        else:
            radius = rng.uniform(150, 500)
            omega = speed / max(radius, 1.0)
            pos = _smooth_orbit(t, cx, cy, alt, radius, omega, phase, climb)

        # keep inside the site & above ground
        pos[:, 2] = np.clip(pos[:, 2], 15.0, None)
        vel = _velocity(t, pos)

        # staggered appearance so tracks are born/die during the mission
        t_appear = 0.0 if i == 0 else rng.uniform(0, 0.25 * scn.duration_s)
        t_disappear = np.inf
        if rng.random() < 0.25:
            t_disappear = rng.uniform(0.6 * scn.duration_s, scn.duration_s)

        targets.append(
            GroundTruth(
                truth_id=i,
                uav_class=uav_class,
                t=t,
                pos=pos,
                vel=vel,
                rf_active=bool(spec["rf"]),
                t_appear=t_appear,
                t_disappear=t_disappear,
            )
        )
    return targets
