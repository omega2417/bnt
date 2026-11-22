"""Build and execute notebooks/CRTM_OIS_demo.ipynb."""
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
# CRTM-OIS — демонстрація програмного проєкту

**Staged Method and System for Computing the Integral Cyber Resilience of Critical Infrastructure Objects**
(рукопис для *Systems*, MDPI) — програмна реалізація, орієнтована на **агентів** і **нейрорішення**.

Ноутбук проходить увесь ланцюг статті і розширення проєкту:

| § | Зміст | Звідки у статті |
|---|---|---|
| 1 | Сценарій BNK_PAY, кортежі метрик, таблиці класів | §2.1, §2.5, Table A1 |
| 2 | Сім етапів методу на одному прогоні, шина за шиною | §2.2, Table 1, Table 6 |
| 3 | Структурна модель B0–B8, CU, дев’ять шин | §2.3, Fig. 1–2, Tables 2–3 |
| 4 | Перевірка відтворення 15 опублікованих значень | §3.1, Table 5 |
| 5 | П’ять експериментів адекватності, розгортка t | §3.3, Table 7, Fig. 5–6 |
| 6 | Робастність до ваг і контроль некомпенсації | §3.4, Fig. 7 |
| 7 | **Агентний шар**: блоки як агенти на шині повідомлень | розширення |
| 8 | **Нейросурогат** (монотонна MLP) проти точної системи | розширення |
| 9 | **Цифровий двійник + мультиагентний центр**: телеметрія, автоенкодер, прогноз, сторож | розширення §4.2 |
| 10 | **Агент-радник**: точний what-if і план покращення | розширення §4.1, §4.3 |
| 11 | **LLM-аналітик** (інструменти для Claude) і офлайн-звіт | розширення |
| 12 | **Калібрування ваг цілей** за експертними рівнями | майбутня робота §4.5 |

> Дані сценарію — ілюстративні значення з CRTM [37], не польові вимірювання. Експерименти верифікують реалізацію, а не
> валідність оцінок реальних об’єктів. Цифровий двійник і «експерти» в §9 і §12 — синтетичні.
""")

code("""
import sys, time, json, warnings
from pathlib import Path
sys.path.insert(0, str(Path.cwd().parent))     # корінь проєкту CRTM-OIS
warnings.filterwarnings("ignore")
import numpy as np, pandas as pd
import matplotlib.pyplot as plt
%matplotlib inline
from crtm_ois import *
from crtm_ois import levels as lv, experiments as ex
from crtm_ois.viz import charts, diagrams
pd.set_option("display.width", 200); pd.set_option("display.max_columns", 30)
cfg = bnk_pay()
print(SOFTWARE_VERSION, "| конфігурація", cfg.version, "| метрик:", cfg.n_metrics, "| дій:", len(cfg.actions))
""")

md("## 1. Сценарій і модель метрик\nКожна базова дія β має кортеж дескрипторів: таблиця класів ξ ∈ ℝ⁶, полярність σ, вага, ознака ключової метрики (*).")
code("""
rows = []
for a in cfg.actions:
    for m in a.metrics:
        rows.append({"goal": a.goal, "action": a.code, "metric": m.code + ("*" if m.core else ""), "name": m.name,
                     "unit": m.unit, "σ": m.sigma, "ξ": m.xi, "w": round(m.weight, 3),
                     "discrete step": m.step, "E1": e1_values()[(a.code, m.code)]})
pd.DataFrame(rows)
""")
md("Анкерована кусково-лінійна нормалізація (4) збігається з таблицею класів за побудовою; лінійне перемасштабування — ні:")
code("fig = charts.normalization_figure(cfg); plt.show()")

md("## 2. Сім етапів на одному прогоні (стан E1)\nКерувальний блок `assess` викликає етапи по черзі; кожен етап повертає запис шини.")
code("""
r = assess(cfg, e1_values(), n=200_000)
print("trace:", " → ".join(f"{t['bus']}({t['block']})" for t in r.trace.records))
print(f"R = {r.R['R']:.4f} ({r.R['level_name']}),  R_min = {r.R['R_min']:.4f},  [R_L, R_U] = [{r.R['R_L']:.4f}, {r.R['R_U']:.4f}]")
print("стабільний щодо пропусків:", r.R["stable_missing"], "| найслабша ціль:", r.R["weakest_goal"], "| час:", round(r.elapsed_ms,1), "мс")
""")
md("Динамічний режим для дії UN.S1.A1 у станах E1 та E2 (Table 6 статті):")
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

md("## 3. Структурна модель системи")
code("fig = diagrams.method_stages(); plt.show()\nfig = diagrams.structural_model(); plt.show()")
code("""
pd.DataFrame([{"bus": b, "from": s, "to": d, "quantities": q} for b, (s, d, q) in BUSES.items()])
""")
code("fig = diagrams.hierarchy(assess(cfg, e1_values(), robust=False)); plt.show()")

md("## 4. Відтворення опублікованих значень CRTM (Table 5)\nДопуск 0.0005 — половина одиниці останнього опублікованого знака.")
code("""
rep = ex.reproduction(cfg)
df = pd.DataFrame(rep["rows"]); df["system"] = df["system"].round(4); df["abs_diff"] = df["abs_diff"].round(5)
print(f"відтворено {rep['n_ok']}/{rep['n']}, max |Δ| = {rep['max_abs_diff']:.5f}; оболонка CN.S2.A1: {rep['enclosure']['ok']}; "
      f"інтегральний індекс vs ручний розрахунок: {rep['integral_system']:.4f} vs {rep['integral_hand']:.4f}")
df
""")
md("Правило (12) проти опублікованої Table A1. Знайдено дві розбіжності (E2, UN.S1.A1, M3/M4: 102/142 у таблиці, 102.5/142.5 за правилом); "
   "за замовчуванням використовується опублікована таблиця, вплив на R < 0.0002:")
code("""
from crtm_ois.scenarios import compare_rule_with_table
print(compare_rule_with_table(cfg))
rule = five_states(cfg, source="rule")
print("R(E2) table vs rule:", round(assess(cfg, st["E2"], robust=False).index, 5), round(assess(cfg, rule["E2"], robust=False).index, 5))
""")

md("## 5. П’ять експериментів адекватності (Table 7, Fig. 5–6)")
code("""
t0 = time.time(); adq = ex.adequacy(cfg, n=200_000); sw = ex.sweep(cfg)
tab = pd.DataFrame([{ "exp": e, "t": adq[e]["t"], "goals ANT/WITH/REC/AD": " / ".join(f"{adq[e]['goals_mean'][g]:.3f}" for g in GOALS),
    "R": round(adq[e]["R"], 3), "level": adq[e]["level_code"], "expected": lv.code(adq[e]["expected"]), "R_min": round(adq[e]["R_min"], 3),
    "[R_L, R_U]": f"[{adq[e]['R_L']:.3f}, {adq[e]['R_U']:.3f}]", "R̄ ± sd": f"{adq[e]['mc']['mean']:.3f} ± {adq[e]['mc']['sd']:.3f}",
    "shares": ", ".join(f"{k} {v:.1%}" for k, v in adq[e]["mc"]["shares"].items() if v > 0.0005), "vetoed": ", ".join(adq[e]["vetoed"]) or "—"}
    for e in ["E1", "E2", "E3", "E4", "E5"]])
print("порядок E4<E2<E1<E3<E5:", adq["_order_ok"], "| монотонність R:", sw["monotone_R"], "| перетини меж:",
      {k: round(v, 3) for k, v in sw["crossings"].items()}, f"| {time.time()-t0:.1f} c")
tab
""")
code("fig = charts.adequacy_figure(adq); plt.show()\nfig = charts.actions_and_sweep(adq, sw, cfg); plt.show()")
code("""
norms = {e: assess(cfg, x, robust=False).norm["M"] for e, x in st.items()}
fig = charts.metric_heatmap(adq, cfg, norms); plt.show()
fig = charts.goal_radar(adq); plt.show()
""")

md("## 6. Робастність до ваг і некомпенсація (Fig. 7)")
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
## 7. Агентний шар: блоки B0–B8 і CU як агенти на шині повідомлень
Кожен блок структурної моделі — агент, що підписаний на свої вхідні шини (топіки) і публікує вихідну шину.
Блок спрацьовує, коли для одного прогону (correlation id) надійшли всі його входи. Результат команди агентів
збігається з `assess` до 1e-12; відмова B2 зупиняє ланцюг (CU публікує `stop`).
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
c = cu.start({**e1_values(), ("UN.S1.A1", "M1"): None})       # ключова метрика відсутня
print("run", c, "→", cu.failures[c])
print("повідомлень на шині:", len(bus.log), "| статуси прогону 1:", cu.status[1])
""")
code("fig = diagrams.agent_topology(); plt.show()")

md("""
## 8. Нейросурогат: монотонна MLP проти необмеженої
Мережа навчається відображенню «сирі вимірювання → (R, R_min)» на станах, згенерованих точною системою.
У монотонній мережі всі ваги параметризовано як softplus(v) ≥ 0, тож R̂ не спадає за жодною метрикою — нейронний аналог
критерію адекватності (iii). Сурогат лише дорадчий: на межі рівнів (E1 = 0.698) він помиляється, тому вердикт видає точна система.
""")
code("""
from crtm_ois.neural.models import NeuralSurrogate
nets, evals, surs = {}, {}, {}
for name, mono in (("monotone", True), ("unconstrained", False)):
    t0 = time.time(); s = NeuralSurrogate(cfg, monotone=mono).fit(n=30_000, epochs=150)
    surs[name], nets[name], evals[name] = s, s.net, s.evaluate()
    print(f"{name:14s} params={s.net.n_params():5d}  MAE(R)={evals[name]['mae_R']:.4f}  MAE(R_min)={evals[name]['mae_Rmin']:.4f}  "
          f"level acc={evals[name]['level_accuracy']:.1%}  monotonicity violations={evals[name]['monotone_violations']:.1%}  ({time.time()-t0:.0f} c)")
for e in st:
    p = surs["monotone"].predict_sheet(st[e]); exact = assess(cfg, st[e], robust=False)
    print(e, f"neural R̂={p['R']:.3f} ({lv.code(p['level'])})  exact R={exact.index:.3f} ({exact.R['level_code']})")
fig = charts.surrogate_figure(evals, nets); plt.show()
""")
md("Градієнт сурогату дає миттєву карту чутливості (∂R̂/∂позиція метрики) — використовується для швидкого відбору кандидатів перед точним what-if:")
code("""
sens = surs["monotone"].sensitivity(e1_values())
top = sorted(sens.items(), key=lambda kv: -kv[1])[:10]
fig, ax = plt.subplots(figsize=(8, 3.6))
ax.barh([f"{a}.{m}" for (a, m), _ in top][::-1], [v for _, v in top][::-1], color="#6250d6", height=0.6)
ax.set_xlabel("∂R̂ / ∂(position)"); ax.set_title("Neural sensitivity at E1 (top 10 metrics)"); plt.show()
""")

md("""
## 9. Цифровий двійник і мультиагентний центр стійкості
Синтетичний двійник процесингового центру генерує телеметрію 39 метрик (інцидент фішингу, відмова постачальника TI,
програма покращення) з вадами сенсорів (пропуски, сплески, «залиплі» значення).

Агенти: **TEL** (телеметрія) → **DQ** (автоенкодер + правило персистентності для ключових метрик) → **CU/B0–B8** (точний вердикт)
→ **FC** (нейропрогноз на 6 тактів) → **WD** (сторож з гістерезисом) → **ADV** (радник). **NN** дає нейронний nowcast паралельно.
""")
code("""
from crtm_ois.agents.ops import ResilienceOperationsCenter, train_neural_agents
t0 = time.time(); sur, ae, fc = train_neural_agents(cfg); print(f"навчання нейроагентів: {time.time()-t0:.0f} c")
oc = ResilienceOperationsCenter(cfg, seed=3, surrogate=sur, ae=ae, forecaster=fc)
t0 = time.time(); h = oc.run(220); print(f"220 тактів: {time.time()-t0:.1f} c, повідомлень на шині: {len(oc.bus.log)}")
F, Fl = h["faults"] >= 2, h["flags"]
print(f"DQ: recall={(F & Fl).sum()/F.sum():.0%}, precision={(F & Fl).sum()/Fl.sum():.0%} | "
      f"forecast MAE={np.nanmean(np.abs(h['forecast'][12:-6]-h['R'][18:])):.4f} | nowcast MAE={np.mean(np.abs(h['nowcast']-h['R'])):.4f}")
fig = charts.twin_dashboard(h, cfg); plt.show()
""")
code("pd.DataFrame(h['alerts'])[['tick', 'severity', 'kind', 'text']]")
code("pd.DataFrame(h['advice'])")
code("fig = diagrams.sequence_chart(oc.bus, corr=1, title='Dynamic mode on the bus: one assessment run (tick 0)'); plt.show()")

md("""
## 10. Агент-радник: точний what-if і план покращення
Кандидати діють на **фізичні вимірювання**: спільне вимірювання AM-DA-1 одночасно змінює обидві дії цілі Withstand
(горизонтальна залежність, §4.3). Мета плану — стійкий вердикт, тобто гарантований індекс R_L вище межі рівня.
""")
code("""
from crtm_ois.agents.advisor import ImprovementAdvisor
adv = ImprovementAdvisor(cfg)
cands = adv.candidates(e1_values()); plan = adv.plan(e1_values())
display(pd.DataFrame(cands)[["source", "from", "to", "dR", "dR_L", "dR_min"]].head(10).round(4))
print("пропущене значення:", adv.missing_value_thresholds(e1_values()))
fig = charts.advisor_figure(cands, plan); plt.show()
""")

md("""
## 11. LLM-аналітик: система як набір інструментів
`ResilienceToolbox` надає шість інструментів з JSON-схемами (`load_state`, `assess_current`, `explain_action`, `what_if`,
`recommend`, `get_trace`). `ClaudeAnalyst` запускає цикл tool use Claude API (SDK `tool_runner`, модель `claude-opus-5-5`,
адаптивне мислення, серверні fallbacks), і кожне число у відповіді береться з інструментів, тобто з точної системи.
`OfflineAnalyst` використовує ті самі інструменти без мережі.
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
    print(analyst.ask("Оціни поточний стан E1 процесингового центру: чи стабільний вердикт і що покращити першочергово?"))
else:
    print("ANTHROPIC_API_KEY не задано — пропускаємо виклик Claude (див. OfflineAnalyst вище).")
""")

md("""
## 12. Калібрування ваг цілей за експертними рівнями (майбутня робота §4.5)
Синтетична панель «експертів» оцінює 300 об’єктів, неявно зважуючи цілі як (0.15, 0.40, 0.30, 0.15).
Диференційовна порядкова логістична модель відновлює ω; узгодженість вимірюємо квадратично зваженою каппою Коена.
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
## 13. Підсумок і обмеження
* Точна система відтворює 15/15 опублікованих значень CRTM у межах 0.0005, призначає очікувані рівні E1–E5 у правильному
  порядку, монотонна вздовж розгортки, накладає вето у E4 і звітує про пропуски оболонкою; частки за вагами E1 — 54.4 % / 45.6 %.
* Агентний шар реалізує структурну модель буквально (блоки = агенти, шини = топіки) і дає той самий результат.
* Нейрорішення дорадчі: монотонний сурогат не має порушень монотонності, але на межі рівнів помиляється; автоенкодер і правило
  персистентності відсіюють збої сенсорів до того, як вони спричинять хибне вето.
* Двійник, збої сенсорів і експертна панель синтетичні; польова валідність не встановлена.
""")

nb["cells"] = C
nb["metadata"]["kernelspec"] = {"name": "python3", "display_name": "Python 3", "language": "python"}
out = ROOT / "notebooks" / "CRTM_OIS_demo.ipynb"
NotebookClient(nb, timeout=900, kernel_name="python3", resources={"metadata": {"path": str(out.parent)}}).execute()
nbf.write(nb, out)
print("written", out)
