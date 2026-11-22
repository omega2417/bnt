"""Build notebooks/EBAW_Colab.ipynb: a self-contained, Colab-oriented notebook that embeds the
complete ``ebaw`` package (written to disk with %%writefile), so that it runs from a single
file without the repository.  Run:  python tools/build_notebook.py"""
import os

import nbformat as nbf

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MODULES = ["__init__", "model", "sim", "warrant", "ledger", "gateway", "stats", "benchmark", "dataset", "demo"]

nb = nbf.v4.new_notebook()
C = []


def md(s):
    C.append(nbf.v4.new_markdown_cell(s.strip("\n")))


def code(s, hide=False):
    c = nbf.v4.new_code_cell(s.strip("\n"))
    if hide:
        c.metadata["cellView"] = "form"
        c.metadata["jupyter"] = {"source_hidden": True}
    C.append(c)


md(r"""
# Evidence-Bound Action Warrants (EBAW) for agentic security operations — self-contained notebook

**ebaw-soc 2.0.0** · simulation, reference gateway core and the **EBAW-SOC-Synth** dataset
*(Ukrainian: самодостатній notebook для Google Colab — симуляція, еталонне ядро шлюзу та синтетичний датасет)*

Companion of the article *D. Prokopovych-Tkachenko, "Evidence-Bound Action Warrants for Agentic Security Operations: A Deterministic Gateway Enforcing Evidence Freshness, Calibrated Confidence, and Response Deadlines", submitted to Inventions (MDPI), 2026.*

The notebook is **self-contained**: Section 0 writes the complete Python package to disk, so it runs on Google Colab (File → Upload notebook) or any Jupyter installation without the repository. It needs only `simpy` beyond the Colab default stack and runs end to end in about 1–2 minutes with the default settings.

| § | Content | Article |
|---|---|---|
| 0 | Setup and embedded package source | Suppl. S1 |
| 1 | Model: action classes, tiers, scenarios, calibration map | §3.3, §4.1–4.2, Tables 4–5 |
| 2 | Reference gateway core: warrants, quorum ledger, enforcement point, attacks | §3.1–3.6, Algorithm 1, Prop. 3 |
| 3 | One replication of the six admission policies | §4.3–4.4 |
| 4 | Main experiment: 8 scenarios × N replications × 6 policies, ranking | §5.1, §5.5, Table 5, Fig. 6 |
| 5 | Propositions 1 and 2: admissibility condition and check-to-act window | §3.6, §5.2, §5.6 |
| 6 | Lattice of the 32 contracts under combined stress | §5.3, Fig. 3 |
| 7 | EBAW-SOC-Synth dataset: generation, validation, schema | §6.1, Tables 7–8 |
| 8 | Benchmark tasks: calibration, thresholds, policies, sample sizes | §6.1, §6.3 |
| 9 | Your own scenario | — |
| 10 | Export | — |

> **All data are synthetic.** Latency distributions, drift, policy dynamics, calibration and the analyst model are stated assumptions of the article; ledger latencies are parameterized from published Avalanche figures. EBAW-SOC-Synth realizes the *proposed* cyber-range dataset schema with simulated data; it is not a measurement of a real SOC.
""")

md(r"""
## 0. Setup

`N_REP` controls the number of replications of Sections 4–6. With `N_REP = 30` the main tables reproduce the article exactly (seeds 42 + r); the run takes about 1–3 minutes. Reduce it for a quick look.
""")
code(r"""
#@title Settings and dependencies
N_REP = 30        #@param {type:"integer"}
N_REP_LATTICE = 10 #@param {type:"integer"}
import importlib, subprocess, sys, os
for pkg, pin in (("simpy", "simpy>=4.1"), ("cryptography", "cryptography")):
    if importlib.util.find_spec(pkg) is None:
        subprocess.run([sys.executable, "-m", "pip", "install", "-q", pin], check=True)
WORK = "ebaw_colab"                      # working directory (relative to the notebook)
os.makedirs(os.path.join(WORK, "ebaw"), exist_ok=True)
if os.path.abspath(WORK) not in sys.path:
    sys.path.insert(0, os.path.abspath(WORK))
IN_COLAB = "google.colab" in sys.modules
import numpy, scipy, pandas, matplotlib, simpy
print("python", sys.version.split()[0], "| numpy", numpy.__version__, "| scipy", scipy.__version__,
      "| pandas", pandas.__version__, "| matplotlib", matplotlib.__version__, "| simpy", simpy.__version__)
print("article environment: Python 3.13, SimPy 4.1.2, NumPy 2.5.3, SciPy 1.18.1, pandas 3.0.5 "
      "(other versions run, but results may differ in the last digits)")
""")

md(r"""
### 0.1 Embedded package source

The following cells write the `ebaw` package (identical to `ebaw/` in the Zenodo archive) into `./ebaw_colab/ebaw/`. They are collapsed on Colab; expand them to read the code.

| Module | Role |
|---|---|
| `model.py` | parameters, scenarios S0–S7, calibration map (Wilson lower bounds, monotone envelope) |
| `sim.py` | SimPy discrete-event model, six admission policies, revalidation, metrics |
| `warrant.py` | warrant claims (Table 3), Ed25519/HMAC signing, compact tokens, nonce store, Merkle root |
| `ledger.py` | permissioned ledger with masking Byzantine quorum reads (n ≥ 4f + 1) |
| `gateway.py` | deterministic gateway core (Algorithm 1) and enforcement point |
| `stats.py` | sample sizes (Eq. 22), rule of three, CIs, ECE, Friedman/Nemenyi |
| `dataset.py` | EBAW-SOC-Synth generator, loader and validator (Tables 7–8) |
| `benchmark.py` | benchmark tasks T1–T3 on the dataset |
| `demo.py` | a small deterministic world for the gateway walk-through |
""")
for m in MODULES:
    src = open(os.path.join(ROOT, "ebaw", f"{m}.py")).read()
    code(f"%%writefile {{WORK}}/ebaw/{m}.py\n{src}", hide=True)

code(r"""
import importlib, ebaw
importlib.reload(ebaw)
import numpy as np, pandas as pd, matplotlib.pyplot as plt
from ebaw import model, sim, gateway, ledger, warrant, stats, dataset, benchmark as B, demo
pd.set_option("display.width", 200); pd.set_option("display.max_columns", 30)
OI = dict(AD="#D55E00", CO="#E69F00", RO="#CC79A7", GN="#56B4E9", EB="#0072B2", ET="#009E73")
ORDER = ["AD", "CO", "RO", "GN", "EB", "ET"]
plt.rcParams.update({"figure.dpi": 110, "axes.spines.top": False, "axes.spines.right": False, "font.size": 11})
print("ebaw", ebaw.__version__, "| signature scheme:", warrant.Signer().alg)
""")

md(r"""
## 1. Model

Seven action classes with risk tiers, freshness bounds Φ, deadlines D and median execution times τ (Table 4); four risk tiers with AUTO/OBSERVE thresholds; eight scenarios (Table 5).
""")
code(r"""
acts = pd.DataFrame(model.ACTIONS).T
acts["theta_auto"] = acts.tier.map(lambda t: model.TIERS[t][0]); acts["theta_obs"] = acts.tier.map(lambda t: model.TIERS[t][1])
display(acts[["p", "tier", "theta_auto", "theta_obs", "Phi", "D", "tau", "drift"]])
display(pd.DataFrame([(k, v[0], v[1]) for k, v in model.SCENARIOS.items()], columns=["id", "scenario", "overrides of BASE"]))
""")
code(r"""
cal = model.Calibrator(model.BASE, 42)
s = np.linspace(0, 1, 501)
fig, ax = plt.subplots(figsize=(6.2, 4.2))
mid = 0.5 * (cal.edges[1:] + cal.edges[:-1])
ax.plot(mid, cal.phat, "o", color="#999999", ms=4, label="empirical precision per bin")
ax.step(s, cal(s), where="post", color=OI["EB"], lw=2, label="conservative map g(s), Eq. (4)")
for t, (ta, _) in model.TIERS.items():
    ax.axhline(ta, ls=":", lw=1, color="#666666"); ax.text(0.01, ta + 0.005, f"θ_auto {t}", fontsize=8, color="#444444")
ax.set_xlabel("detection score s"); ax.set_ylabel("P(malicious | s)"); ax.legend(loc="lower right", fontsize=9)
ax.set_title("Calibration map: 25 equal-mass bins, one-sided Wilson bounds (z = 1.645)"); plt.show()
""")

md(r"""
## 2. Reference gateway core

`ebaw.gateway` implements Algorithm 1 outside the simulator. It evaluates the predicates only from **authenticated inputs** — signed observations, quorum-read ledger state, the versioned policy store and its own clock — and **never from fields asserted by the proposer** (assumption A3). It issues signed, single-use, expiring warrants. Enforcement points execute only with a verifying, unexpired, unused warrant and a committed EXECUTE verdict (A2). Any error or missing input makes the affected predicate false (A4).

The walk-through follows Figure 1 and then tries every attack of the threat model.
""")
code(r"""
log = demo.walkthrough()
""")
code(r"""
# Anatomy of a warrant (claims of Table 3)
W = demo.World()
e = W.observe("ws-0042", t_obs=100.0, score=0.97)
d = W.gw.admit(W.propose("isolate_host", "ws-0042", [e.evidence_id], claimed=0.99, t=112.0), 112.0)
h, c, s_ = d.token.split(".")
import json
print("header:", json.loads(warrant.b64u_dec(h)))
print(json.dumps(json.loads(warrant.b64u_dec(c)), indent=1))
print("signature:", s_[:40], "...")
""")
code(r"""
# Masking Byzantine quorums: n = 4f + 1 validators, read quorum ceil((n + 2f + 1)/2), f + 1 identical reports
import itertools
rows = []
for n, f in ((5, 1), (9, 2), (13, 3)):
    for fault in ("crash", "withhold", "fabricate", "equivocate"):
        L = ledger.QuorumLedger(n=n, f=f)
        L.anchor("tx", "d" * 64, "ws-1", 0.0, [1 + 0.1 * i for i in range(n)])
        for i in range(f):
            L.behaviour[i] = ledger.Behaviour(fault)
        ok = forged = tot = 0
        for Q in itertools.combinations(range(n), L.q):
            tot += 1
            ok += L.quorum_read("tx", 10.0, Q)[0] == "final"
            forged += L.quorum_read("ghost", 10.0, Q, asset_hint="ws-1")[0] != "absent"
        rows.append(dict(n=n, f=f, quorum=L.q, fault=fault, quorums_tested=tot, committed_state_read=ok, fabricated_state_accepted=forged))
display(pd.DataFrame(rows))
""")

md(r"""
## 3. One replication of the six admission policies

AD — agent-direct; CO — confidence-only; RO — receipt-only; GN — gateway without revalidation; EB — full EBAW contract; ET — tier-scoped EBAW. All policies replay the **same** proposal stream (synchronized common random numbers).
""")
code(r"""
P = model.scenario_params("S7")
props = sim.generate(P, 42, cal)
res = {sim.SHORT[p.name]: sim.run(P, props, p) for p in sim.MAIN_POLICIES}
one = pd.DataFrame({k: sim.summarize(v, props) for k, v in res.items()}).T.loc[ORDER]
display(one[["n", "n_adv", "adv_exec", "UER", "CVR", "DMR", "ESC", "TTC_med", "J"]].round(2))
kinds = pd.Series([p.kind for p in props]).value_counts()
print("proposal kinds in this shift:", kinds.to_dict())
print("outcomes under EB:", pd.Series([r["outcome"] for r in res["EB"]]).value_counts().to_dict())
""")

md(r"""
Metrics (Section 4.4): **UER** unsafe executions per 1000 proposals; **CVR** contract-violation rate of autonomous executions (%); **DMR** deadline-miss rate of malicious incidents (%); **ESC** escalation rate (%); **TTC** time to containment (s); **J** = 10·U + 5·M + 1·E expected cost per proposal.
""")

md(r"""
## 4. Main experiment

8 scenarios × `N_REP` replications × 6 policies. With `N_REP = 30` the table equals Table 5 of the article.
""")
code(r"""
import time
t0 = time.time(); rows = []; win = []
for key in model.SCENARIOS:
    P = model.scenario_params(key)
    for rep in range(N_REP):
        props = sim.generate(P, 42 + rep, cal)
        for pol in sim.MAIN_POLICIES:
            R = sim.run(P, props, pol); code_ = sim.SHORT[pol.name]
            s = sim.summarize(R, props); s.update(scenario=key, rep=rep, policy=code_); rows.append(s)
            if code_ in ("GN", "EB"):
                win += [dict(scenario=key, policy=code_, window=r["window"], change_v=r["window_change_v"],
                             violation=r["violation"]) for r in R if r["executed"] and not r["manual"]]
main = pd.DataFrame(rows); win = pd.DataFrame(win)
print(f"{len(main)} runs in {time.time() - t0:.0f} s")
J = main.groupby(["scenario", "policy"]).J.mean().unstack()[ORDER]
ARTICLE_J = {"AD": [3.335, 3.335, 3.618, 3.463, 3.335, 4.345, 3.72, 4.174], "CO": [0.77, 0.773, 1.029, 0.915, 0.77, 1.873, 0.826, 1.421],
             "RO": [3.298, 3.195, 3.581, 3.425, 3.298, 3.93, 3.696, 3.889], "GN": [0.649, 0.779, 0.916, 0.795, 0.596, 0.551, 0.873, 1.008],
             "EB": [0.644, 0.78, 0.908, 0.702, 0.58, 0.547, 0.877, 0.963], "ET": [0.639, 0.709, 0.892, 0.697, 0.575, 0.542, 0.752, 0.826]}
ART = pd.DataFrame(ARTICLE_J, index=list(model.SCENARIOS))
display(J.round(3).style.highlight_min(axis=1, props="font-weight:bold"))
print("max |J - article| =", float((J.round(3) - ART).abs().max().max()), "(0 with N_REP = 30 and the pinned versions)")
""")
code(r"""
pool = main.groupby("policy").agg(n=("n", "sum"), unsafe=("unsafe", "sum"), viol=("viol", "sum"), n_auto=("n_auto", "sum"),
                                   miss=("miss", "sum"), n_mal=("n_mal", "sum"), esc=("esc", "sum"), adv=("adv_exec", "sum"),
                                   n_adv=("n_adv", "sum"), J=("J", "mean")).loc[ORDER]
pool["UER"] = 1000 * pool.unsafe / pool.n; pool["CVR"] = 100 * pool.viol / pool.n_auto
pool["DMR"] = 100 * pool.miss / pool.n_mal; pool["ESC"] = 100 * pool.esc / pool.n
pool["adversarial executed"] = pool.adv.astype(int).astype(str) + "/" + pool.n_adv.astype(int).astype(str)
display(pool[["UER", "CVR", "DMR", "ESC", "J", "adversarial executed", "n_auto"]].round(2))
fig, ax = plt.subplots(1, 2, figsize=(12, 4.2))
x = np.arange(len(J.index)); w = 0.13
for i, p in enumerate(ORDER):
    ax[0].bar(x + (i - 2.5) * w, J[p], w, color=OI[p], label=p, edgecolor="white", linewidth=0.8)
ax[0].set_xticks(x, J.index); ax[0].set_ylabel("expected cost J per proposal"); ax[0].legend(ncol=6, fontsize=8, frameon=False)
ax[0].set_title("Expected cost by scenario")
U = main.groupby(["scenario", "policy"]).UER.mean().unstack()[ORDER]
for p in ORDER:
    ax[1].plot(U.index, U[p], "o-", color=OI[p], label=p, lw=1.8, ms=5)
ax[1].set_yscale("log"); ax[1].set_ylabel("UER per 1000 proposals (log)"); ax[1].set_title("Unsafe executions by scenario")
plt.tight_layout(); plt.show()
""")
code(r"""
# Friedman / Nemenyi over replications (blocks = replications, metric averaged over scenarios), Section 5.5
for metric in ("J", "UER"):
    tab = main.groupby(["rep", "policy"])[metric].mean().unstack()[ORDER]
    if len(tab) >= 3:
        r = stats.friedman_nemenyi(tab)
        print(f"{metric}: chi2 = {r['chi2']:.1f}, p = {r['p']:.2e}, CD = {r['CD']:.2f}; mean ranks:",
              {k: round(v, 2) for k, v in r["ranks"].items()})
""")

md(r"""
## 5. Propositions 1 and 2

**Proposition 1** — a class is autonomously admissible when the end-to-end check latency Λ = a₀ + max(Δₐ, δₛ + L_c) + δ_q + δ_g + Δ_o + δ_r does not exceed B_α = min(Φ_α, D_α − τ_α). It is checked here by Monte Carlo (no queueing) against the simulator under the contract {P1, P3, P5}. **Corollary 1** (Cantelli): E[Λ] + σ_Λ·√((1−η)/η) ≤ B_α ⇒ Pr[Λ ≤ B_α] ≥ 1 − η.

**Proposition 2** — without revalidation an admitted action executes on a changed state with probability 1 − E[e^{−λW}]; with revalidation the exposure shrinks to the commit latency δ_c.
""")
code(r"""
import math
def analytic_admissibility(P, n=200000, seed=7, eta=0.05):
    rng = np.random.default_rng(seed)
    ing = P["ing_median"] * np.exp(P["ing_sigma"] * rng.standard_normal(n))
    ing = ing + (rng.random(n) < P["stale_p"]) * rng.uniform(P["stale_lo"], P["stale_hi"], n)
    agent = P["agent_median"] * np.exp(P["agent_sigma"] * rng.standard_normal(n))
    u = rng.random(n); lc = P["lc_median"] * np.exp(P["lc_sigma"] * rng.standard_normal(n))
    lc = np.where(u < P["lc_stall_p"], rng.uniform(P["lc_stall_lo"], P["lc_stall_hi"], n), lc)
    lc = np.where((u >= P["lc_stall_p"]) & (u < P["lc_stall_p"] + P["lc_delay_p"]), rng.uniform(P["lc_delay_lo"], P["lc_delay_hi"], n), lc)
    sg = P["lat_sigma"]
    dq, dg, dr = (P["dq_median"] * np.exp(sg * rng.standard_normal(n)), P["dg_median"] * np.exp(sg * rng.standard_normal(n)),
                  P["dg_median"] * np.exp(sg * rng.standard_normal(n)))
    prep = P["prep_median"] * np.exp(P["prep_sigma"] * rng.standard_normal(n))
    lam = ing + np.maximum(agent, P["ds"] + lc) + dq + dg + prep + dr
    k = math.sqrt((1 - eta) / eta); out = {}
    for a, A in model.ACTIONS.items():
        tau = A["tau"] * np.exp(model.TAU_SIGMA * rng.standard_normal(n)); tau_hat = A["tau"] * math.exp(1.2816 * model.TAU_SIGMA)
        B_ = min(A["Phi"], A["D"] - tau_hat)
        out[a] = dict(B=B_, cantelli_ok=lam.mean() + k * lam.std() <= B_, P_an=float(((lam <= A["Phi"]) & (lam + tau <= A["D"])).mean()))
    return out, lam.mean(), lam.std()

pol_t = sim.Policy("GW{FLD}", "GW", frozenset("FLD"), True)
rows = []
for key in ("S0", "S2"):
    P = model.scenario_params(key); ok = {a: [0, 0] for a in model.ACTION_NAMES}
    for rep in range(N_REP):
        props = sim.generate(P, 42 + rep, cal)
        for r in sim.run(P, props, pol_t):
            if r["kind"] == "gen":
                fail = ("F" in r["fails_all"]) or ("D" in r["fails_all"]) or r["lc_timeout"]
                ok[r["action"]][0] += int(not fail); ok[r["action"]][1] += 1
    an, m, sd = analytic_admissibility(P, 400000)
    print(f"{key}: E[Λ] = {m:.1f} s, σ_Λ = {sd:.1f} s")
    rows += [dict(scenario=key, action=a, B=an[a]["B"], cantelli_ok=an[a]["cantelli_ok"], P_analytic=an[a]["P_an"],
                  P_simulated=ok[a][0] / max(1, ok[a][1])) for a in model.ACTION_NAMES]
p1 = pd.DataFrame(rows); p1["diff_pp"] = 100 * (p1.P_simulated - p1.P_analytic)
display(p1.round(3))
""")
code(r"""
rows = []
for sc in ("S0", "S3", "S7"):
    lam = model.scenario_params(sc)["pol_rate_rel_per_h"] / 3600
    for p in ("GN", "EB"):
        d = win[(win.scenario == sc) & (win.policy == p)]
        rows.append(dict(scenario=sc, policy=p, n=len(d), W_median_s=d.window.median(), W_p95_s=np.percentile(d.window, 95),
                         P_change_simulated=d.change_v.mean(), P_change_Prop2=1 - np.mean(np.exp(-lam * d.window)),
                         violation_rate=d.violation.mean()))
display(pd.DataFrame(rows).round(5))
""")

md(r"""
## 6. Lattice of the 32 contracts (combined stress S7)

Every subset S ⊆ {F, C, L, V, D} with revalidation. Proposition 4 guarantees pointwise monotonicity for fixed decision instants. System-level metrics need not be monotone, because queueing and escalation depend on the contract.
""")
code(r"""
P = model.scenario_params("S7"); lat = []
for rep in range(N_REP_LATTICE):
    props = sim.generate(P, 42 + rep, cal)
    for pol in sim.lattice_policies():
        s = sim.summarize(sim.run(P, props, pol), props)
        s.update(rep=rep, subset="".join(x for x in model.PREDICATES if x in pol.S) or "∅", k=len(pol.S)); lat.append(s)
lat = pd.DataFrame(lat).groupby(["subset", "k"])[["UER", "CVR", "DMR", "ESC", "J"]].mean().reset_index()
display(lat.sort_values("J").head(8).round(3))
fig, ax = plt.subplots(figsize=(7, 4))
ax.scatter(lat.k + np.random.default_rng(0).uniform(-0.12, 0.12, len(lat)), lat.J, c=lat.UER, cmap="viridis_r", s=40)
for _, r in lat.nsmallest(4, "J").iterrows():
    ax.annotate(r.subset, (r.k, r.J), xytext=(6, 0), textcoords="offset points", fontsize=8)
ax.set_xlabel("number of predicates in the contract"); ax.set_ylabel("expected cost J"); ax.set_title("Contract lattice under S7 (colour: UER)")
plt.show()
""")

md(r"""
## 7. EBAW-SOC-Synth dataset

A synthetic reference realization of the dataset proposed in Section 6.1. It has the record schema of Table 7 and the scenario catalog and volumes of Table 8: 900 episodes, 6300 proposals, of which at least 600 are adversarial. It consists of eight linked tables (`episodes`, `observations`, `ledger_anchors`, `proposals`, `policy_snapshots`, `gateway_verdicts`, `executions`, `analyst_actions`) and a benchmark table `policy_outcomes` (proposal × policy). Observations carry SHA-256 digests and Ed25519 sensor signatures. Issued warrants are stored as signed tokens. The manifest holds per-file digests and a signed Merkle root. Splits are made at episode level and in time: 60/20/20 for fitting the calibration map, selecting thresholds and testing.

If the notebook runs inside the Zenodo archive, the shipped copy is used; otherwise it is regenerated in a few seconds. Generation is deterministic, so the Merkle root is identical in both cases.
""")
code(r"""
SHIPPED = [p for p in ("../data/ebaw-soc-synth-1.0.0", "data/ebaw-soc-synth-1.0.0") if os.path.exists(os.path.join(p, "manifest.json"))]
DS = os.path.join(WORK, "ebaw-soc-synth-1.0.0")
man = dataset.build(DS, progress=lambda s: None)
print("generated:", os.path.relpath(DS), "| merkle root", man["merkle_root"])
if SHIPPED:
    shipped = json.load(open(os.path.join(SHIPPED[0], "manifest.json")))["merkle_root"]
    print("shipped copy:", SHIPPED[0], "| identical:", shipped == man["merkle_root"])
errs = dataset.validate(DS)
D = dataset.load(DS)
display(pd.DataFrame([(k, v["rows"], v["bytes"] // 1024, v["sha256"][:16]) for k, v in man["files"].items()],
                     columns=["file", "rows", "KiB", "sha256 (prefix)"]))
""")
code(r"""
E, Pp = D["episodes"], D["proposals"]
cat = pd.DataFrame({k: dict(name=v["name"], techniques="; ".join(v["techniques"]), perturbation=v["perturbation"],
                            episodes=v["episodes"], proposals=v["proposals"]) for k, v in dataset.CATALOG.items()}).T
cat["adversarial"] = Pp[Pp.kind != "genuine"].groupby("scenario_id").size()
display(cat)
display(E.groupby(["split", "label"]).size().unstack(fill_value=0))
display(Pp.head(3)); display(D["gateway_verdicts"].drop(columns="warrant_token").head(3))
""")
code(r"""
# Field dictionary (Table 7) - also in datapackage.json (Frictionless Data) and DATASHEET.md
schema = pd.DataFrame([(t, c, ty, d) for t, cols in dataset.SCHEMA.items() for c, ty, d in cols], columns=["table", "field", "type", "description"])
display(schema[schema.table.isin(["observations", "gateway_verdicts"])])
""")
code(r"""
# Verify a stored warrant and a sensor signature with the published keys
keys = json.load(open(os.path.join(DS, "keys.json")))
gv = warrant.Verifier(keys["gateway"]["alg"], bytes.fromhex(keys["gateway"]["public_key"]), keys["gateway"]["kid"])
tok = D["gateway_verdicts"].query("warrant_token != ''").warrant_token.iloc[0]
print(warrant.decode(tok, gv))
o = D["observations"].iloc[0]
sv = warrant.Verifier(keys["sensors"][o.sensor]["alg"], bytes.fromhex(keys["sensors"][o.sensor]["public_key"]), o.sensor)
print("sensor signature valid:", sv.verify(bytes.fromhex(o.raw_digest), bytes.fromhex(o.sensor_signature)))
""")

md(r"""
## 8. Benchmark tasks

* **T1 Calibration** — fit the conservative map on the train split and evaluate it on held-out test episodes.
* **T2 Thresholds** — choose the AUTO threshold of each tier on the validation split with an offline cost proxy (c_U = 10 per benign autonomous execution, c_E = 1 per escalation).
* **T3 Admission policies** — test-split metrics of the six policies with 95% Wilson intervals; adversarial executions with exact zero-event upper bounds; the sample sizes of Section 6.3 (Eq. 22 and the rule of three).
""")
code(r"""
c1 = B.task_calibration(D)
print({k: v for k, v in c1.items() if k not in ("map", "_cal")})
s_te, y_te, _ = B.labeled_scores(D, "test")
fig, ax = plt.subplots(figsize=(5.5, 4.8)); edges = np.linspace(0, 1, 11)
ax.plot([0, 1], [0, 1], "--", color="#777777", lw=1)
for name, g, col in (("fitted on train", c1["_cal"], OI["EB"]), ("article map", cal, OI["CO"])):
    cf = g(s_te); idx = np.clip(np.digitize(cf, edges) - 1, 0, 9); ok = [b for b in range(10) if (idx == b).sum() >= 20]
    ax.plot([cf[idx == b].mean() for b in ok], [y_te[idx == b].mean() for b in ok], "o-", color=col, label=name)
ax.set_xlabel("g(s)"); ax.set_ylabel("observed share malicious"); ax.legend(); ax.set_title("T1 reliability (test split)"); plt.show()
display(B.task_thresholds(D, c1["_cal"]).round(3))
""")
code(r"""
t3 = B.task_policies(D, "test")
display(t3["table"].round(2))
display(t3["J_by_scenario"].round(3).style.highlight_min(axis=1, props="font-weight:bold"))
print("sample-size planning:", {k: (round(v, 4) if isinstance(v, float) else v) for k, v in t3["planning"].items()})
""")

md(r"""
## 9. Your own scenario

Change any parameter of `model.BASE` (see `model.py`), for example the confirmation-latency mixture, the policy-change rate or the analyst capacity, and compare the policies on paired streams.
""")
code(r"""
my = dict(model.BASE); my.update(lc_delay_p=0.5, lc_delay_lo=20.0, lc_delay_hi=90.0, pol_rate_rel_per_h=2.0, n_analyst=1)
rows = []
for rep in range(min(N_REP, 5)):
    props = sim.generate(my, 1000 + rep, cal)
    for pol in sim.MAIN_POLICIES:
        s = sim.summarize(sim.run(my, props, pol), props); s.update(policy=sim.SHORT[pol.name]); rows.append(s)
display(pd.DataFrame(rows).groupby("policy")[["UER", "CVR", "DMR", "ESC", "J"]].mean().loc[ORDER].round(3))
""")

md(r"""
## 10. Export

Saves the tables of this session and the generated dataset into `ebaw_results.zip`. On Colab the archive is offered for download.
""")
code(r"""
import shutil
OUT = os.path.join(WORK, "results"); os.makedirs(OUT, exist_ok=True)
main.to_csv(os.path.join(OUT, "main_runs.csv"), index=False); lat.to_csv(os.path.join(OUT, "lattice.csv"), index=False)
p1.to_csv(os.path.join(OUT, "prop1.csv"), index=False); t3["table"].to_csv(os.path.join(OUT, "dataset_policies_test.csv"))
shutil.copytree(DS, os.path.join(OUT, "ebaw-soc-synth-1.0.0"), dirs_exist_ok=True)
zp = shutil.make_archive("ebaw_results", "zip", OUT); print(os.path.relpath(zp), os.path.getsize(zp) // 1024, "KiB")
if IN_COLAB:
    from google.colab import files; files.download(zp)
""")
md(r"""
---
**License.** Code MIT; dataset CC BY 4.0. **Citation.** Please cite the software and dataset via `CITATION.cff` / Zenodo and the article once published.
""")

nb["cells"] = C
nb["metadata"] = {"kernelspec": {"name": "python3", "display_name": "Python 3"}, "language_info": {"name": "python"},
                  "colab": {"provenance": [], "toc_visible": True, "name": "EBAW_Colab.ipynb"}}
os.makedirs(os.path.join(ROOT, "notebooks"), exist_ok=True)
nbf.write(nb, os.path.join(ROOT, "notebooks", "EBAW_Colab.ipynb"))
print("written notebooks/EBAW_Colab.ipynb with", len(C), "cells")
