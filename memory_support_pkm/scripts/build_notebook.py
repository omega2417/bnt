"""Build notebooks/PGMem_Colab.ipynb: a self-contained Colab notebook that
embeds the pgmem package via %%writefile, so it runs without uploads."""
from pathlib import Path

import nbformat as nbf

ROOT = Path(__file__).resolve().parents[1]
MODULES = ["__init__", "model", "governance", "assistance", "recall", "metrics", "synth",
           "simulate", "stats", "schema", "plots", "interactive", "architecture", "neural", "pipeline"]

md = nbf.v4.new_markdown_cell
code = nbf.v4.new_code_cell

cells = [
    md("""# Provenance-governed agentic AI for personal knowledge and memory support
### Reference implementation · synthetic dataset · statistics · neural-network realisation

Executable companion to the manuscript *"Provenance-governed agentic AI for personal knowledge and memory support: a framework and rule-level demonstration"*.

**What this notebook does**

| § | Content | Paper |
|---|---|---|
| 1 | Generates a **synthetic** cohort of people with memory impairment (MCI, mild dementia, acquired brain injury) with full **metadata** (Frictionless Data Package) | §6.2 |
| 2 | Cohort statistics: ridgelines, cognitive landscape, metadata fingerprint | §6.2 |
| 3 | **Neural-network solution on real components** — system architecture and grounded-recall pipeline diagrams, bill of materials | §4, Fig. 1–2 |
| 4 | Paper scenarios (Olena, 72) on working code: Eqs. (1)–(5), invariants I1–I4 | §5 |
| 5 | Three conditions on identical histories — reminder app, single agent + RAG, proposed framework — with radar, Sankey, scoreboard, forest plot, animation | §6, Table 4 |
| 6 | Metadata × outcomes: raincloud, parallel coordinates, Kruskal–Wallis, Spearman, logistic regression | §6 |
| 7 | Recall by stratum: heatmap and sunburst (Table 3 counterexamples) | §5.2 |
| 8 | Release-rule calibration: risk–coverage curve, dev → held-out | §4.4 |
| 9 | **Live neural components**: mDeBERTa-XNLI entailment for ent(a, r), zero-shot intent, e5 dense retrieval, end-to-end neural recall | §4.4 |

> ⚠️ **All data are synthetic.** No record corresponds to a real person; distributions are design assumptions, not clinical estimates. Results show how the framework's rules behave and do **not** demonstrate benefit for people (paper §7.3).

*Runtime:* ≈2 min on CPU without §9; §9 downloads ≈1.3 GB of model weights — choose **Runtime → Change runtime type → T4 GPU** for speed (CPU also works).
"""),
    md("## 0. Environment"),
    code("""%pip -q install pandas numpy scipy matplotlib tabulate plotly
import os, sys
PROJECT = "pgmem_project"
os.makedirs(f"{PROJECT}/pgmem", exist_ok=True)
os.makedirs(f"{PROJECT}/data", exist_ok=True)
sys.path.insert(0, PROJECT)"""),
    md("""### 0.1 Package code `pgmem`

The next cells write the package modules into `pgmem_project/pgmem/`. They can be collapsed.
*Alternative:* upload `pgmem_project.zip` and unzip it (cell after the modules)."""),
]
for m in MODULES:
    src = (ROOT / "pgmem" / f"{m}.py").read_text(encoding="utf-8")
    cells.append(code(f"%%writefile pgmem_project/pgmem/{m}.py\n{src}"))

cells += [
    code("""# (Optional) use the zip bundle instead of the embedded code:
USE_ZIP = False
if USE_ZIP:
    from google.colab import files
    up = files.upload()                      # choose pgmem_project.zip
    import zipfile
    zipfile.ZipFile(next(iter(up))).extractall(".")
    PROJECT = "memory_support_pkm"; sys.path.insert(0, PROJECT)"""),
    code("""import importlib, json, warnings
import pgmem
importlib.reload(pgmem)
import numpy as np, pandas as pd, matplotlib.pyplot as plt
from IPython.display import display, Markdown, Image
from pgmem import pipeline, schema, stats, plots, simulate, architecture
from pgmem import interactive as ix
pd.set_option("display.width", 200, "display.max_columns", 40)
warnings.filterwarnings("ignore", category=FutureWarning)
REPORTS = f"{PROJECT}/reports"; os.makedirs(REPORTS, exist_ok=True)
print("pgmem", pgmem.__version__)"""),

    md("""## 1. Synthetic dataset and metadata

Parameters: number of participants, observation period (days) and seed for reproducibility."""),
    code("""N_PARTICIPANTS, DAYS, SEED = 240, 28, 2026
DATA = f"{PROJECT}/data"
tables = pipeline.generate_dataset(DATA, N_PARTICIPANTS, DAYS, SEED)
for k, df in tables.items():
    print(f"{k:18s} {df.shape}")"""),
    md("""### 1.1 Metadata (`datapackage.json`)

Every table is described by a schema: field type, description, range, allowed values. The same schema **validates** any dataset — including a real one collected after ethical approval."""),
    code("""desc = json.load(open(f"{DATA}/datapackage.json", encoding="utf-8"))
print(desc["title"]); print(desc["description"]); print("generator:", desc["generator"])
meta = pd.DataFrame([dict(table=r["name"], field=f["name"], type=f["type"], description=f["description"],
                          constraints=json.dumps(f.get("constraints", {}), ensure_ascii=False))
                     for r in desc["resources"] for f in r["schema"]["fields"]])
display(meta[meta.table == "participants"])
print("Validation problems:", schema.validate(DATA) or "none")"""),
    code("""t = pipeline.load_dataset(DATA)
cohort = t["participants"]
display(cohort.head())
display(t["records"].head())
display(t["questions"].sample(5, random_state=1)[["stratum", "requester", "text", "ideal"]])"""),

    md("""## 2. Statistics of people with memory impairment (metadata)

**Cohort fingerprint:** age ridgelines per diagnosis; the MoCA × PRMQ landscape with density contours (thick = 70 % of peak density); and a z-score heat-strip that shows at a glance how each diagnostic group departs from the cohort mean."""),
    code("""display(Markdown("### Cohort characteristics by diagnosis"))
display(stats.describe_cohort(cohort))
display(Markdown("### Severity by MoCA × diagnosis"))
display(stats.memory_impairment_profile(cohort))"""),
    code("""plots.cohort_overview(cohort); plt.show()
num = ["age", "moca", "prmq_prospective", "prmq_retrospective", "education_years", "digital_literacy", "months_since_diagnosis"]
display(Markdown("### Spearman correlations between metadata"))
display(cohort[num].corr(method="spearman").round(2).style.background_gradient(cmap="RdBu", vmin=-1, vmax=1))"""),
    code("""display(Markdown("### Age bands and living situation"))
display(pd.crosstab(cohort.age_band, cohort.diagnosis, margins=True))
display(cohort.groupby("diagnosis")[["lives_alone", "has_trusted_person", "sensors_connected", "uses_voice"]].mean().round(2))"""),

    md("""## 3. Neural-network solution on real components

The paper's Figure 1 names **logical roles**. The diagrams below bind every role to a concrete, openly available component so the design can be built, benchmarked and audited:

* **blue** — pretrained neural networks (ASR, LLM, encoders, NLI cross-encoder, TTS);
* **grey** — deterministic `pgmem` rules (Eqs. 2–5, evidence typing, gates);
* **amber** — governance: permission is checked at retrieval, at release and again at dispatch (I1).

The key design rule: *neural models propose, rule gates dispose* — a high entailment score can never override a failed permission, conflict, identity or freshness check."""),
    code("""architecture.system_architecture(REPORTS); plt.show()"""),
    code("""architecture.neural_recall_pipeline(REPORTS); plt.show()"""),
    code("""bom = pd.DataFrame([
    ("Speech in", "Silero VAD → Whisper large-v3-turbo", "neural", "1.8 M + 809 M", "MIT", "device / server"),
    ("Speech out", "Piper TTS (uk_UA, en_GB) / Coqui XTTS-v2", "neural", "≈20 M / 467 M", "MIT / CPML", "device"),
    ("Interaction role", "Llama-3.1-8B-Instruct, Q4_K_M (llama.cpp / vLLM)", "neural", "8 B", "Llama 3.1 community", "local server"),
    ("Memory role: encoder", "BGE-M3 (prod.) / multilingual-e5-small (this notebook)", "neural", "568 M / 118 M", "MIT", "server"),
    ("Memory role: reranker", "BGE-reranker-v2-m3 cross-encoder", "neural", "568 M", "Apache-2.0", "server"),
    ("Verification: ent(a, r)", "mDeBERTa-v3-base-xnli-multilingual-nli-2mil7", "neural", "278 M", "MIT", "server"),
    ("Claim decomposition", "LLM with JSON-schema constrained decoding", "neural", "(shared 8 B)", "—", "server"),
    ("Assistance (Eqs. 2–3)", "pgmem.assistance", "rule", "—", "this work", "server"),
    ("Release rule (Eq. 5)", "pgmem.recall.release, θ calibrated (§8)", "rule", "—", "this work", "server"),
    ("Policy engine (I1)", "Open Policy Agent (Rego) ⇄ pgmem.PolicyEngine", "governance", "—", "Apache-2.0", "server"),
    ("Event base (Eq. 1)", "PostgreSQL 16 + pgvector, PROV-O lineage", "storage", "—", "PostgreSQL", "server"),
    ("Connectors", "CalDAV, Android CallLog, Health Connect / HealthKit, BLE pill box via MQTT", "storage", "—", "various", "device"),
], columns=["role", "component", "type", "parameters", "licence", "runs on"])
display(bom)"""),

    md("""## 4. Paper scenarios on working code

Personal event base (Eq. 1), access policy, grounded recall (Eqs. 4–5)."""),
    code("""from datetime import datetime, timedelta
from pgmem import PersonalEventBase, PolicyEngine, GroundedRecall, Record, EvidenceStatus as ES, Question
from pgmem import ActionQueue, QueuedAction, next_level, gate

T = datetime(2026, 10, 2, 10)
base, pol = PersonalEventBase("olena"), PolicyEngine("olena")
gr = GroundedRecall(base, pol)
def add(subject, value, status, kind, cat, kappa=0.9, source="calendar", content=None):
    return base.add(Record(base.new_id(), "olena", subject, content or value, T, source, kappa, frozenset({"self"}),
                           status=status, category=cat, kind=kind, value=value))
def ask(subject, kind, cat, who="olena"):
    a = gr.answer(Question("q", "olena", who, subject, kind, cat))
    print(f"[{a.decision}] {a.text}")
    return a

print("Past appointment (only a plan exists):")
add("appt:Kovalenko", "2026-10-02", ES.PLAN, "scheduled", "appointments", 0.95, content="Appointment with Dr Kovalenko")
ask("appt:Kovalenko", "occurred", "appointments")
print("\\nMedication (self-report at 08:47):")
add("med:2026-10-23", "true", ES.SELF_REPORT, "occurred", "medication", 0.85, "user_touch", "Morning medication taken")
ask("med:2026-10-23", "occurred", "medication")
print("\\nAndrii's call (call log not connected):")
ask("call:Andrii:2026-10-22", "occurred", "social")
print("\\nDisputed record (electricity bill):")
r1 = add("bill", "true", ES.SELF_REPORT, "occurred", "finance", 0.8, "user_voice", "Electricity bill paid")
r2 = add("bill", "false", ES.OBSERVATION, "occurred", "finance", 0.99, "carer_entry", "Bill not paid (carer entry)")
base.mark_disputed([r1.record_id, r2.record_id], "olena", T)
ask("bill", "occurred", "finance")
print("\\nPersonal note, daughter asks without permission:")
add("note:1", "Wi-Fi password is on the fridge", ES.SELF_REPORT, "content", "personal_note", source="user_voice")
ask("note:1", "content", "personal_note", who="iryna");"""),
    code("""print("I1: consent withdrawn after a message was queued")
pol.grant("iryna", "medication", "message")
q = ActionQueue(pol)
q.enqueue(QueuedAction("msg-1", "message", "iryna", "medication", "Morning medication missed", T))
pol.revoke("iryna", "medication", "message")
print("sent:", q.dispatch(T + timedelta(minutes=5)), "| cancelled:", [a.key for a in q.cancelled])

print("\\nI4: correcting a record invalidates the cached answer")
r = add("appt:dentist", "2026-10-10", ES.PLAN, "scheduled", "appointments", content="Dentist")
ask("appt:dentist", "scheduled", "appointments")
base.correct(r.record_id, "olena", T, value="2026-10-14", content="Dentist (rescheduled)")
ask("appt:dentist", "scheduled", "appointments")

print("\\nEquation (2): escalation L1→L2 only when G_k = 1")
for postponed, progress in [(False, True), (True, True), (False, False)]:
    g = gate(True, postponed, False, progress)
    print(f"  postponed={postponed}, progress_check={progress}: G={g}, L→{next_level(1, g, 4)}")

print("\\nAudit trail:"); display(pd.DataFrame([vars(e) for e in base.audit]).tail(6))"""),

    md("""## 5. Comparative simulation of three conditions

The same synthetic people and days (common random numbers) for: **reminder app** (fixed L1, silence = missed), **single agent + RAG** (escalates on timeout, no dispatch-time consent check, no evidence types) and the **proposed framework**."""),
    code("""%%time
ep, rc = pipeline.run_simulation(t, f"{PROJECT}/results", SEED)
out = pipeline.analyse(t, ep, rc, f"{PROJECT}/results", REPORTS, n_boot=300)
display(Markdown("### Pooled indicators (estimate and 95% cluster-bootstrap CI)"))
display(out["by_condition"].round(3))"""),
    md("""**How to read:**
* **TSR** = N_c/N_s — share of completed tasks; **FPR** (FAR in the paper) = N_f/N_p — share of unnecessary prompts (task already done, or after postponement/decline).
* **independence** — share of completions at L0–L1. For the reminder app it is trivially 1.0 because no other levels exist.
* **invented_outcome_rate** — episodes where silence was turned into "missed" (violates I3).
* **F_ext** = N_e/N_r — share of released claims supported by the reference history; **coverage** = N_a/N_q. F_ext is undefined (NaN) when no claims are released.
* The baseline agent's higher TSR is achieved by escalating despite postponement and by contacts without valid consent — under proposition P3 this is **not** success.

### 5.1 Radar profile — every axis oriented so that the outer ring is better
Bands are 95 % cluster-bootstrap intervals; × marks an undefined indicator. The interactive version shows raw values on hover."""),
    code("""plots.condition_radar(out["by_condition"]); plt.show()
ix.condition_radar(out["by_condition"]).show()"""),
    code("""plots.condition_dots(out["by_condition"], ["TSR", "FPR", "independence", "invented_outcome_rate"]); plt.show()
plots.condition_dots(out["by_condition"], ["F_ext", "coverage", "fabricated_per_100", "appropriate_behaviour"]); plt.show()"""),
    md("""### 5.2 Where does silence become a fabricated outcome? (interactive Sankey)
Condition → true outcome → recorded state. **Red ribbons** are tasks that were in fact completed but recorded as missed — a direct violation of I3. In the proposed framework these flows end in *unknown*, *postponed* or *declined* instead."""),
    code("""ix.episode_sankey(ep).show()"""),
    md("""### 5.3 Invariant scoreboard and paired differences"""),
    code("""plots.invariant_scoreboard(ep, rc); plt.show()
plots.paired_forest(out["paired"]); plt.show()
display(Markdown("### Safety and invariants")); display(out["safety"])
display(Markdown("### Paired differences per participant")); display(out["paired"].round(4))"""),
    md("""### 5.4 Assistance levels and adaptation (Eqs. 2–3)
Diverging bars put *independent* completions (L0–L1) to the right and *more help* (L2–L4) to the left. The adaptation panel shows the starting level falling over the 28 days for routine tasks — with the user's agreement only — while the safety-critical medication task never adapts."""),
    code("""plots.level_distribution(ep); plt.show()
plots.adaptation_over_time(ep); plt.show()"""),
    md("""### 5.5 Week-by-week animation
Each bubble is one synthetic participant: x = MoCA, y = cumulative task success, size = escalations so far. Press ▶ to watch the conditions separate."""),
    code("""ix.weekly_trajectories(ep, cohort).show()"""),

    md("## 6. Metadata × outcomes: who benefits least?"),
    code("""display(out["by_condition_diagnosis"][["diagnosis", "condition", "TSR", "FPR", "independence", "F_ext", "coverage"]].round(3))
plots.tsr_raincloud(out["participant_metrics"], cohort); plt.show()"""),
    md("""**Parallel coordinates** — every line is one person, coloured by TSR under the proposed framework. *Drag along any axis* to brush a subgroup (e.g. MoCA ≤ 17 or digital literacy = 1) and see where their outcomes land."""),
    code("""ix.cohort_parallel(cohort, out["participant_metrics"]).show()"""),
    code("""display(Markdown("### Statistical tests (proposed framework)")); display(out["group_tests"].round(4))
display(Markdown("### Logistic regression of episode completion (OR, 95% CI)")); display(out["logit"].round(3))
pm = out["participant_metrics"].merge(cohort, on="participant_id")
p = pm[pm.condition == "proposed"]
p = p.assign(moca_band=pd.cut(p.moca, [0, 17, 21, 25, 30], labels=["≤17", "18–21", "22–25", "26–30"]))
display(p.groupby("moca_band", observed=True)[["TSR", "independence", "FPR", "coverage"]].agg(["mean", "count"]).round(3))"""),

    md("""## 7. Recall by stratum (Table 3 counterexamples)
The heatmap colour is the share of reference behaviour; the second line in each cell lists the invariant violations that a plain accuracy score would hide (e.g. the baseline is "100 % appropriate" on attendance questions while overstating 720 plans as attendance)."""),
    code("""plots.recall_heatmap(out["strata"]); plt.show()
ix.recall_sunburst(rc).show()"""),
    code("""display(out["strata"].round(3))
display(Markdown("### Example answers"))
display(rc[rc.stratum.isin(["attendance", "unanswerable", "contradictory", "consent_restricted"])]
        .groupby(["stratum", "condition"]).head(1)[["stratum", "condition", "decision", "answer_text"]])"""),

    md("""## 8. Calibrating the release rule (Eq. 5)
The paper requires θ_low and θ_high to be *calibrated on development data and tested on held-out cases*. The risk–coverage curve shows what each θ_low trades: lower thresholds answer more questions (coverage C) at the cost of faithfulness (F_ext). Participants are split 50/50; the lowest θ_low reaching F_ext ≥ 0.99 on the development half is reported on the held-out half (★)."""),
    code("""from pgmem.recall import THETA_LOW, THETA_HIGH
cal = out["calibration"]
print(f"calibrated θ_low = {cal['theta_low']:.2f}")
display(pd.DataFrame({"development": cal["dev"], "held-out": cal["test"]}).T.round(4))
plots.risk_coverage(out["risk_coverage"], THETA_LOW, THETA_HIGH, calibrated=cal); plt.show()
ix.risk_coverage(out["risk_coverage"], THETA_LOW).show()"""),

    md("""## 9. Live neural components

This section runs real pretrained networks in place of the simulation's noisy scorer:

| Step | Model | Role in the paper |
|---|---|---|
| NLI entailment | `MoritzLaurer/mDeBERTa-v3-base-xnli-multilingual-nli-2mil7` (278 M, 100+ languages incl. Ukrainian) | ent(a_j, r) in Eq. (4) |
| Zero-shot intent | same NLI model | which claim kind the question asks for |
| Dense retrieval | `intfloat/multilingual-e5-small` (118 M, 384-d) | Memory role, R(q) |

If the weights cannot be downloaded (no internet), each component falls back to a transparent lexical scorer and says so — the notebook still runs end to end. Evidence typing (I2), permission (I1), identity and conflict gates remain deterministic either way."""),
    code("""RUN_NEURAL = True          # set False to skip downloads
%pip -q install transformers sentence-transformers sentencepiece
from pgmem import neural
nli = neural.NLIScorer(use_model=RUN_NEURAL)
emb = neural.DenseRetriever(use_model=RUN_NEURAL)
print("NLI backend:      ", nli.backend)
print("Embedding backend:", emb.backend)"""),
    md("""### 9.1 Why a plan does not entail attendance
Rows are records (premises) written the way the event base types them; columns are claims an assistant might make. A well-behaved NLI model gives a high score where the record really supports the claim and a low score for *"attended"* given only a calendar entry — the gap that I2 hard-codes."""),
    code("""premises = [
    "The calendar lists: Appointment with Dr Kovalenko, planned for 02 October 2026 at 10:00.",
    "The person reported on 23 October 2026 at 08:47: Morning medication taken.",
    "The source 'call_log' observed on 22 October 2026 at 19:00: Incoming call: Oleh.",
    "The person reported on 20 October 2026 at 20:00: Wi-Fi password is on the fridge.",
]
hypotheses = [
    "The appointment with Dr Kovalenko was planned for 02 October 2026.",
    "Olena attended the appointment with Dr Kovalenko.",
    "The person reported taking the morning medication.",
    "A sensor confirmed the medication was taken.",
    "Oleh called.",
    "Andrii called.",
    "The note says the Wi-Fi password is on the fridge.",
]
mat = nli.matrix(premises, hypotheses)
plots.entailment_heatmap(mat, f"P(entailment) — {nli.backend.split('/')[-1]}"); plt.show()"""),
    md("""### 9.2 End-to-end neural recall on Olena's event base
Free-text question → zero-shot intent → e5 retrieval over **permission-filtered** records → deterministic identity check (names and dates in the question must match the record) → `GroundedRecall` gates → NLI support score → release rule."""),
    code("""from pgmem.neural import NeuralRecall, IntentClassifier, neural_sup
T2 = datetime(2026, 10, 22, 19)
ob, op = PersonalEventBase("olena"), PolicyEngine("olena")
op.grant("trusted:olena", "medication", "read")
def put(subject, content, value, status, kind, cat, kappa=0.9, source="calendar", when=T):
    ob.add(Record(ob.new_id(), "olena", subject, content, when, source, kappa, frozenset({"self"}),
                  status=status, category=cat, kind=kind, value=value))
put("appt:Kovalenko:2026-10-02", "Appointment with Dr Kovalenko", "2026-10-02", ES.PLAN, "scheduled", "appointments", 0.95)
put("med:morning:2026-10-23", "Morning medication taken", "true", ES.SELF_REPORT, "occurred", "medication", 0.85, "user_touch")
put("call:Oleh:2026-10-22", "Incoming call: Oleh", "true", ES.OBSERVATION, "occurred", "social", 0.98, "call_log", T2)
put("note:olena:0", "Wi-Fi password is on the fridge", "Wi-Fi password is on the fridge", ES.SELF_REPORT, "content", "personal_note", 0.9, "user_voice")

nr = NeuralRecall(GroundedRecall(ob, op, sup=neural_sup(nli)), emb, IntentClassifier(nli))
rows = []
for text, who in [("When is my appointment with Dr Kovalenko?", "olena"),
                  ("Did I actually go to the appointment with Dr Kovalenko?", "olena"),
                  ("Did I take my morning medication?", "olena"),
                  ("Did Oleh call me?", "olena"),
                  ("Did Andrii call me yesterday?", "olena"),
                  ("What does my note about the Wi-Fi say?", "olena"),
                  ("What does her note about the Wi-Fi say?", "trusted:olena")]:
    tr = nr.ask(text, "olena", requester=who)
    rows.append(dict(asked_by=who, question=text, intent=tr.intent,
                     top_hit=f"{tr.retrieved[0][0]} ({tr.retrieved[0][1]:.2f})" if tr.retrieved else "—",
                     decision=tr.answer.decision, S_min=None if tr.answer.s_min is None else round(tr.answer.s_min, 3),
                     answer=tr.answer.text))
display(pd.DataFrame(rows))"""),
    md("""### 9.3 Swapping the simulated scorer for the NLI network
The rule-level comparison of §5 used a *noisy reference scorer*. Here the proposed condition's ent(a, r) is computed by the NLI network for a subset of participants, and the release behaviour is compared on identical questions. Expect lower coverage if the network is conservative — that is the honest cost of real entailment, reported alongside F_ext as the paper requires."""),
    code("""N_NEURAL = 30   # participants (raise on GPU)
sub = cohort.head(N_NEURAL)
rc_noisy = simulate.simulate_recall(sub, t["records"], t["questions"], t["reference_history"], SEED + 20)
rc_nli = simulate.simulate_recall(sub, t["records"], t["questions"], t["reference_history"], SEED + 20,
                                  sup_factory=lambda rng: neural_sup(nli))
def summary(r, label):
    p = r[r.condition == "proposed"]
    rel = p.claims_released.sum()
    return dict(scorer=label, questions=len(p), coverage=p.substantive.mean(),
                F_ext=p.claims_supported.sum() / rel if rel else float("nan"),
                appropriate=p.appropriate.mean(), uncertain_answers=(p.decision == "answer_uncertain").mean(),
                overstated=int(p.overstated.sum()), consent_violations=int(p.consent_violation.sum()))
display(pd.DataFrame([summary(rc_noisy, "simulated noisy scorer"), summary(rc_nli, f"NLI: {nli.backend}")]).round(3))
fig, ax = plt.subplots(figsize=(8, 3))
for r, lbl, c in [(rc_noisy, "simulated", "#8a8984"), (rc_nli, "NLI network", "#2a78d6")]:
    s = r[(r.condition == "proposed") & r.s_min.notna()].s_min
    ax.hist(s, bins=30, range=(0, 1), alpha=0.6, color=c, label=lbl)
for th in (THETA_LOW, THETA_HIGH):
    ax.axvline(th, color="#0b0b0b", ls="--", lw=1)
ax.set(xlabel="support score S_min", ylabel="answers", title="Support-score distribution vs release thresholds")
ax.legend(); plt.show()"""),

    md("""## 10. Your own data

To analyse a real (ethically approved, pseudonymised) dataset: put CSVs with the same names and columns into a folder together with `datapackage.json`, run `schema.validate(...)`, then `pipeline.load_dataset` → `run_simulation`/`analyse`. The `ability_latent` column is needed only by the simulation."""),
    code("""# MY_DATA = "my_data"          # folder with participants.csv, episodes.csv, ... and datapackage.json
# print(schema.validate(MY_DATA))
# t2 = pipeline.load_dataset(MY_DATA)"""),
    md("## 11. Download results (CSV tables, PNG figures, interactive HTML)"),
    code("""import shutil
archive = shutil.make_archive("pgmem_results", "zip", PROJECT)
print(archive)
try:
    from google.colab import files; files.download(archive)
except ImportError:
    pass"""),
]

nb = nbf.v4.new_notebook(cells=cells, metadata={
    "kernelspec": {"name": "python3", "display_name": "Python 3"},
    "language_info": {"name": "python"},
    "colab": {"provenance": [], "toc_visible": True},
    "accelerator": "GPU",
})
out = ROOT / "notebooks" / "PGMem_Colab.ipynb"
nbf.write(nb, out)
print(out)
