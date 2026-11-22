"""Regenerate every number, table and figure: python scripts/make_figures.py [--fast]"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from crtm_ois import assess, bnk_pay, five_states                      # noqa: E402
from crtm_ois import experiments as ex                                  # noqa: E402
from crtm_ois.agents.advisor import ImprovementAdvisor                  # noqa: E402
from crtm_ois.agents.ops import ResilienceOperationsCenter, train_neural_agents  # noqa: E402
from crtm_ois.neural.models import (GoalWeightCalibrator, NeuralSurrogate,  # noqa: E402
                                    synthetic_expert_panel)
from crtm_ois.viz import charts, diagrams                               # noqa: E402
from crtm_ois import levels as lv                                       # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--fast", action="store_true", help="fewer Monte Carlo samples and runs")
    args = ap.parse_args()
    n = 40_000 if args.fast else 200_000
    figs, res_dir = ROOT / "figures", ROOT / "results"
    figs.mkdir(exist_ok=True); res_dir.mkdir(exist_ok=True)
    t0 = time.time()
    cfg = bnk_pay()
    res = ex.run_all(res_dir / "results.json", n=n, runs=200 if args.fast else 2000)
    adq = res["adequacy"]
    print("experiments", round(time.time() - t0, 1), "s")

    def save(fig, name):
        fig.savefig(figs / name)
        import matplotlib.pyplot as plt
        plt.close(fig)
        print("  ", name)

    st = five_states(cfg)
    rE = {e: assess(cfg, x, robust=False) for e, x in st.items()}
    save(diagrams.method_stages(), "fig01_method_stages.png")
    save(diagrams.structural_model(), "fig02_structural_model.png")
    save(diagrams.hierarchy(rE["E1"]), "fig03_hierarchy_E1.png")
    save(charts.metric_heatmap(adq, cfg, {e: r.norm["M"] for e, r in rE.items()}), "fig04_metric_heatmap.png")
    save(charts.adequacy_figure(adq), "fig05_adequacy.png")
    save(charts.actions_and_sweep(adq, res["sweep"], cfg), "fig06_actions_sweep.png")
    save(charts.robustness_and_noncomp(adq, res["non_compensation"]), "fig07_robustness_noncomp.png")
    save(charts.normalization_figure(cfg), "fig08_normalization.png")
    save(charts.goal_radar(adq), "fig09_goal_radar.png")

    # neural surrogate: monotone vs unconstrained
    nets, evals = {}, {}
    for name, mono in (("monotone", True), ("unconstrained", False)):
        s = NeuralSurrogate(cfg, monotone=mono).fit(n=30_000, epochs=150)
        nets[name], evals[name] = s.net, s.evaluate()
        if mono:
            sur_mono = s
    save(charts.surrogate_figure(evals, nets), "fig10_neural_surrogate.png")

    # multi-agent run on the digital twin
    sur, ae, fc = train_neural_agents(cfg)
    oc = ResilienceOperationsCenter(cfg, seed=3, surrogate=sur, ae=ae, forecaster=fc)
    h = oc.run(220)
    save(diagrams.agent_topology(), "fig11_agent_topology.png")
    save(diagrams.sequence_chart(oc.bus, corr=1, title="Dynamic mode on the bus: one assessment run (tick 0)"),
         "fig12_agent_sequence.png")
    save(charts.twin_dashboard(h, cfg), "fig13_twin_dashboard.png")

    adv = ImprovementAdvisor(cfg)
    save(charts.advisor_figure(adv.candidates(st["E1"]), adv.plan(st["E1"])), "fig14_advisor.png")

    G, expert = synthetic_expert_panel(cfg, 300)
    cal = GoalWeightCalibrator().fit(G, expert)
    before = lv.levels(G.mean(1))
    after = lv.levels(G @ cal.omega)
    save(charts.calibration_figure(cal, (0.15, 0.40, 0.30, 0.15), G, expert, before, after, cfg.goals),
         "fig15_calibration.png")

    F, Fl = h["faults"] >= 2, h["flags"]
    extra = {"surrogate": {k: {kk: vv for kk, vv in v.items() if isinstance(vv, float)} for k, v in evals.items()},
             "surrogate_E1": sur_mono.predict_sheet(st["E1"]),
             "twin": {"ticks": int(len(h["t"])), "alerts": h["alerts"], "advice": h["advice"],
                      "dq_recall": float((F & Fl).sum() / max(F.sum(), 1)),
                      "dq_precision": float((F & Fl).sum() / max(Fl.sum(), 1)),
                      "forecast_mae": float(np.nanmean(np.abs(h["forecast"][12:-6] - h["R"][18:])))},
             "calibration": {"omega": cal.omega.tolist(), "true": [0.15, 0.40, 0.30, 0.15]}}
    (res_dir / "agents_neural.json").write_text(json.dumps(extra, indent=2, default=float))
    print("done", round(time.time() - t0, 1), "s")


if __name__ == "__main__":
    main()
