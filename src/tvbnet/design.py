"""Scenario design: full crossing of structural factors with an L9(3^4) orthogonal array."""
from __future__ import annotations

import itertools
import hashlib

import numpy as np
import pandas as pd

# Standard L9(3^4) orthogonal array, level codes 1..3 (same array as uavews 0.2.0 plan).
L9 = np.array([
    (1, 1, 1, 1), (1, 2, 2, 3), (1, 3, 3, 2),
    (2, 1, 2, 2), (2, 2, 3, 1), (2, 3, 1, 3),
    (3, 1, 3, 3), (3, 2, 1, 2), (3, 3, 2, 1),
])
L9_FACTORS = ["effectiveness_mean", "input_reliability", "impact_multiplier", "budget_fraction"]


def stable_id(prefix: str, *parts) -> str:
    """Non-semantic, deterministic identifier (truncated SHA-256)."""
    h = hashlib.sha256("|".join(map(str, (prefix,) + parts)).encode()).hexdigest()
    return f"{prefix}-{h[:12]}"


def l9_balance(arr: np.ndarray = L9) -> bool:
    """Every pair of columns contains each level pair exactly once."""
    for i, j in itertools.combinations(range(arr.shape[1]), 2):
        pairs = {(a, b) for a, b in zip(arr[:, i], arr[:, j])}
        if len(pairs) != 9:
            return False
    return True


def build_design(cfg: dict) -> pd.DataFrame:
    rows = []
    lv = cfg["l9_factors"]
    for top, fam, depth in itertools.product(cfg["topologies"], cfg["families"], cfg["depth_levels"]):
        for r_idx, row in enumerate(L9, start=1):
            cell = stable_id("cell", top, fam, depth, r_idx)
            for rep in range(1, cfg["replicates"] + 1):
                rows.append({
                    "scenario_id": stable_id("scn", top, fam, depth, r_idx, rep),
                    "cell_id": cell,
                    "topology": top,
                    "family": fam,
                    "depth": depth,
                    "l9_row": r_idx,
                    "replicate": rep,
                    **{f: lv[f][row[k] - 1] for k, f in enumerate(L9_FACTORS)},
                })
    return pd.DataFrame(rows)
