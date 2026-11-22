"""Export the input data of the experiments (Data S1) to plain CSV/JSON files in data/."""
from __future__ import annotations

import csv
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from crtm_ois import bnk_pay, five_states                      # noqa: E402
from crtm_ois.scenarios import REFERENCE_E1, STATES, compare_rule_with_table  # noqa: E402


def main():
    out = ROOT / "data"
    out.mkdir(exist_ok=True)
    cfg = bnk_pay()
    table = five_states(cfg, "table")
    rule = five_states(cfg, "rule")
    with open(out / "metric_catalog.csv", "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["goal", "task", "action", "action_name", "metric", "metric_name", "unit", "polarity_sigma",
                    "xi0_critical", "xi1", "xi2", "xi3", "xi4", "xi5_ideal", "weight", "core", "discrete_step",
                    "measurement_source"])
        for a in cfg.actions:
            for m in a.metrics:
                w.writerow([a.goal, a.task, a.code, a.name, m.code, m.name, m.unit, m.sigma, *m.xi,
                            round(m.weight, 6), int(m.core), m.step or "", m.source])
    for name, st in (("inputs_E1_E5_table_A1.csv", table), ("inputs_E1_E5_rule12.csv", rule)):
        with open(out / name, "w", newline="") as f:
            w = csv.writer(f)
            w.writerow(["action", "metric", *STATES])
            for k in cfg.keys():
                w.writerow([*k, *["n.r." if st[e][k] is None else st[e][k] for e in STATES]])
    ref = {"source": "Korchenko et al., Information 2026, 17, 1170 (Table 5 of the manuscript)",
           "tolerance": 0.0005, "state": "E1",
           "actions": REFERENCE_E1["actions"],
           "enclosure": {k: list(v) for k, v in REFERENCE_E1["enclosure"].items()},
           "goals_mean": REFERENCE_E1["goals_mean"], "goals_min": REFERENCE_E1["goals_min"]}
    (out / "reference_values_CRTM.json").write_text(json.dumps(ref, indent=2))
    (out / "state_parameters.json").write_text(json.dumps(
        {"t": STATES, "rule": "u' = u + |t| (eta* - u); discrete metrics rounded, ties to even",
         "differences_rule_vs_table_A1": compare_rule_with_table(cfg),
         "configuration_version": cfg.version, "seed": cfg.seed, "theta": cfg.theta,
         "goal_weights": cfg.goal_weights}, indent=2))
    print("written:", sorted(p.name for p in out.iterdir()))


if __name__ == "__main__":
    main()
