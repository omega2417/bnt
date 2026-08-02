"""Per-seed dataset construction with scenario-level train/val/test split."""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from .. import ATTACK_CLASSES, BENIGN_LABEL
from ..features.pipeline import build_windows
from ..rng import seed_from_label
from ..schemas import ADAConfig, DatasetConfig, ScenarioConfig
from ..simulation.scenario_engine import MissionData, simulate_mission
from .overrides import make_attack

__all__ = ["SeedDataset", "build_seed_dataset", "assign_splits"]


@dataclass
class SeedDataset:
    seed: int
    train: pd.DataFrame
    val: pd.DataFrame
    test: pd.DataFrame
    missions: list[MissionData]
    feature_dim: int
    class_counts: dict[str, dict[str, int]]  # split -> label -> n windows


def assign_splits(n: int, ds: DatasetConfig) -> list[str]:
    """Assign ``n`` missions of a class to splits at scenario level."""
    if n <= 1:
        return ["train"]
    if n == 2:
        return ["train", "test"]
    n_test = max(1, round(n * ds.test_frac))
    n_val = max(1, round(n * ds.val_frac))
    n_train = n - n_val - n_test
    # Guarantee at least one train mission, borrowing from val then test.
    while n_train < 1:
        if n_val > 1:
            n_val -= 1
        elif n_test > 1:
            n_test -= 1
        else:
            break
        n_train += 1
    # Trim any overshoot (rare) from test/val while keeping >=1 train.
    while n_train + n_val + n_test > n:
        if n_test > 1:
            n_test -= 1
        elif n_val > 1:
            n_val -= 1
        else:
            n_train -= 1
    splits = ["train"] * n_train + ["val"] * n_val + ["test"] * n_test
    return splits[:n]


def build_seed_dataset(
    scenario: ScenarioConfig, ada: ADAConfig, ds: DatasetConfig, seed: int
) -> SeedDataset:
    classes = [BENIGN_LABEL, *ATTACK_CLASSES]
    missions: list[MissionData] = []
    idx = 0
    for cls in classes:
        n = ds.missions_per_class
        splits = assign_splits(n, ds)
        for j in range(n):
            mission_seed = seed_from_label(f"{cls}-{j}", seed)
            attack = None if cls == BENIGN_LABEL else make_attack(cls, scenario, j)
            m = simulate_mission(scenario, attack, mission_seed, idx, split=splits[j])
            missions.append(m)
            idx += 1

    windows = build_windows(missions, scenario, ada)
    # Propagate split from mission frames (build_windows preserves 'split'? assign here).
    split_of = {m.run_id: m.frame["split"].iloc[0] for m in missions}
    windows["split"] = windows["run_id"].map(split_of)

    train = windows[windows["split"] == "train"].reset_index(drop=True)
    val = windows[windows["split"] == "val"].reset_index(drop=True)
    test = windows[windows["split"] == "test"].reset_index(drop=True)

    counts = {
        s: windows[windows["split"] == s]["attack_label"].value_counts().to_dict()
        for s in ("train", "val", "test")
    }
    from ..features.pipeline import BASE_NUMERIC_FEATURES, PHASE_FEATURES

    return SeedDataset(
        seed=seed, train=train, val=val, test=test, missions=missions,
        feature_dim=len(BASE_NUMERIC_FEATURES) + len(PHASE_FEATURES), class_counts=counts,
    )
