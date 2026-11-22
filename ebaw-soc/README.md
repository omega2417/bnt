# ebaw-soc 2.0.0 — evidence-bound action warrants for agentic security operations

> **About this repository.** This is a GitHub copy of the archived releases on Zenodo, with no changes to code or data:
> - **ebaw-soc 2.0.0** (software, simulation and reference gateway core): https://doi.org/10.5281/zenodo.23246047
> - **EBAW-SOC-Synth 1.0.0** (synthetic dataset, also in [`data/ebaw-soc-synth-1.0.0/`](data/ebaw-soc-synth-1.0.0/)): https://doi.org/10.5281/zenodo.23246133
>
> Please cite the Zenodo DOIs (see [`CITATION.cff`](CITATION.cff)). Author: Dmytro Prokopovych-Tkachenko
> ([ORCID 0000-0002-6590-3898](https://orcid.org/0000-0002-6590-3898)). License: MIT for code, CC BY 4.0 for the dataset.


Simulation, reference gateway core, the **EBAW-SOC-Synth** dataset and a self-contained Google Colab
notebook accompanying the article

> D. Prokopovych-Tkachenko, *Evidence-Bound Action Warrants for Agentic Security Operations: A Deterministic
> Gateway Enforcing Evidence Freshness, Calibrated Confidence, and Response Deadlines*, submitted to
> *Inventions* (MDPI), 2026.

An LLM agent in a security operations center (SOC) proposes containment actions. A deterministic gateway
outside the agent admits an action only if five predicates hold: P1 evidence freshness, P2 calibrated
confidence, P3 quorum-confirmed ledger evidence, P4 current policy version and P5 response-time budget.
It then issues a signed, single-use, expiring **warrant**, which is revalidated immediately before
execution.

Version 2.0.0 extends `ebaw-sim 1.0.0` (Supplementary Material S1 of the article). The simulation and the
article scripts are unchanged and still reproduce every number of the article bit for bit.

| Component | Where | What |
|---|---|---|
| Discrete-event simulation | `ebaw/model.py`, `ebaw/sim.py`, `scripts/` | 6 admission policies × 8 scenarios × 30 replications, lattice of 32 contracts, Propositions 1–2, Figures 1–6, Tables 4–6 |
| Reference gateway core | `ebaw/warrant.py`, `ebaw/ledger.py`, `ebaw/gateway.py` | Algorithm 1 from authenticated inputs only; Ed25519-signed warrants (Table 3); masking Byzantine quorum reads; enforcement point with nonce store |
| Dataset EBAW-SOC-Synth 1.0.0 | `data/ebaw-soc-synth-1.0.0/`, `ebaw/dataset.py` | record schema of Table 7, catalog D1–D8 of Table 8: 900 episodes, 6300 proposals (615 adversarial), 9 CSV tables, signed manifest, datasheet |
| Benchmark | `ebaw/benchmark.py`, `scripts/benchmark_dataset.py` | T1 calibration, T2 thresholds, T3 admission policies, sample sizes (Eq. 22) — Figures 7–8 |
| Colab notebook | `notebooks/EBAW_Colab.ipynb` | self-contained (embeds the whole package); runs end to end in 1–3 min |
| Tests | `tests/` | 48 property tests (Propositions 3–4, quorum masking, warrant integrity, calibration, determinism, dataset integrity) |

**All data are synthetic.** The latency distributions, drift model, policy dynamics, calibration and analyst
model are stated assumptions (Section 4 of the article). Ledger confirmation latencies are parameterized
from published Avalanche figures. EBAW-SOC-Synth realizes the *proposed* cyber-range dataset with simulated
records. It is not a measurement of a real SOC.

## Quick start

**Google Colab.** Open `notebooks/EBAW_Colab.ipynb` (File → Upload notebook) and choose *Runtime → Run all*.
The notebook writes the package itself and installs only `simpy`.

**Locally** (Python 3.13 and the pinned versions reproduce the article exactly; Python ≥ 3.10 runs):

```bash
python3 -m pip install -r requirements.txt
bash run_all.sh                       # about 3 minutes on one core: article results, dataset, benchmark, tests
python3 -m ebaw demo                  # narrated protocol walk-through with attacks
python3 -m ebaw dataset --out /tmp/ds # regenerate the dataset (5 s, byte-identical)
python3 -m ebaw validate data/ebaw-soc-synth-1.0.0
python3 -m ebaw benchmark data/ebaw-soc-synth-1.0.0
python3 -m pytest -q                  # requires requirements-dev.txt
```

Set `EBAW_NREP` to change the number of replications of the article experiments (default 30), e.g.
`EBAW_NREP=5 bash run_all.sh` for a smoke test.

## Reproduce the article

| Step | Command | Outputs (`results/`, `figures/`) | Article |
|---|---|---|---|
| 1 | `python3 scripts/run_experiments.py` | `main_runs.csv`, `lattice_runs.csv`, `windows.csv`, `upset_EB_S7.csv`, `cfd_S6_rep0.csv`, `traces.json`, `prop1.csv` | all simulation runs |
| 2 | `python3 scripts/extra_analyses.py` | `ablation_fifo.csv`, `ttc_auto.csv`, `extra.json` | FIFO/EDF ablation, TTC, miss attribution |
| 3 | `python3 scripts/fig1_sequence.py` … `fig6_cd.py` | `fig1_sequence.png` … `fig6_cd.png`, `friedman.json` | Figures 1–6, Friedman/Nemenyi |
| 4 | `python3 scripts/analyze.py` | `summary.json`, `table_J_by_scenario.csv`, `table_UER_by_scenario.csv` | Tables 4–6, Sections 5.1–5.6 |
| 5 | `python3 scripts/make_dataset.py` | `data/ebaw-soc-synth-1.0.0/` | Section 6.1, Tables 7–8 |
| 6 | `python3 scripts/benchmark_dataset.py` | `dataset_benchmark.json`, `dataset_policies_test.csv`, `dataset_thresholds.csv`, `fig7_dataset.png`, `fig8_calibration.png` | Section 6.1, 6.3 |

Headline numbers (pooled over 8 scenarios × 30 replications): the full gateway executes 0 of 4276
adversarial proposals; confidence-only admission executes 3309 (77.4%). The gateway records 0 contract
violations in 53,668 autonomous executions and reduces unsafe executions from 53.2 to 14.6 per 1000
proposals, at a deadline-miss rate 2.0 points higher.

| Article element | Source |
|---|---|
| Figure 1 (UML sequence diagram) | `scripts/fig1_sequence.py` |
| Figure 2 (timing diagram) | `scripts/fig2_timing.py` ← `results/traces.json` |
| Figure 3 (Hasse diagram of 32 contracts) | `scripts/fig3_hasse.py` ← `results/lattice_runs.csv` |
| Figure 4 (UpSet plot) | `scripts/fig4_upset.py` ← `results/upset_EB_S7.csv` |
| Figure 5 (cumulative flow diagram) | `scripts/fig5_cfd.py` ← `results/cfd_S6_rep0.csv` |
| Figure 6 (critical difference diagrams) | `scripts/fig6_cd.py` ← `results/main_runs.csv` |
| Tables 4–6 | `ebaw/model.py`, `results/prop1.csv`, `results/table_J_by_scenario.csv`, `results/summary.json` |
| Algorithm 1, Table 2, Table 3 | `ebaw/gateway.py`, `ebaw/warrant.py` |
| Proposition 3 (fail-closed, no self-authorization) | `tests/test_gateway.py`, `python -m ebaw demo` |
| Proposition 4 (pointwise monotonicity) | `tests/test_gateway.py::test_contract_monotonicity_pointwise` |
| Tables 7–8 (dataset schema and catalog) | `ebaw/dataset.py` (`SCHEMA`, `CATALOG`), `data/ebaw-soc-synth-1.0.0/` |
| Eq. (22), rule of three (Section 6.3) | `ebaw/stats.py`, `tests/test_model.py` |

## Reference gateway core

```python
from ebaw.demo import World
W = World()                                          # sensors, 5-validator ledger (f = 1), policy store, gateway, PEP
e = W.observe("ws-0042", t_obs=100.0, score=0.97)    # signed observation, digest anchored on the ledger
p = W.propose("isolate_host", "ws-0042", [e.evidence_id], claimed=0.99, t=112.0)
d = W.gw.admit(p, 112.0)                             # ISSUE -> d.token is a signed warrant
W.gw.revalidate(d.token, 140.0)                      # EXECUTE (commits the verdict)
W.pep.execute(d.token, "isolate_host", "ws-0042", 140.1)   # (True, 'executed'); a replay is refused
```

The gateway never reads the confidence claimed by the agent (assumption A3). Every missing input, parse
error or timeout makes the affected predicate false (A4). A warrant authorizes exactly one action on one
asset until its expiry `t_exp = t_obs + min(Φ, D − τ̂)` (Eq. 9). Signing uses Ed25519 from `cryptography`
when it is installed. Otherwise it falls back to HMAC-SHA256, which is meant for experiments only: it is a
symmetric scheme and does not satisfy assumption A1.

## Dataset EBAW-SOC-Synth 1.0.0

Nine linked tables: `episodes`, `observations`, `ledger_anchors`, `proposals`, `policy_snapshots`,
`gateway_verdicts`, `executions`, `analyst_actions` and the benchmark table `policy_outcomes`, which holds
the outcome of every proposal under all six policies. Splits are made at episode level and in time
(60/20/20). The dataset includes SHA-256 digests, Ed25519 sensor signatures, signed warrant tokens and a
signed Merkle-root manifest, together with `datapackage.json` (Frictionless), `DATASHEET.md` and
`LICENSE` (CC BY 4.0). It can be deposited as a separate Zenodo record with `zenodo/dataset.zenodo.json`.

## Determinism

Replication *r* of the article experiments uses seed `42 + r`. Dataset shift *k* of scenario D*j* uses seed
`20260000 + 1000·j + k`. Each proposal draws its attributes from its own generator seeded by (seed,
stream, index), so all comparisons are paired. With the pinned package versions all outputs, including the
dataset Merkle root, are reproduced exactly.

## Layout

```
ebaw/            package: model, sim (v1.0.0, unchanged); warrant, ledger, gateway, stats, dataset, benchmark, demo (new)
scripts/         article experiments and figures (v1.0.0); make_dataset.py, benchmark_dataset.py (new)
data/            EBAW-SOC-Synth 1.0.0 (CSV, datapackage.json, manifest.json, keys.json, DATASHEET.md, LICENSE)
notebooks/       EBAW_Colab.ipynb (self-contained, executed)
results/         generated tables (CSV/JSON)
figures/         generated figures (PNG, 400 dpi)
tests/           pytest property tests
tools/           build_notebook.py (regenerates the notebook from ebaw/), make_release.sh
zenodo/          dataset.zenodo.json (metadata for a separate dataset record)
```

## License and citation

Code: MIT License (`LICENSE`). Dataset: CC BY 4.0 (`LICENSE-DATA`). Please cite the software and dataset via
`CITATION.cff` and the Zenodo DOI, and the article once published. Metadata: `.zenodo.json`, `codemeta.json`.
