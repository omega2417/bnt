"""Randomized blocked run schedule (protocol section 4.2, Listing 1).

Configuration order is randomised inside every ``topology x load`` block
to break confounding with time of day, ambient traffic, thermal drift and
disk warm-up.  The schedule is a pure function of the campaign profile
and the master seed, so re-generating it anywhere yields byte-identical
CSV.
"""

from __future__ import annotations

import itertools
from pathlib import Path

import numpy as np
import pandas as pd

from .config import CampaignProfile, MASTER_SEED, get_profile

SCHEDULE_COLUMNS = [
    "run_id",
    "block",
    "order",
    "config",
    "topology",
    "load_tps",
    "repeat",
    "trace_id",
    "cell_id",
]


def build_schedule(
    profile: CampaignProfile | str, seed: int = MASTER_SEED
) -> pd.DataFrame:
    """Return the randomized schedule of every run in the campaign.

    ``trace_id`` identifies the immutable workload trace shared by all
    configurations and topologies of the same ``load x repeat`` pair; it
    is what makes the design paired.  ``run_id`` stays unique per
    execution.
    """
    if isinstance(profile, str):
        profile = get_profile(profile)

    rng = np.random.default_rng(seed)

    rows = list(
        itertools.product(
            profile.configs, profile.topologies, profile.loads_tps,
            range(1, profile.repeats + 1),
        )
    )
    schedule = pd.DataFrame(
        rows, columns=["config", "topology", "load_tps", "repeat"]
    )
    schedule["trace_id"] = (
        "L" + schedule.load_tps.astype(str)
        + "-R" + schedule.repeat.astype(str).str.zfill(2)
    )
    schedule["block"] = schedule.topology + "_" + schedule.load_tps.astype(str)
    schedule["cell_id"] = (
        schedule.config + "_" + schedule.topology + "_"
        + schedule.load_tps.astype(str)
    )
    # Randomise the order of the configurations within each block.  The
    # permutation is drawn per block from a single generator, so the whole
    # schedule is reproducible from one seed.
    schedule["order"] = schedule.groupby("block", sort=True)["repeat"].transform(
        lambda s: rng.permutation(len(s))
    )
    schedule = schedule.sort_values(["block", "order"], kind="mergesort")
    schedule = schedule.reset_index(drop=True)
    schedule["run_id"] = [f"RUN-{i:04d}" for i in range(1, len(schedule) + 1)]

    assert len(schedule) == profile.n_runs, "schedule size must equal equation (1)"
    return schedule[SCHEDULE_COLUMNS]


def write_schedule(
    profile: CampaignProfile | str, out_path: Path, seed: int = MASTER_SEED
) -> Path:
    """Write the schedule to CSV with a stable column order and line ending."""
    schedule = build_schedule(profile, seed=seed)
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    schedule.to_csv(out_path, index=False, lineterminator="\n")
    return out_path


def read_schedule(path: Path) -> pd.DataFrame:
    return pd.read_csv(path)
