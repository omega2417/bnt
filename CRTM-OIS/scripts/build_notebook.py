"""Build and execute the English demo notebook notebooks/CRTM_OIS_demo.ipynb."""
from pathlib import Path

import nbformat as nbf
from nbclient import NotebookClient

ROOT = Path(__file__).resolve().parents[1]
nb = nbf.v4.new_notebook()
C = []


def md(s):
    C.append(nbf.v4.new_markdown_cell(s.strip()))


def code(s):
    C.append(nbf.v4.new_code_cell(s.strip()))


md("""
# CRTM-OIS — demonstration notebook

Software for the manuscript **"A Staged Method and System for Computing the Integral Cyber Resilience of Critical
Infrastructure Objects: A Systems Approach Based on a Set-Theoretic Tuple Metric Model"** (*Systems*, MDPI),
extended with an **agent layer** and **neural components**.

| § | Content | Manuscript |
|---|---|---|
| 1 | Scenario BNK_PAY, metric tuples, class tables | §2.1, §2.5, Table A1 |
| 2 | The seven stages on one run, bus by bus | §2.2, Table 1, Table 6 |
| 3 | Structural model: blocks B0–B8, control unit CU, nine buses | §2.3, Figs. 1–2, Tables 2–3 |
| 4 | Reproduction of the 15 published reference values | §3.1, Table 5 |
| 5 | Five adequacy experiments and the sweep of t | §3.3, Table 7, Figs. 5–6 |
| 6 | Weight robustness and non-compensation control | §3.4, Fig. 7 |
| 7 | **Agent layer**: blocks as agents on a message bus | extension |
| 8 | **Neural surrogate** (monotone MLP) vs. the exact system | extension |
| 9 | **Digital twin + multi-agent operations center**: telemetry, autoencoder, forecaster, watchdog | extension of §4.2 |
| 10 | **Advisor agent**: exact what-if and improvement plan | extension of §4.1, §4.3 |
| 11 | **LLM analyst** (tools for Claude) and offline report | extension |
| 12 | **Calibration of goal weights** against expert levels | future work, §4.5 |

> The scenario data are the illustrative values of CRTM [37], not field measurements. The experiments verify the
> implementation, not the validity of verdicts for real objects. The digital twin (§9) and the expert panel (§12) are synthetic.
""")

code("""
import sys, time, json, warnings
from pathlib import Path
sys.path.insert(0, str(Path.cwd().parent))     # project root
warnings.filterwarnings("ignore")
import numpy as np, pandas as pd
import matplotlib.pyplot as plt
%matplotlib inline
from crtm_ois import *
from crtm_ois import levels as lv, experiments as ex
from crtm_ois.viz import charts, diagrams
pd.set_option("display.width", 200); pd.set_option("display.max_columns", 30)
cfg = bnk_pay()
print(SOFTWARE_VERSION, "| configuration", cfg.version, "| metrics:", cfg.n_metrics, "| basic actions:", len(cfg.actions))
""")

md("## 1. Scenario and metric model\nEach basic action β carries a tuple of metric descriptors: class table ξ ∈ ℝ⁶, polarity σ, weight and core flag (*).")
code("""
rows = []
for a in cfg.actions:
    for m in a.metrics:
        rows.append({"goal": a.goal, "action": a.code, "metric": m.code + ("*" if m.core else ""), "name": m.name,
                     "unit": m.unit, "σ": m.sigma, "ξ": m.xi, "w": round(m.weight, 3),
                     "discrete step": m.step, "E1": e1_values()[(a.code, m.code)]})
pd.DataFrame(rows)
""")
md("The anchored piecewise-linear normalization (4) agrees with the class table by construction; min–max rescaling does not:")
code("fig = charts.normalization_figure(cfg); plt.show()")

md("## 2. The seven stages on one run (state E1)\nThe control unit `assess` calls the stages in order; every stage returns the record of a bus.")
code("""
r = assess(cfg, e1_values(), n=200_000)
print("trace:", " → ".join(f"{t['bus']}({t['block']})" for t in r.trace.records))
print(f"R = {r.R['R']:.4f} ({r.R['level_name']}),  R_min = {r.R['R_min']:.4f},  [R_L, R_U] = [{r.R['R_L']:.4f}, {r.R['R_U']:.4f}]")
print("stable w.r.t. missing data:", r.R["stable_missing"], "| weakest goal:", r.R["weakest_goal"], "| time:", round(r.elapsed_ms,1), "ms")
""")
md("Dynamic mode for action UN.S1.A1 in states E1 and E2 (Table 6 of the manuscript):")
code("""
st = five_states(cfg)
def table6(e):
    rr = assess(cfg, st[e], robust=False); a = cfg.action("UN.S1.A1")
    d = pd.DataFrame([{"exp": e, "code": m.code + ("*" if m.core else ""), "x (bus X)": st[e][("UN.S1.A1", m.code)],
                       "ξ": m.xi, "m (bus M)": round(rr.norm["M"][("UN.S1.A1", m.code)], 4),
                       "level": lv.code(rr.norm["Lambda"][("UN.S1.A1", m.code)]), "w": m.weight,
                       "w·m": round(m.weight * rr.norm["M"][("UN.S1.A1", m.code)], 4)} for m in a.metrics])
    A = rr.A["UN.S1.A1"]
    print(f"{e}: S = {A['S']:.4f}, c = {A['c']:.2f}, μ = {A['mu']:.4f} ({lv.code(A['level'])})")
    return d
pd.concat([table6("E1"), table6("E2")])
""")

md("## 3. Structural model of the system")
code("fig = diagrams.method_stages(); plt.show()\nfig = diagrams.structural_model(); plt.show()")
code("""
pd.DataFrame([{"bus": b, "from": s, "to": d, "quantities": q} for b, (s, d, q) in BUSES.items()])
""")
code("fig = diagrams.hierarchy(assess(cfg, e1_values(), robust=False)); plt.show()")

md("## 4. Reproduction of the published CRTM values (Table 5)\nTolerance 0.0005, half a unit of the last published decimal.")
code("""
rep = ex.reproduction(cfg)
df = pd.DataFrame(rep["rows"]); df["system"] = df["system"].round(4); df["abs_diff"] = df["abs_diff"].round(5)
print(f"reproduced {rep['n_ok']}/{rep['n']}, max |Δ| = {rep['max_abs_diff']:.5f}; enclosure CN.S2.A1: {rep['enclosure']['ok']}; "
      f"integral index vs. hand calculation: {rep['integral_system']:.4f} vs {rep['integral_hand']:.4f}")
df
""")
md("Rule (12) vs. the published Table A1. Two differences were found (E2, UN.S1.A1, M3/M4: 102/142 in the table, 102.5/142.5 by the rule); "
   "the published table is used by default; the effect on R is below 0.0002:")
code("""
from crtm_ois.scenarios import compare_rule_with_table
print(compare_rule_with_table(cfg))
rule = five_states(cfg, source="rule")
print("R(E2) table vs rule:", round(assess(cfg, st["E2"], robust=False).index, 5), round(assess(cfg, rule["E2"], robust=False).index, 5))
""")

md("## 5. Five adequacy experiments (Table 7, Figs. 5–6)")
code("""
t0 = time.time(); adq = ex.adequacy(cfg, n=200_000); sw = ex.sweep(cfg)
tab = pd.DataFrame([{ "exp": e, "t": adq[e]["t"], "goals ANT/WITH/REC/AD": " / ".join(f"{adq[e]['goals_mean'][g]:.3f}" for g in GOALS),
    "R": round(adq[e]["R"], 3), "level": adq[e]["level_code"], "expected": lv.code(adq[e]["expected"]), "R_min": round(adq[e]["R_min"], 3),
    "[R_L, R_U]": f"[{adq[e]['R_L']:.3f}, {adq[e]['R_U']:.3f}]", "R̄ ± sd": f"{adq[e]['mc']['mean']:.3f} ± {adq[e]['mc']['sd']:.3f}",
    "shares": ", ".join(f"{k} {v:.1%}" for k, v in adq[e]["mc"]["shares"].items() if v > 0.0005), "vetoed": ", ".join(adq[e]["vetoed"]) or "—"}
    for e in ["E1", "E2", "E3", "E4", "E5"]])
print("order E4<E2<E1<E3<E5:", adq["_order_ok"], "| R monotone:", sw["monotone_R"], "| boundary crossings:",
      {k: round(v, 3) for k, v in sw["crossings"].items()}, f"| {time.time()-t0:.1f} s")
tab
""")
code("fig = charts.adequacy_figure(adq); plt.show()\nfig = charts.actions_and_sweep(adq, sw, cfg); plt.show()")
code("""
norms = {e: assess(cfg, x, robust=False).norm["M"] for e, x in st.items()}
fig = charts.metric_heatmap(adq, cfg, norms); plt.show()
fig = charts.goal_radar(adq); plt.show()
""")

md("## 6. Weight robustness and non-compensation (Fig. 7)")
code("""
nc = ex.non_compensation(cfg)
fig = charts.robustness_and_noncomp(adq, nc); plt.show()
rb = ex.robustness_rho(cfg, n=200_000)
pd.DataFrame({(rho, e): {k: f"{v:.1%}" for k, v in d["shares"].items() if v > 0} for rho, dd in rb.items() for e, d in dd.items()}).T
""")
code("""
pd.DataFrame({op: [round(v, 3) for v in nc[op]["action"]] for op in ("additive", "hard", "capped")},
             index=pd.Index(nc["sources"], name="TI sources")).assign(R_capped=[round(v, 3) for v in nc["capped"]["R"]],
                                                                     R_min_capped=nc["capped"]["R_min"])
""")

md("""
## 7. Agent layer: blocks B0–B8 and CU as agents on a message bus
Every block of the structural model is an agent that subscribes to its input buses (topics) and publishes its output bus.
A block fires when all its inputs for one run (correlation id) have arrived. The agent team agrees with `assess` to 1e-12;
a failure in B2 stops the chain (CU publishes `stop`).
""")
code("""
from crtm_ois.agents.bus import MessageBus
from crtm_ois.agents.blocks import build_block_team
bus = MessageBus(); reports = []
bus.subscribe("report", lambda m: reports.append(m.payload))
ref, cu, blocks = build_block_team(bus, cfg, mc_samples=20_000)
for e, x in st.items():
    cu.start(x)
    print(e, f"agents R = {reports[-1]['R']:.6f}", f"| CU/assess R = {assess(cfg, x, robust=False).index:.6f}", "| level", reports[-1]["level_code"])
c = cu.start({**e1_values(), ("UN.S1.A1", "M1"): None})       # core metric missing
print("run", c, "→", cu.failures[c])
print("messages on the bus:", len(bus.log), "| statuses of run 1:", cu.status[1])
""")
code("fig = diagrams.agent_topology(); plt.show()")

md("""
## 8. Neural surrogate: monotone vs. unconstrained MLP
The network learns the map "raw measurements → (R, R_min)" on states labelled by the exact system. In the monotone
network every weight is parameterised as softplus(v) ≥ 0, so R̂ is nondecreasing in every metric — the neural
counterpart of adequacy criterion (iii). The surrogate is advisory: at a level boundary (E1 = 0.698) it errs, so the
verdict is issued by the exact system.
""")
code("""
from crtm_ois.neural.models import NeuralSurrogate
nets, evals, surs = {}, {}, {}
for name, mono in (("monotone", True), ("unconstrained", False)):
    t0 = time.time(); s = NeuralSurrogate(cfg, monotone=mono).fit(n=30_000, epochs=150)
    surs[name], nets[name], evals[name] = s, s.net, s.evaluate()
    print(f"{name:14s} params={s.net.n_params():5d}  MAE(R)={evals[name]['mae_R']:.4f}  MAE(R_min)={evals[name]['mae_Rmin']:.4f}  "
          f"level acc={evals[name]['level_accuracy']:.1%}  monotonicity violations={evals[name]['monotone_violations']:.1%}  ({time.time()-t0:.0f} s)")
for e in st:
    p = surs["monotone"].predict_sheet(st[e]); exact = assess(cfg, st[e], robust=False)
    print(e, f"neural R̂={p['R']:.3f} ({lv.code(p['level'])})  exact R={exact.index:.3f} ({exact.R['level_code']})")
fig = charts.surrogate_figure(evals, nets); plt.show()
""")
md("The gradient of the surrogate gives an instant sensitivity map (∂R̂/∂ metric position), used to pre-select candidates before the exact what-if:")
code("""
sens = surs["monotone"].sensitivity(e1_values())
top = sorted(sens.items(), key=lambda kv: -kv[1])[:10]
fig, ax = plt.subplots(figsize=(8, 3.6))
ax.barh([f"{a}.{m}" for (a, m), _ in top][::-1], [v for _, v in top][::-1], color="#6250d6", height=0.6)
ax.set_xlabel("∂R̂ / ∂(position)"); ax.set_title("Neural sensitivity at E1 (top 10 metrics)"); plt.show()
""")

md("""
## 9. Digital twin and multi-agent resilience operations center
A synthetic twin of the processing center emits telemetry of the 39 metrics (phishing incident, TI provider outage,
improvement programme) with sensor defects (missing values, spikes, stuck readings).

Agents: **TEL** (telemetry) → **DQ** (autoencoder + persistence rule for core metrics) → **CU/B0–B8** (exact verdict)
→ **FC** (neural forecast, 6 ticks ahead) → **WD** (watchdog with hysteresis) → **ADV** (advisor). **NN** gives a neural nowcast in parallel.
""")
code("""
from crtm_ois.agents.ops import ResilienceOperationsCenter, train_neural_agents
t0 = time.time(); sur, ae, fc = train_neural_agents(cfg); print(f"training of the neural agents: {time.time()-t0:.0f} s")
oc = ResilienceOperationsCenter(cfg, seed=3, surrogate=sur, ae=ae, forecaster=fc)
t0 = time.time(); h = oc.run(220); print(f"220 ticks: {time.time()-t0:.1f} s, messages on the bus: {len(oc.bus.log)}")
F, Fl = h["faults"] >= 2, h["flags"]
print(f"DQ: recall={(F & Fl).sum()/F.sum():.0%}, precision={(F & Fl).sum()/Fl.sum():.0%} | "
      f"forecast MAE={np.nanmean(np.abs(h['forecast'][12:-6]-h['R'][18:])):.4f} | nowcast MAE={np.mean(np.abs(h['nowcast']-h['R'])):.4f}")
fig = charts.twin_dashboard(h, cfg); plt.show()
""")
code("pd.DataFrame(h['alerts'])[['tick', 'severity', 'kind', 'text']]")
code("pd.DataFrame(h['advice'])")
code("fig = diagrams.sequence_chart(oc.bus, corr=1, title='Dynamic mode on the bus: one assessment run (tick 0)'); plt.show()")

md("""
## 10. Advisor agent: exact what-if and improvement plan
Candidates act on **physical measurements**: the shared measurement AM-DA-1 changes both actions of the goal Withstand at
once (horizontal dependency, §4.3). The plan targets a stable verdict, i.e. the guaranteed index R_L above the level boundary.
""")
code("""
from crtm_ois.agents.advisor import ImprovementAdvisor
adv = ImprovementAdvisor(cfg)
cands = adv.candidates(e1_values()); plan = adv.plan(e1_values())
display(pd.DataFrame(cands)[["source", "from", "to", "dR", "dR_L", "dR_min"]].head(10).round(4))
print("unreported value:", adv.missing_value_thresholds(e1_values()))
fig = charts.advisor_figure(cands, plan); plt.show()
""")

md("""
## 11. LLM analyst: the system as a set of tools
`ResilienceToolbox` exposes six tools with JSON schemas (`load_state`, `assess_current`, `explain_action`, `what_if`,
`recommend`, `get_trace`). `ClaudeAnalyst` runs the Claude API tool-use loop (SDK `tool_runner`, model `claude-opus-5-5`,
adaptive thinking, server-side fallbacks); every number in its answer comes from the tools, i.e. from the exact system.
`OfflineAnalyst` uses the same tools without network access.
""")
code("""
from crtm_ois.agents.llm import ResilienceToolbox, OfflineAnalyst, ClaudeAnalyst
tb = ResilienceToolbox(cfg)
print(json.dumps([s["name"] + ": " + s["description"][:70] for s in tb.schemas()], indent=1, ensure_ascii=False))
print(json.dumps(tb.what_if("CN.S1.A1", "AM-DA-1", 90), ensure_ascii=False))
""")
code("from IPython.display import Markdown\nMarkdown(OfflineAnalyst(tb).report('E1'))")
code("""
import os
if os.environ.get("ANTHROPIC_API_KEY"):
    analyst = ClaudeAnalyst(ResilienceToolbox(cfg))
    print(analyst.ask("Assess the current state E1 of the processing center: is the verdict stable and what should be improved first?"))
else:
    print("ANTHROPIC_API_KEY is not set — skipping the Claude call (see OfflineAnalyst above).")
""")

md("""
## 12. Calibration of goal weights against expert levels (future work, §4.5)
A synthetic expert panel rates 300 objects, implicitly weighting the goals as (0.15, 0.40, 0.30, 0.15).
A differentiable ordinal-logistic model recovers ω; agreement is measured by the quadratic-weighted Cohen kappa.
""")
code("""
from crtm_ois.neural.models import GoalWeightCalibrator, synthetic_expert_panel, quadratic_kappa
G, expert = synthetic_expert_panel(cfg, 300)
cal = GoalWeightCalibrator().fit(G, expert)
before, after = lv.levels(G.mean(1)), lv.levels(G @ cal.omega)
print("learned ω =", np.round(cal.omega, 3), "| κw equal =", round(quadratic_kappa(expert, before), 3), "| κw learned =", round(quadratic_kappa(expert, after), 3))
fig = charts.calibration_figure(cal, (0.15, 0.40, 0.30, 0.15), G, expert, before, after, cfg.goals); plt.show()
""")

md("""
## 13. Summary and limitations
* The exact system reproduces 15/15 published CRTM values within 0.0005, assigns the expected levels to E1–E5 in the
  expected order, is monotone along the sweep, vetoes in E4 and reports missing data by an enclosure; the weight shares of E1 are 54.4 % / 45.6 %.
* The agent layer realises the structural model literally (blocks = agents, buses = topics) and gives the same result.
* The neural components are advisory: the monotone surrogate has no monotonicity violations but errs at level boundaries;
  the autoencoder and the persistence rule filter sensor faults before they cause a false veto.
* The twin, the sensor faults and the expert panel are synthetic; field validity is not established.
""")

nb["cells"] = C
nb["metadata"]["kernelspec"] = {"name": "python3", "display_name": "Python 3", "language": "python"}
out = ROOT / "notebooks" / "CRTM_OIS_demo.ipynb"
NotebookClient(nb, timeout=900, kernel_name="python3", resources={"metadata": {"path": str(out.parent)}}).execute()
nbf.write(nb, out)
print("written", out)
