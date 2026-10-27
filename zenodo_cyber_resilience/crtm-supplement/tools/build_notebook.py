#!/usr/bin/env python3
"""Build notebooks/CRTM_Colab.ipynb from the package sources.

The setup cell embeds the package, the data files and the reproduction
script, so the notebook runs stand-alone in Google Colab (no upload, no
network access to the repository needed). When the notebook is opened
inside the unpacked supplement, the local sources are used instead.
"""
from __future__ import annotations

import base64
import json
import zlib
from pathlib import Path

import nbformat as nbf

ROOT = Path(__file__).resolve().parent.parent
EMBED = sorted([*ROOT.glob("crtm/*.py"), *ROOT.glob("data/*"), ROOT / "scripts" / "reproduce.py"])


def md(s):
    return nbf.v4.new_markdown_cell(s.strip())


def code(s):
    return nbf.v4.new_code_cell(s.strip())


def setup_cell() -> str:
    files = {str(p.relative_to(ROOT)): p.read_text(encoding="utf-8") for p in EMBED}
    payload = base64.b64encode(zlib.compress(json.dumps(files, ensure_ascii=False).encode("utf-8"), 9)).decode()
    payload = "\n".join(payload[i:i + 100] for i in range(0, len(payload), 100))
    return f'''
# @title ⚙️ Setup: locate or unpack the `crtm` package (run first)
import sys, json, pathlib, importlib, base64, zlib

def _find_local():
    for c in [pathlib.Path.cwd(), *pathlib.Path.cwd().parents][:3]:
        if (c / "crtm" / "__init__.py").exists() and (c / "data" / "phishing_metrics.csv").exists():
            return c
    return None

ROOT = _find_local()
if ROOT is None:
    # stand-alone mode (e.g. Google Colab): write the embedded sources
    ROOT = pathlib.Path("crtm-supplement").resolve()
    _FILES = json.loads(zlib.decompress(base64.b64decode("""
{payload}
""")).decode("utf-8"))
    for rel, text in _FILES.items():
        p = ROOT / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text, encoding="utf-8")
    print(f"unpacked {{len(_FILES)}} embedded files into {{ROOT}}")
sys.path.insert(0, str(ROOT))
import crtm
importlib.reload(crtm)
print("crtm", crtm.__version__, "from", ROOT)
'''


CELLS = [
    md("""
# Cyber-Resilience Tuple Model (CRTM) — interactive digital supplement

Companion notebook for the article

> **A Set-Theoretic Tuple Model with Level-Consistent Normalization and Non-Compensatory
> Aggregation for Assessing the Cyber Resilience of Critical Infrastructure.**
> *Information* (MDPI), 2026. DOI: *to be assigned*. Software DOI (Zenodo): *to be assigned*.

The notebook re-computes every number of the illustrative application (phishing, ATT&CK T1566,
at the bank processing center BNK_PAY), redraws the figures, and lets you change the inputs
interactively. It runs unchanged in **Google Colab** (*Runtime → Run all*) or locally in Jupyter.

| Section | Article | What you can do |
|---|---|---|
| 1 | §3 | identifiers, admissible projections, lattice operations ⊔ / ⊓, Jaccard distance |
| 2 | §4–5 | class tables, Theorem 1, Corollary 1, anchored normalization, consistency check |
| 3 | §6 | knockout operators (hard gate, power, capped) — sliders for γ, ϑ and the core metric |
| 4 | §7.2 | worked example UN.S1.A1 (Table 5) |
| 5 | §7.4 | sensitivity to response times — sliders for τ₃, τ₄ |
| 6 | §7.5 | random weights (Dirichlet), closed-form moments vs Monte Carlo |
| 7 | §7.6 | scenario profile, missing-metric enclosure (Table 6) |
| 8 | — | full reproduction check (107 published values) and export |
| 9 | — | sandbox: score your own metric |

*The numerical values are the illustrative example values of the source study, not field measurements.*
"""),
    code(setup_cell()),
    code("""
import numpy as np, pandas as pd, matplotlib.pyplot as plt
from IPython.display import display, Markdown
from crtm import aggregation as agg, sensitivity as sens, uncertainty as unc, figures as F
from crtm.hierarchy import Projection, iota, iota_inv, check_code, jaccard_index
pd.set_option("display.precision", 4)
actions = crtm.load_metrics()
scen = crtm.load_scenarios()
UN = actions["UN.S1.A1"]
try:
    import ipywidgets as W
    HAVE_WIDGETS = True
except ImportError:
    HAVE_WIDGETS = False
print("actions:", list(actions), "| metrics:", sum(a.q for a in actions.values()),
      "| widgets:", HAVE_WIDGETS)
"""),
    md("""
## 1. Set-theoretic data model (Section 3)

**Proposition 1.** The identifier map ι(i, j, k) = c_i.Sj.Ak is injective and is inverted by parsing.
The check below also illustrates the *mixed-script* defect found in the source tabulation: a Cyrillic
«С» that looks like a Latin «C».
"""),
    code("""
print(iota(6, 1, 1), "->", iota_inv("UN.S1.A1"))
print("Latin 'CN'   :", check_code("CN") or "valid")
print("Cyrillic 'СN':", check_code("\\u0421N"))
"""),
    md("""
**Definition 3 / Proposition 2.** A projection is *admissible* if it uses only catalog techniques of each
action. Admissible projections form a finite distributive lattice: join ⊔ = compound threat,
meet ⊓ = common actions.
"""),
    code("""
P, Q = scen["projections"]["DDoS"], scen["projections"]["phishing"]
J, M = P | Q, P & Q
print("admissible:", P.is_admissible(scen["catalog"]), Q.is_admissible(scen["catalog"]))
print("meet  P⊓Q :", sorted(M.actions))
print("|join| =", len(J.actions), " Jaccard(actions) =", round(jaccard_index(P.actions, Q.actions), 4))
print("|E(P)|, |E(Q)| =", len(P.downset()), len(Q.downset()),
      " Jaccard(down-sets) =", round(jaccard_index(P.downset(), Q.downset()), 4))
print("inadmissible example:", Projection({"UN.S3.A1": {"CA"}}).violations(scen["catalog"]))
F.fig_projections(scen); plt.show()
"""),
    md("""
## 2. Metric model and level-consistent normalization (Sections 4–5)

All 39 metrics of the phishing scenario with their class tables ξ (Appendix A).
`tab` is the level printed in the class table; `lin`/`anc` are the levels of the two normalizations.
"""),
    code("""
rows = []
for b, a in actions.items():
    for p, mt in enumerate(a.metrics):
        nl, na = mt.normalized("linear"), mt.normalized("anchored")
        rows.append(dict(action=b, p=p+1, code=mt.code + ("*" if mt.core else ""), metric=mt.name,
                         unit=mt.unit, xi=mt.table.xi, value=mt.value,
                         tab=crtm.LEVEL_ABBR[mt.tabulated_level()-1] if mt.observed else "n.r.",
                         n_ch=nl, lin=crtm.level_abbr(nl), nu=na, anc=crtm.level_abbr(na)))
tA1 = pd.DataFrame(rows)
tA1["linear consistent"] = (tA1["lin"] == tA1["tab"]) | (tA1["tab"] == "n.r.")
display(tA1)
print("inconsistent linear scores:", (~tA1["linear consistent"]).sum(), "of", (tA1["tab"] != "n.r.").sum())
"""),
    md("""
**Theorem 1 / Corollary 1.** A clipped affine map can match a five-level class table only if the
class boundaries are evenly spaced relative to y = (0, .2, .4, .7, .9, 1). The two-anchor rule
n_{c,h} sends η₄ to 1 ≠ 0.9 and is therefore *never* consistent: the interval below is always nonempty.
"""),
    code("""
t3 = UN.metrics[2].table
print("Theorem 1 condition (11) holds:", t3.affine_consistent()[0])
print("Corollary 1 interval for M3:", t3.corollary1_interval())
F.fig_normalizations(UN); plt.show()
F.fig_consistency(actions); plt.show()
"""),
    md("""
## 3. Non-compensatory aggregation (Section 6)

Move the sliders: number of threat-intelligence sources (the knockout metric M1 of UN.S1.A1),
power γ and cap ϑ. Watch the **jump** of the hard gate between 0 and 1 source, the loss of
**idempotency** of power discounting, and the capped operator that keeps all three properties
(Corollary 2).
"""),
    code("""
def knockout_demo(sources=1, method="linear", gamma=1.0, theta=0.5):
    m = UN.vector(method); w = UN.w()
    m[0] = float(UN.metrics[0].table.normalize(sources, method))
    vals = {"additive S_w": agg.additive(m, w), "hard gate μ^Φ": agg.hard_gate(m, w, UN.core),
            f"power γ={gamma}": agg.power(m, w, UN.core, gamma),
            f"capped ϑ={theta}": agg.capped(m, w, UN.core, theta)}
    df = pd.DataFrame({"score": vals}).assign(level=lambda d: [crtm.level_name(v) for v in d.score])
    display(Markdown(f"**{sources} source(s)** → normalized m₁ = {m[0]:.3f} ({method})"))
    display(df)

if HAVE_WIDGETS:
    W.interact(knockout_demo, sources=W.IntSlider(1, 0, 4), method=["linear", "anchored"],
               gamma=W.FloatSlider(value=1.0, min=0.1, max=3, step=0.1),
               theta=W.FloatSlider(value=0.5, min=0.05, max=1, step=0.05))
else:
    for s in (0, 1, 4): knockout_demo(s)
"""),
    code("""
w, K = UN.w(), UN.core
props = {name: {"idempotent": agg.is_idempotent(f, 6), "veto at M1": agg.has_veto(f, 6, 0),
                 "jump at m1=0": round(agg.max_jump_at(f, UN.vector("linear"), 0), 4)}
         for name, f in {"additive": lambda m: agg.additive(m, w), "hard gate": lambda m: agg.hard_gate(m, w, K),
                         "power γ=1": lambda m: agg.power(m, w, K, 1), "capped ϑ=0.5": lambda m: agg.capped(m, w, K, .5)}.items()}
display(pd.DataFrame(props).T)   # cf. Table 4
F.fig_operators(UN); plt.show()
"""),
    md("## 4. Worked example: threat-intelligence action UN.S1.A1 (Table 5)"),
    code("""
w = UN.w(); lin, anc = UN.vector("linear"), UN.vector("anchored")
t5 = pd.DataFrame({"metric": [m.name for m in UN.metrics], "value": [m.value for m in UN.metrics],
                   "n_ch": lin, "lvl": [crtm.level_abbr(v) for v in lin], "ν_ξ": anc,
                   "lvl ": [crtm.level_abbr(v) for v in anc], "w": w, "w·n": w*lin, "w·ν": w*anc})
display(t5)
for name, a, b in (("gated, specified w", agg.hard_gate(lin, w, K), agg.hard_gate(anc, w, K)),
                   ("equal weights", agg.additive(lin, np.ones(6)/6), agg.additive(anc, np.ones(6)/6))):
    print(f"{name:20s} linear {a:.4f} ({crtm.level_abbr(a)})   anchored {b:.4f} ({crtm.level_abbr(b)})")
F.fig_contributions(UN); plt.show()
"""),
    md("""
## 5. Sensitivity to response times (Section 7.4)

The linear verdict *high* holds only by a margin of 0.0035. Drag τ₃ (relevance) and τ₄
(dissemination) to see where each normalization changes level.
"""),
    code("""
def times_demo(tau3=25.0, tau4=45.0):
    for meth in ("linear", "anchored"):
        s = sens.score_with(UN, {2: tau3, 3: tau4}, meth)
        print(f"{meth:9s} score {s:.4f}  →  {crtm.level_name(s)}")

print("thresholds for 'high':",
      "linear τ4 =", round(sens.threshold(UN, 3, .9, "linear", 45, 120), 1), "min;",
      "linear τ3 =", round(sens.threshold(UN, 2, .9, "linear", 25, 90), 1), "min;",
      "anchored τ3 (τ4=45) =", round(sens.threshold(UN, 2, .9, "anchored", 1e-6, 24.99), 1), "min")
if HAVE_WIDGETS:
    W.interact(times_demo, tau3=W.FloatSlider(value=25, min=0, max=200, step=0.5),
               tau4=W.FloatSlider(value=45, min=0, max=260, step=0.5))
else:
    times_demo()
F.fig_sensitivity(UN); plt.show()
"""),
    md("""
## 6. Uncertainty in the weights (Section 7.5, Proposition 7)

w ~ Dirichlet(α·1). The exact mean is the equal-weight score and Var = s²/(qα+1).
Monte Carlo uses the article's seed 20261027 and 200 000 samples.
"""),
    code("""
rows = []
for meth in ("linear", "anchored"):
    for a in (1, 4):
        s = unc.summary(UN.vector(meth), a)
        rows.append({"normalization": meth, "α": a, **{k: v for k, v in s.items() if k not in ("alpha", "levels")}})
display(pd.DataFrame(rows))
F.fig_dirichlet(UN); plt.show()
"""),
    md("## 7. Scenario profile and missing metrics (Section 7.6, Table 6)"),
    code("""
res = {m: crtm.evaluate_scenario(actions, method=m) for m in ("linear", "anchored")}
t6 = pd.DataFrame([{ "action": b, "goal": actions[b].goal, "q": actions[b].q, "κ": res["anchored"]["actions"][b].kappa,
                     "linear": r.score, "lvl": crtm.level_abbr(r.score), "lin. enclosure": (round(r.lower, 3), round(r.upper, 3)),
                     "anchored": res["anchored"]["actions"][b].score,
                     "lvl ": crtm.level_abbr(res["anchored"]["actions"][b].score),
                     "anc. enclosure": (round(res["anchored"]["actions"][b].lower, 3), round(res["anchored"]["actions"][b].upper, 3)),
                     "inconsistent (lin.)": len(r.inconsistent)} for b, r in res["linear"]["actions"].items()])
display(t6)
display(pd.DataFrame({m: {g: f"{v['mean']:.3f} / {v['min']:.3f}" for g, v in res[m]["profile"].items()} for m in res})
        .rename_axis("goal: mean / min"))
print("linear profile dominates anchored profile:", crtm.dominates(res["linear"]["profile"], res["anchored"]["profile"]))
F.fig_profile(actions); plt.show()
"""),
    md("""
## 8. Full reproduction check

Runs `scripts/reproduce.py`: compares the computed values with **107 values printed in the article**,
writes `results/results.json`, the tables (CSV) and all figures (PNG/SVG/PDF).
Set `FAST = True` for 20 000 instead of 200 000 Monte Carlo samples.
"""),
    code("""
FAST = False
import runpy, sys as _s
_s.argv = ["reproduce.py", "--out", str(ROOT / "results")] + (["--fast"] if FAST else [])
try:
    runpy.run_path(str(ROOT / "scripts" / "reproduce.py"), run_name="__main__")
except SystemExit as e:
    print("exit status:", e.code)
chk = pd.read_csv(ROOT / "results" / "checks.csv")
print(f"{chk.ok.sum()} / {len(chk)} published values reproduced")
display(chk[~chk.ok] if (~chk.ok).any() else Markdown("**All published values reproduced.**"))
"""),
    code("""
# optional: download the results as a zip (Colab only)
import shutil
zip_path = shutil.make_archive(str(ROOT / "crtm_results"), "zip", ROOT / "results")
try:
    from google.colab import files
    files.download(zip_path)
except ImportError:
    print("results archived at", zip_path)
"""),
    md("""
## 9. Sandbox: score your own metric

Enter a class table in the printed order critical / below average / average / above average / high
(ξ₀ … ξ₅, see Section 5.1 for the encoding rule) and a measured value.
"""),
    code("""
def my_metric(xi0=180., xi1=179., xi2=90., xi3=30., xi4=10., xi5=0., value=25.):
    try:
        t = crtm.ClassTable((xi0, xi1, xi2, xi3, xi4, xi5))
    except crtm.ClassTableError as e:
        print("invalid class table:", e); return
    lt, ln, an = t.tabulated_level(value), t.linear(value), t.anchored(value)
    print(f"polarity σ = {t.sigma:+d}; tabulated level: {crtm.LEVEL_NAMES[lt-1]}")
    print(f"linear   n_ch = {ln:.4f} → {crtm.level_name(ln)}{'   ✗ inconsistent' if crtm.level(ln) != lt else ''}")
    print(f"anchored ν_ξ  = {an:.4f} → {crtm.level_name(an)}")
    print("Corollary 1 interval (class 4 → 'high' under n_ch):", t.corollary1_interval()["x_interval"])

if HAVE_WIDGETS:
    W.interact_manual(my_metric, **{k: W.FloatText(v) for k, v in
        dict(xi0=180., xi1=179., xi2=90., xi3=30., xi4=10., xi5=0., value=25.).items()})
else:
    my_metric()
"""),
    md("""
---
**License.** Code: MIT. Data and figures: CC BY 4.0. Please cite the article and the Zenodo record
(see `CITATION.cff`). Generated from the sources by `tools/build_notebook.py`.
"""),
]


def main():
    nb = nbf.v4.new_notebook()
    nb.cells = CELLS
    nb.metadata = {"kernelspec": {"display_name": "Python 3", "language": "python", "name": "python3"},
                   "language_info": {"name": "python"},
                   "colab": {"provenance": [], "toc_visible": True, "name": "CRTM_Colab.ipynb"}}
    out = ROOT / "notebooks" / "CRTM_Colab.ipynb"
    nbf.write(nb, out)
    print("wrote", out, f"({out.stat().st_size / 1024:.0f} KiB)")


if __name__ == "__main__":
    main()
