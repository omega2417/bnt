"""Builds notebooks/MetaTwin_Guard_Colab.ipynb with an embedded copy of the package."""
import base64
import gzip
import io
import sys
import tarfile
from pathlib import Path

import nbformat as nbf

ROOT = Path(__file__).resolve().parents[1]


def embedded_package() -> str:
    """Reproducible base64 tar.gz of the package and tests (fixed mtime/owner/mode)."""
    raw = io.BytesIO()
    with gzip.GzipFile(fileobj=raw, mode="wb", mtime=0) as gz:
        with tarfile.open(fileobj=gz, mode="w", format=tarfile.PAX_FORMAT) as tar:
            for sub in ("metatwin_guard", "tests"):
                for p in sorted((ROOT / sub).glob("*.py")):
                    data = p.read_bytes()
                    info = tarfile.TarInfo(f"{sub}/{p.name}")
                    info.size, info.mtime, info.mode = len(data), 0, 0o644
                    tar.addfile(info, io.BytesIO(data))
    return base64.b64encode(raw.getvalue()).decode()


md = nbf.v4.new_markdown_cell
code = nbf.v4.new_code_cell
cells = []

cells.append(md("""# MetaTwin-Guard — demonstrations, benchmark and conclusions (Google Colab)

Companion notebook to *An Explainable and Verifiable Digital Twin of a Two-Site Cyber Range for Metaverse
Infrastructure Assurance: Software Artifact and Field Protocol* (Korchenko, Prokopovych-Tkachenko, Davydenko,
Askerov, Herasymenko, Zhurov).

The notebook walks through every mechanism of the reference artifact and re-executes the deterministic synthetic
benchmark:

| § | Content | Article |
|---|---|---|
| 1 | Evidence levels and the confirmed two-site topology | §3.1–3.2, Fig. 1, Table 1 |
| 2 | Signed telemetry envelope (Ed25519, SHA-256) | §3.4, RFC 8032, FIPS 180-4 |
| 3 | Integrity gateway and the admission-before-state invariant | §3.5, Eqs. (1)–(2), Table 2 |
| 4 | Robust explainable detector, static rules, hybrid decision; decision traces | §3.6–3.7, §4.6, Eqs. (3)–(7) |
| 5 | Freshness / staleness of twin state | §3.5 |
| 6 | Quorum-signed evidence chain and its limits | §3.8, §4.7 |
| 7 | Deterministic benchmark: 6 scenarios × 8 runs, 17,280 events | §3.9, §4.2, Table 5, Fig. 4 |
| 8 | **Executed** layer ablation | Table 6 |
| 9 | Analytical and **executed** sensitivity | Table 7 |
| 10 | Timing and explanation outputs | §4.3 |
| 11 | Multi-seed robustness | Table 8 gate |
| 12 | Automated tests | §4.1, Table 4 |
| 13 | Conclusions | §4.5, §6 |

> **Evidence boundary.** All results here are *level B — deterministic synthetic software verification*. They are not
> cyber-range field evidence. The evidence ledger is a single-process emulation, not a distributed blockchain. The
> deterministic keys are test fixtures only.

**Run:** *Runtime → Run all*. A full run takes about 1–3 minutes on a standard Colab CPU runtime.
"""))

cells.append(md("## 0. Setup\n\nThe package needs only `cryptography` (pre-installed on Colab) and `matplotlib`. "
                "If a release zip (`MetaTwin-Guard-v*-zenodo.zip`, any browser-renamed variant) has been uploaded to `/content`, "
                "it is used; otherwise the copy of the package embedded in the next cell (identical to the release) is unpacked. "
                "The cell can be re-run safely and prints which copy was imported."))
cells.append(code("""%pip install -q "cryptography>=42.0.5" matplotlib"""))
cells.append(code(f'''import base64, glob, io, os, shutil, sys, tarfile, zipfile
from pathlib import Path

EMBEDDED = "{embedded_package()}"


def _extract_zip(zip_path, dest):
    shutil.rmtree(dest, ignore_errors=True)
    with zipfile.ZipFile(zip_path) as z:
        z.extractall(dest)
    hits = sorted(dest.rglob("metatwin_guard/__init__.py"), key=lambda p: len(p.parts))
    if not hits:
        raise FileNotFoundError(f"{{zip_path}} does not contain metatwin_guard/__init__.py")
    return hits[0].parent.parent  # directory that CONTAINS the package


def _extract_embedded(dest):
    shutil.rmtree(dest, ignore_errors=True)
    dest.mkdir(parents=True)
    with tarfile.open(fileobj=io.BytesIO(base64.b64decode(EMBEDDED)), mode="r:gz") as tar:
        tar.extractall(dest, **({{"filter": "data"}} if hasattr(tarfile, "data_filter") else {{}}))
    return dest


# Any uploaded release zip, also renamed by the browser ("... (1).zip") or prefixed.
zips = sorted({{*glob.glob("/content/*MetaTwin*Guard*.zip"), *glob.glob("*MetaTwin*Guard*.zip")}})
if Path("metatwin_guard/__init__.py").exists():
    work, source = Path("."), "current directory"
elif Path("../metatwin_guard/__init__.py").exists():
    work, source = Path(".."), "repository checkout (parent directory)"
elif zips:
    work, source = _extract_zip(zips[-1], Path("metatwin_guard_zip")), f"uploaded zip {{zips[-1]}}"
else:
    work, source = _extract_embedded(Path("metatwin_guard_src")), "embedded copy"
work = work.resolve()

# Re-running this cell must switch cleanly to the selected copy.
for name in [m for m in sys.modules if m == "metatwin_guard" or m.startswith("metatwin_guard.")]:
    del sys.modules[name]
sys.path[:] = [p for p in sys.path if not p.rstrip("/").endswith(("metatwin_guard_src", "metatwin_guard_zip"))]
if str(work) not in sys.path:
    sys.path.insert(0, str(work))
os.environ["PYTHONPATH"] = str(work)

import metatwin_guard as mtg, cryptography, platform
print("Source:", source)
print("metatwin_guard", mtg.__version__, "from", mtg.__file__)
print("cryptography", cryptography.__version__, "| Python", platform.python_version())'''))
cells.append(code("""import json, math, statistics, copy
from datetime import timedelta
import matplotlib.pyplot as plt
from IPython.display import display, Markdown

from metatwin_guard import config, topology, plots
from metatwin_guard import (MetaTwinGuard, SoftwareSensor, IntegrityGateway, QuorumEvidenceLedger,
                            RobustDetector, StaticRules, TwinState, deterministic_private_key, tamper_features)
from metatwin_guard.generator import START_TIME, normal_features
from metatwin_guard.detector import min_simultaneous_deviations
from metatwin_guard import benchmark as bm
import random

def md_table(rows, cols, fmt=None):
    fmt = fmt or {}
    out = ["| " + " | ".join(cols) + " |", "|" + "---|" * len(cols)]
    for r in rows:
        out.append("| " + " | ".join(fmt.get(c, str)(r[c]) if c in r else "" for c in cols) + " |")
    display(Markdown("\\n".join(out)))"""))

# 1
cells.append(md("""## 1. Evidence levels and confirmed topology

* **Level A — confirmed context:** documented components of the two-site range.
* **Level B — software verification:** this artifact, unit tests, deterministic generator (everything executed below).
* **Level C — planned field method:** the prospective protocol (Supplementary File S1); no measurement exists.

Nominal provider rates are not measured throughput; unknown inventory items are left unknown rather than invented."""))
cells.append(code("""print(json.dumps(topology.summary(), indent=2))
print("Not supplied:", ", ".join(topology.NOT_SUPPLIED))
plots.figure_topology(); plt.show()"""))

# 2
cells.append(md("""## 2. Signed telemetry envelope

A software sensor builds a canonical event (sorted-key JSON), hashes the feature payload with SHA-256 (FIPS 180-4),
links it to its previous event hash, and signs the envelope with Ed25519 (RFC 8032). `ingest_time_utc` is assigned on
receipt and is therefore outside the signature."""))
cells.append(code("""sensor = SoftwareSensor("sA-edge", "A", "A/edge-router", deterministic_private_key("sA-edge", config.MASTER_SEED))
rng = random.Random(1)
ev = sensor.emit(normal_features(rng, transients=False), START_TIME, 45.0, "demo", "baseline")
print(json.dumps({k: (v[:24] + "…" if isinstance(v, str) and len(v) > 40 else v) for k, v in ev.items()}, indent=2))"""))

# 3
cells.append(md("""## 3. Integrity gateway and admission-before-state invariant

$g(e_i)=C_{schema}\\wedge C_{hash}\\wedge C_{signature}\\wedge C_{id}\\wedge C_{sequence}\\wedge C_{chain}$ (Eq. 1) and
$T_i = U(T_{i-1}, e_i)$ if $g(e_i)=1$, otherwise $T_{i-1}$ (Eq. 2).

Below, a guard ingests a clean baseline and then receives one legitimate event and six manipulations. For each we show
the reasons, whether the twin state hash changed, and that an evidence block was still written."""))
cells.append(code("""sensors = {sid: SoftwareSensor(sid, site, node, deterministic_private_key(sid, config.MASTER_SEED))
           for sid, (site, node) in topology.SENSORS.items()}
guard = MetaTwinGuard({s: x.private_key.public_key() for s, x in sensors.items()})
rng = random.Random(7); t = START_TIME
history = []
for i in range(120):
    t += timedelta(seconds=1)
    e = sensors[rng.choice(list(sensors))].emit(normal_features(rng), t, 45.0, "demo", "baseline")
    history.append(e); guard.process(e)
guard.fit_baseline()

s = sensors["s-vpn"]
def nxt(feats=None, dt=1):
    global t; t += timedelta(seconds=dt)
    return s.emit(feats or normal_features(rng, transients=False), t, 45.0, "demo", "evaluation")

legit = nxt()
cases = [("legitimate event", legit)]
cases.append(("replay of an accepted event", copy.deepcopy(history[10])))
e2 = nxt(); cases.append(("modified after signing (hash not fixed)", tamper_features(e2, {"rtt_ms": 420.0}, False)))
cases.append(("modified after signing (hash recomputed)", tamper_features(e2, {"rtt_ms": 420.0}, True)))
cases.append(("original of the modified event", e2))
rogue = SoftwareSensor("s-rogue", "A", "A/vpn-path", deterministic_private_key("s-rogue", 99))
cases.append(("unregistered key", rogue.emit(normal_features(rng), t, 45.0, "demo", "evaluation")))
e3, e4 = nxt(), nxt()
cases.append(("out-of-order: later event first", e4))
cases.append(("…then the earlier one", e3))
broken = dict(nxt()); broken.pop("signature"); cases.append(("malformed (missing signature)", broken))
cases.append(("next legitimate event after a lost one", nxt()))

rows = []
for name, e in cases:
    before, nblocks = guard.twin.state_hash(), len(guard.ledger.blocks)
    r = guard.process(e)
    rows.append({"case": name, "admitted": r["admitted"], "reasons": ", ".join(r["reasons"]) or "—",
                 "state changed": guard.twin.state_hash() != before, "evidence block": len(guard.ledger.blocks) == nblocks + 1,
                 "hybrid alert": r["hybrid_alert"]})
md_table(rows, ["case", "admitted", "reasons", "state changed", "evidence block", "hybrid alert"])"""))
cells.append(md("""**Observation.** Only admitted events change the state; every rejected event leaves a signed evidence record with
its reasons. Rejection of an earlier event that arrives after a later one is by design: legitimate re-ordering needs a
bounded buffer at the collector (field deployment), and the later event itself is rejected because its previous-hash
does not continue the accepted chain.

**Limitation made visible.** The last row shows that once a legitimate event is lost (here: the malformed one), the
gateway rejects every later event of that source, because its previous-hash no longer matches. The reference artifact
deliberately does not re-synchronize a source chain; gap reporting and authenticated re-synchronization belong to the
field collector and are listed in the extended verification suite."""))

# 4
cells.append(md("""## 4. Robust explainable detector, rules and hybrid decision

$s_j=\\max(1.4826\\,MAD_j,0.25)$ (Eq. 3, Rousseeuw & Croux 1993), $z_j=\\min(20,|x_j-m_j|/s_j)$ (Eq. 4),
$A(x)=\\sqrt{\\tfrac1p\\sum z_j^2}$ (Eq. 5), alert if $A\\ge 3.20$, contributions $c_j=z_j/\\sum_k z_k$ (Eq. 6),
hybrid $d_H=d_R\\vee d_X\\vee\\neg g$ (Eq. 7).

First, the fitted baseline; then the three decision traces of §4.6, computed directly from the stated deviations."""))
cells.append(code("""det = guard.detector
md_table([{"feature": f, "median": det.median[f], "MAD": det.mad[f], "scale s_j": det.scale[f],
           "floor active": det.scale[f] == config.DISPERSION_FLOOR} for f in config.FEATURES],
         ["feature", "median", "MAD", "scale s_j", "floor active"],
         {c: (lambda v: f"{v:.3f}") for c in ("median", "MAD", "scale s_j")})

def trace(z):
    A = math.sqrt(sum(v*v for v in z.values()) / len(z)); tot = sum(z.values())
    top = sorted(((f, v/tot) for f, v in z.items()), key=lambda kv: -kv[1])[:3]
    return A, top
for name, z in [
    ("VPN path degradation", dict(rtt_ms=6.0, jitter_ms=5.2, loss_pct=4.4, throughput_mbps=2.0, auth_failures=0.3, vpn_status=0, power_status=0)),
    ("Replay (ordinary values)", dict(rtt_ms=0.6, jitter_ms=0.3, loss_pct=0.2, throughput_mbps=0.4, auth_failures=0.1, vpn_status=0, power_status=0)),
    ("Isolated power transition", dict(rtt_ms=0.8, jitter_ms=0.5, loss_pct=0.3, throughput_mbps=0.3, auth_failures=0.0, vpn_status=0, power_status=4.0)),
]:
    A, top = trace(z)
    print(f"{name:28s} A = {A:.2f}  flagged = {A >= config.SCORE_THRESHOLD}   top-3: " + ", ".join(f"{f} ({c:.2f})" for f, c in top))
print(f"\\nSingle continuous feature must reach z = 3.20·√7 = {3.2*math.sqrt(7):.2f}; isolated binary flip gives A = √(16/7) = {math.sqrt(16/7):.2f}")"""))
cells.append(code("""# The same on live events through the full pipeline
x = normal_features(rng, transients=False)
for label, mod in [("ordinary", {}), ("VPN degradation", {"rtt_ms": x["rtt_ms"] + 160, "jitter_ms": 70, "loss_pct": 8}),
                   ("power transition", {"power_status": 0.0})]:
    t += timedelta(seconds=1)
    r = guard.process(sensors["sB-edge"].emit({**x, **mod}, t, 45.0, "demo", "evaluation"))
    print(f"{label:18s} admitted={r['admitted']}  rules={r['rules_fired'] or '-'}  A={r['robust_score']:.2f}  "
          f"robust={r['robust_alert']}  hybrid={r['hybrid_alert']}  top3={[(f, round(c, 2)) for f, c in r['top_contributions']]}")"""))

# 5
cells.append(md("""## 5. Freshness of twin state

Missing telemetry never changes the state (Eq. 2), so the twin must expose age: node state is *current*
($\\Delta\\le\\tau_{fresh}$), *stale* or *unknown* ($\\Delta>\\tau_{lost}$). Bounds here are the artifact defaults
(30 s / 120 s); in the field they are preregistered."""))
cells.append(code("""for dt in (5, 60, 600):
    now = t + timedelta(seconds=dt)
    print(f"t_last + {dt:4d} s:", {n: guard.twin.freshness(n, now) for n in sorted(guard.twin.nodes)})"""))

# 6
cells.append(md("""## 6. Quorum-signed evidence chain

Each block binds the event hash, integrity result and reasons, anomaly score, decision, top contributions and the
twin-state hash; four validator keys sign the block hash and verification needs ≥ 3 valid signatures."""))
cells.append(code("""rep = guard.ledger.verify()
print("chain:", rep.n_blocks, "blocks, valid =", rep.valid)
print(json.dumps(guard.ledger.blocks[-3]["body"], indent=1)[:900], "…")

tests = {}
f = guard.ledger.tampered_copy(); f.blocks[50]["body"]["hybrid_alert"] = not f.blocks[50]["body"]["hybrid_alert"]
tests["flip a stored decision"] = f.verify()
f = guard.ledger.tampered_copy(); del f.blocks[40]
tests["delete a block"] = f.verify()
f = guard.ledger.tampered_copy(); f.blocks[30]["signatures"]["validator-1"] = "00"*64
tests["1 of 4 signatures invalid"] = f.verify()
f = guard.ledger.tampered_copy()
for v in ("validator-1", "validator-2"): f.blocks[30]["signatures"][v] = "00"*64
tests["2 of 4 signatures invalid"] = f.verify()
for k, rep in tests.items():
    print(f"{k:28s} valid={rep.valid}  {rep.errors[:1]}")"""))
cells.append(md("""**Limit made explicit.** All four keys live in one process: an adversary holding three keys (or the process)
can sign arbitrary blocks. The quorum fixes the evidence *format* and verification rule; it is not Byzantine fault
tolerance, and local append time is not blockchain confirmation time."""))

# 7
cells.append(md("""## 7. Deterministic synthetic benchmark (seed 20260823)

Six scenarios × eight runs; each run has 120 baseline and 240 evaluation events (40 injected, 200 normal):
48 runs, 17,280 events, 1,920 injected events. Three modes are scored on the same events."""))
cells.append(code("""import time
t0 = time.time()
results, rows = bm.run_benchmark(config.MASTER_SEED, config.REPETITIONS)
summary = bm.summarize(rows)
print(f"{len(rows)} runs, {sum(r['n_events'] for r in rows)} events, {sum(r['n_injected'] for r in rows)} injected, "
      f"all ledgers valid = {all(r['ledger_valid'] for r in rows)}, "
      f"state unchanged on every rejection = {all(r['state_unchanged_on_reject'] for r in rows)}  ({time.time()-t0:.0f} s)")
ms = lambda k: (lambda r: f"{r[k+'_mean']:.3f} ± {r[k+'_sd']:.3f}")
md_table([{**r, "Scenario": config.SCENARIO_LABELS[r["scenario"]], "Mode": bm.MODE_LABELS[r["mode"]],
           "Precision": ms("precision")(r), "Recall": ms("recall")(r), "F1": ms("f1")(r),
           "FP/1000": f"{r['fp_per_1000_normal_mean']:.1f} ± {r['fp_per_1000_normal_sd']:.1f}"} for r in summary],
         ["Scenario", "Mode", "Precision", "Recall", "F1", "FP/1000"])
plots.figure_f1(summary); plt.show()"""))
cells.append(md("""**Comparison with the article's Table 5 (mean F1).** The methods and constants are identical; the generator is an
independent implementation of the stated design, so values differ slightly while the pattern must agree."""))
cells.append(code("""ARTICLE_F1 = {"wan_failover": (0.913, 0.880, 0.880), "vpn_degradation": (0.911, 0.878, 0.878),
              "wifi_auth_surge": (0.813, 0.815, 0.815), "power_transition": (0.959, 0.071, 0.893),
              "telemetry_modification": (0.974, 0.931, 0.931), "replay": (0.000, 0.000, 0.879)}
S = {(r["scenario"], r["mode"]): r for r in summary}
FEATURE_MODES = ("rules", "robust", "hybrid")

def best_modes(values, tol=0.01):
    # modes within `tol` of the highest F1 (ties are reported together)
    top = max(values)
    return {bm.MODE_LABELS[m] for m, v in zip(FEATURE_MODES, values) if top - v <= tol}

cmp_rows = []
for sc, art in ARTICLE_F1.items():
    ours = [S[(sc, m)]["f1_mean"] for m in FEATURE_MODES]
    row = {"Scenario": config.SCENARIO_LABELS[sc]}
    for m, o, a in zip(FEATURE_MODES, ours, art):
        row[bm.MODE_LABELS[m]] = f"{o:.3f} (article {a:.3f})"
    row["best mode (±0.01) agrees"] = bool(best_modes(ours) & best_modes(art))
    cmp_rows.append(row)
md_table(cmp_rows, ["Scenario", "Rules", "Robust score", "Hybrid", "best mode (±0.01) agrees"])"""))

# 8
cells.append(md("""## 8. Layer ablation — executed

The article derives integrity-only ($d=\\neg g$) and rules + integrity ($d=d_R\\vee\\neg g$) analytically (Table 6) and
lists an executed ablation as an open gate. Here both configurations are executed on the same events."""))
cells.append(code("""abl = bm.summarize(rows, bm.MODES)
A = {(r["scenario"], r["mode"]): r["f1_mean"] for r in abl}
ARTICLE_T6 = {"wan_failover": (0.0, 0.913), "vpn_degradation": (0.0, 0.911), "wifi_auth_surge": (0.0, 0.813),
              "power_transition": (0.0, 0.959), "telemetry_modification": (1.0, 0.974), "replay": (1.0, 0.954)}
md_table([{"Scenario": config.SCENARIO_LABELS[sc], **{bm.MODE_LABELS[m]: f"{A[(sc, m)]:.3f}" for m in bm.MODES},
           "article derived (int-only / rules+int)": f"{ARTICLE_T6[sc][0]:.3f} / ≈{ARTICLE_T6[sc][1]:.3f}"}
          for sc in config.SCENARIOS],
         ["Scenario"] + [bm.MODE_LABELS[m] for m in bm.MODES] + ["article derived (int-only / rules+int)"])
plots.figure_f1(abl, modes=bm.MODES, name="ablation"); plt.show()"""))

# 9
cells.append(md("""## 9. Sensitivity of the robust score — analytical (Table 7) and executed

For a binary feature with constant baseline, $z=\\min(20,1/s_{min})$ and the minimum number of simultaneous equal
deviations to reach $\\tau$ is $k=\\lceil p\\tau^2/z^2\\rceil$ ($p=7$)."""))
cells.append(code("""tab = []
for fl in (0.10, 0.25, 0.50):
    z = min(20, 1/fl)
    row = {"floor": fl, "z": f"{z:.1f}", "isolated A": f"{math.sqrt(z*z/7):.2f}"}
    for th in (2.5, 3.2, 4.0):
        k = min_simultaneous_deviations(z, th); row[f"k at τ={th}"] = k if k else "not reachable"
    tab.append(row)
md_table(tab, ["floor", "z", "isolated A", "k at τ=2.5", "k at τ=3.2", "k at τ=4.0"])

sens = bm.sensitivity([r for r in results if r.run.scenario in ("power_transition", "wan_failover", "replay")])
for sc in ("power_transition", "wan_failover"):
    plots.figure_sensitivity(sens, sc); plt.show()
fp = {}
for r in sens:
    if r["scenario"] == "replay": fp.setdefault((r["floor"], r["threshold"]), []).append(r["fp_per_1000_normal"])
md_table([{"floor": f, "threshold": t, "FP / 1000 normal (replay runs, robust only)": f"{statistics.fmean(v):.1f}"} for (f, t), v in sorted(fp.items())],
         ["floor", "threshold", "FP / 1000 normal (replay runs, robust only)"])"""))
cells.append(md("""**Observation.** The executed grid confirms the analytical prediction: with the reference floor 0.25 an isolated
power transition is (almost) never detected at any threshold, while floor 0.10 makes it detectable at τ ≤ 3.2. The
false-positive table shows the price of lower thresholds on continuous features — which is why the protocol prefers
explicit rules for binary indicators and preregistered feature-specific floors."""))

# 10
cells.append(md("## 10. Timing and explanation outputs\n\nSynchronization latency is *generator-defined* time; append time is local hashing + 4 signatures on this runtime."))
cells.append(code("""ex = bm.scenario_extras(rows)
md_table([{"Scenario": config.SCENARIO_LABELS[e["scenario"]],
           "sync latency (ms)": f"{e['sync_latency_mean_ms_mean']:.1f}",
           "median append (ms)": f"{e['append_median_ms_mean']:.3f}",
           "top-3 hit rate": "n/a (no changed feature)" if math.isnan(e["explanation_top3_hit_rate_mean"]) else f"{e['explanation_top3_hit_rate_mean']:.3f}",
           "robust AUPRC": "n/a" if math.isnan(e["robust_auprc_mean"]) else f"{e['robust_auprc_mean']:.3f}"} for e in ex],
         ["Scenario", "sync latency (ms)", "median append (ms)", "top-3 hit rate", "robust AUPRC"])"""))

# 11
cells.append(md("## 11. Multi-seed robustness\n\nThe article lists additional master seeds as an open gate. Four further seeds (4 runs each, to keep runtime short) are executed here."))
cells.append(code("""ms_rows = []
for seed in (1, 2, 3, 4):
    _, r = bm.run_benchmark(seed, 4)
    for x in bm.summarize(r, bm.MODES):
        ms_rows.append({"seed": seed, **x})
agg = {}
for r in ms_rows:
    agg.setdefault((r["scenario"], r["mode"]), []).append(r["f1_mean"])
md_table([{"Scenario": config.SCENARIO_LABELS[sc], **{bm.MODE_LABELS[m]: f"{min(agg[(sc, m)]):.3f}–{max(agg[(sc, m)]):.3f}" for m in bm.MODES}}
          for sc in config.SCENARIOS], ["Scenario"] + [bm.MODE_LABELS[m] for m in bm.MODES])"""))

# 12
cells.append(md("## 12. Automated tests\n\nThe five core tests of Table 4 plus 15 extended edge-case tests (unknown/wrong keys, malformed input, ID collision, delayed and out-of-order events, quorum limits, detector mathematics, determinism)."))
cells.append(code("""import subprocess
p = subprocess.run([sys.executable, "-m", "unittest", "discover", "-v", "tests"], cwd=str(work.resolve()),
                   capture_output=True, text=True)
lines = p.stderr.strip().splitlines()
print("\\n".join(l.split(" (")[0] + " ... " + l.rsplit(" ", 1)[-1] for l in lines if l.endswith(("ok", "FAIL", "ERROR"))))
print("\\n".join(lines[-3:]))"""))

# 13
cells.append(md("## 13. Conclusions\n\nKey numbers from this execution:"))
cells.append(code("""F = {(r["scenario"], r["mode"]): r for r in abl}
print(f"Replay:               rules F1={F[('replay','rules')]['f1_mean']:.3f}, robust F1={F[('replay','robust')]['f1_mean']:.3f}, "
      f"hybrid F1={F[('replay','hybrid')]['f1_mean']:.3f}, integrity-only F1={F[('replay','integrity_only')]['f1_mean']:.3f}")
print(f"Power transition:     rules F1={F[('power_transition','rules')]['f1_mean']:.3f}, robust F1={F[('power_transition','robust')]['f1_mean']:.3f} "
      f"(recall {F[('power_transition','robust')]['recall_mean']:.3f}), hybrid F1={F[('power_transition','hybrid')]['f1_mean']:.3f}")
print(f"Hybrid FP per 1000 normal events: {min(F[(s,'hybrid')]['fp_per_1000_normal_mean'] for s in config.SCENARIOS):.1f}–"
      f"{max(F[(s,'hybrid')]['fp_per_1000_normal_mean'] for s in config.SCENARIOS):.1f}  vs rules "
      f"{min(F[(s,'rules')]['fp_per_1000_normal_mean'] for s in config.SCENARIOS):.1f}–{max(F[(s,'rules')]['fp_per_1000_normal_mean'] for s in config.SCENARIOS):.1f}")
print(f"All {len(rows)} evidence chains valid: {all(r['ledger_valid'] for r in rows)}; rejected events never changed state: "
      f"{all(r['state_unchanged_on_reject'] for r in rows)}")"""))
cells.append(md("""1. **Admission before state works as specified.** Replayed, modified (with or without a recomputed payload hash),
   unsigned, unknown-key, malformed and out-of-chain events were rejected, never changed the twin state, and still
   left a verifiable evidence record (§3, §12; all 48 benchmark chains valid).
2. **Authenticity, freshness and anomaly are different properties.** Replay leaves the feature vector ordinary, so both
   feature-only modes score F1 = 0; the hybrid detects it only through ¬g. The executed ablation confirms the article's
   derived Table 6: the replay and modification gain is attributable *entirely* to the integrity layer
   (integrity-only F1 = 1.000), and rules + integrity equals rules in all operational scenarios.
3. **Static rules dominate where a scenario crosses an explicit boundary**; the robust score is competitive only for the
   authentication surge, where a local baseline matters.
4. **The dispersion floor, not the threshold, decides binary detectability.** With $s_{min}=0.25$ an isolated
   power flip gives $A=\\sqrt{16/7}\\approx1.51<3.20$; robust-score F1 for power transition is ≈0.06, and the executed
   sensitivity grid reproduces the analytical Table 7 (floor 0.10 → detectable). Binary indicators belong in explicit
   rules or preregistered feature-specific floors.
5. **OR-fusion trades precision for coverage.** The hybrid inherits the robust score's false-positive rate (about two to
   three times that of rules), so it suits shared situational awareness and evidence, not direct paging; tiered alerts
   (integrity → operational rule → advisory score) are recommended for the field configuration.
6. **Explanations are faithful but not causal.** Top-3 contributions are the exact decomposition of the score and hit
   the manipulated features in the synthetic runs; they do not identify root causes.
7. **The findings are stable across seeds** (§11), but they remain *generator-level* results.
8. **Boundary.** Nothing here measures WAN switching, VPN recovery, wireless detection, EcoFlow autonomy, distributed-
   ledger behaviour or operator benefit. Those require the gated field protocol (S1) and its workbook (S2); synthetic
   timings (generator sync latency, sub-millisecond local append) must not be cited as network or blockchain
   performance."""))

for i, c in enumerate(cells):
    c["id"] = f"cell-{i:02d}"  # deterministic ids keep rebuilds byte-identical
nb = nbf.v4.new_notebook(cells=cells, metadata={
    "kernelspec": {"display_name": "Python 3", "language": "python", "name": "python3"},
    "language_info": {"name": "python"},
    "colab": {"provenance": [], "name": "MetaTwin_Guard_Colab.ipynb"},
})
out = ROOT / "notebooks" / "MetaTwin_Guard_Colab.ipynb"
nbf.write(nb, out)
print("written", out, f"({out.stat().st_size/1024:.0f} KiB)")
