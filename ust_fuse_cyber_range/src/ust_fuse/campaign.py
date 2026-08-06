"""Multi-mission campaigns and the paired Reference-vs-UST-Fuse analysis.

A single mission is anecdote; the proposal's pilot campaign runs 20–30 missions
and analyses variance, effect size and power (sections 10, 13; ЛР-3).  A
:class:`Campaign` replays a scenario across many seeds (and optional domain
randomisation) and produces the paired-statistics table used in the field-trial
report.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional

import numpy as np
import pandas as pd

from .config import RangeConfig, ScenarioConfig, default_range
from .domain import randomize_scenario
from .experiment import ExperimentResult, run_experiment
from .config import ExperimentConfig
from .metrics.stats import PairedResult, paired_comparison, power_analysis
from .rng import RNGHub
from .scenarios import build_scenario

# metric -> lower_is_better
METRIC_DIRECTION = {
    "rmse_pos": True,
    "ospa_mean": True,
    "id_switches": True,
    "n_false_tracks": True,
    "n_missed": True,
    "mota": False,
    "motp": True,
    "track_completeness": False,
    "ece": True,
    "brier": True,
}


@dataclass
class CampaignResult:
    scenario_id: str
    n_missions: int
    per_mission: pd.DataFrame
    paired: Dict[str, PairedResult] = field(default_factory=dict)
    power: Dict[str, Dict] = field(default_factory=dict)
    results: List[ExperimentResult] = field(default_factory=list)

    def paired_table(self) -> pd.DataFrame:
        rows = []
        for metric, pr in self.paired.items():
            row = pr.to_dict()
            row["power"] = self.power.get(metric, {}).get("power", np.nan)
            rows.append(row)
        return pd.DataFrame(rows)


class Campaign:
    def __init__(
        self,
        scenario,
        range_cfg: Optional[RangeConfig] = None,
        n_missions: int = 20,
        base_seed: int = 20260101,
        domain_randomize: bool = False,
        fusion_modes: Optional[List[str]] = None,
    ):
        if isinstance(scenario, str):
            scenario = build_scenario(scenario)
        self.scenario = scenario
        self.range_cfg = range_cfg or default_range()
        self.n_missions = n_missions
        self.base_seed = base_seed
        self.domain_randomize = domain_randomize
        self.fusion_modes = fusion_modes or ["reference", "ust_fuse"]

    def run(self, verbose: bool = False) -> CampaignResult:
        rows: List[Dict] = []
        results: List[ExperimentResult] = []
        rand_hub = RNGHub(self.base_seed)

        for i in range(self.n_missions):
            seed = self.base_seed + 1009 * i
            scn = (
                randomize_scenario(self.scenario, rand_hub, i)
                if self.domain_randomize else self.scenario
            )
            cfg = ExperimentConfig(
                scenario=scn, range_cfg=self.range_cfg, seed=seed,
                fusion_modes=self.fusion_modes,
            )
            res = run_experiment(cfg)
            results.append(res)
            for mode, mr in res.modes.items():
                row = mr.summary()
                row.update({"mission": i, "seed": seed, "weather": scn.weather})
                rows.append(row)
            if verbose:
                print(f"  mission {i+1}/{self.n_missions} done (seed={seed})")

        df = pd.DataFrame(rows)
        paired: Dict[str, PairedResult] = {}
        power: Dict[str, Dict] = {}
        if set(self.fusion_modes) >= {"reference", "ust_fuse"}:
            a = df[df["mode"] == "reference"].sort_values("mission")
            b = df[df["mode"] == "ust_fuse"].sort_values("mission")
            for metric, lower in METRIC_DIRECTION.items():
                if metric not in df.columns:
                    continue
                pr = paired_comparison(
                    a[metric].to_numpy(), b[metric].to_numpy(),
                    metric=metric, lower_is_better=lower,
                )
                paired[metric] = pr
                power[metric] = power_analysis(pr.cohens_d, pr.n)

        return CampaignResult(
            scenario_id=self.scenario.scenario_id,
            n_missions=self.n_missions,
            per_mission=df,
            paired=paired,
            power=power,
            results=results,
        )
