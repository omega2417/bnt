# Confirmed-state access latency in a permissioned Avalanche L1

**A reproducible field experiment: protocol, code, reference dataset, statistics, figures and report.**

[Українською](README_UK.md) · [Protocol](protocol/PROTOCOL.md) · [Data dictionary](protocol/DATA_DICTIONARY.md) · [Reproduce](docs/REPRODUCE.md) · [Zenodo](docs/ZENODO.md)

This repository accompanies the study

> *A Blockchain Solution for Reducing Confirmed-State Access Latency in an
> Avalanche Network: An Experimental Study*

and contains everything needed to run the experiment on the two-site cyber
range of the University of Customs and Finance, to analyse the resulting
logs, and to reproduce every number and every figure of the paper from a
single command.

---

## What the experiment measures

Not the block interval, and not consensus finality. The primary metric is
**`T_visible`**: the time from transmitting a signed transaction until the
first *independent read node* returns the accepted, updated state.

```
T_visible,first(i) = min_r t_read(i,r) − t_send(i)          (eq. 5)
```

An operator needs the confirmed state, not merely a receipt — so the
measurement covers the complete path: submission, gossip, block inclusion,
consensus acceptance, execution, state commit, and the first confirmed
read-back from a node that did not produce the block.

The campaign compares five block-production profiles (stock, 1000, 750,
500, 250 ms) across three topologies and five offered loads, ten repeats
each: **750 runs, 34 875 000 scheduled transactions, 87.50 h** of minimum
machine time.

---

## Run it in Google Colab

The whole pipeline — schedule, traces, dataset, statistics, figures,
report, checksums and the Zenodo archive — runs in a free Colab CPU runtime
in about a minute.

**[`notebooks/Avalanche_Latency_Colab.ipynb`](notebooks/Avalanche_Latency_Colab.ipynb)**

Open it in Colab, run all cells, and the notebook will:

1. install the package and print the campaign arithmetic;
2. generate the randomized schedule and the immutable workload traces;
3. produce a reference dataset in the campaign's exact schema;
4. run the full statistical plan and render every table and figure;
5. verify the SHA-256 manifests and re-derive the results to prove
   bit-for-bit reproducibility;
6. build the archive for the Zenodo deposition and offer it for download.

The notebook also contains a **"bring your own logs"** cell: point it at a
directory of real campaign JSONL and every downstream step runs unchanged.

---

## Provenance, stated plainly

The provided sources confirm the physical infrastructure and the study
design. They contain **no raw logs, no deployed-network configuration and
no measured p50/p95/p99.** This repository therefore ships:

* the complete, executable protocol;
* the code that will run the real campaign (`alp.client`, `deploy/`);
* a **documented reference model** (`alp.simulate`) that produces a dataset
  in the campaign's exact schema.

Every record, table, figure and report generated from the model carries
`provenance = SIMULATED` and an explicit banner. **Those numbers are not
measurements of the cyber range and must not be reported as experimental
results.** `protocol/DATA_REQUIRED.md` lists what a real campaign has to
supply; `protocol/MODEL.md` states exactly what the model does and does not
represent.

When real logs exist, drop them into `data/raw/tx/` and run
`python -m alp pipeline --skip-simulation --provenance MEASURED`. Nothing
else changes: the analysis never asks where a record came from.

---

## Quick start (local)

```bash
pip install -r requirements.txt

python -m alp info --profile full        # the campaign arithmetic, eq. (1)-(4)
python -m alp pipeline --profile demo    # schedule, dataset, statistics, report
python -m alp verify data/raw results    # re-hash and compare to the manifests
python -m alp reproduce --profile smoke  # regenerate and diff the derived tables
python -m alp package --out dist/avalanche-latency-experiment.zip
```

Campaign profiles: `full` (the pre-registered 750-run protocol), `demo`
(every factor level, shortened window — the Colab default), `smoke` (a
two-minute continuous-integration campaign).

---

## What is in here

```
protocol/     the executable specification: protocol, model, data dictionary,
              outstanding-data checklist (English and Ukrainian)
src/alp/      the package
  config.py     every pre-registered constant, in one file
  schedule.py   randomized blocked schedule (750 runs)
  traces.py     immutable workload traces that make the design paired
  theory.py     closed-form pre-experiment calculations, eq. (15)-(16)
  model.py      reference-model parameters, each with its DATA REQUIRED replacement
  simulate.py   discrete-event reference model of the measured path
  client.py     the measurement client that runs on the 25 workstations
  metrics.py    equations (5)-(14), one function each
  analyze.py    run-level reduction, paired bootstrap, Holm, stability rules
  figures.py    every figure of the paper, drawn from code
  tables.py     result tables as CSV, Markdown and JTIT-style LaTeX
  report.py     the narrative report, with hypothesis verdicts by rule
  manifest.py   SHA-256 manifests and reproduction diffs
  package.py    the deterministic Zenodo archive
contracts/    VisibilityProbe.sol and its ABI
deploy/       chain and subnet configs per profile, netem, preflight, run_one,
              Prometheus scrape config, node passport template
scripts/      network probes, node telemetry collector, per-client trace split
notebooks/    the Colab notebook
tests/        pytest suite: protocol arithmetic, metrics, statistics, determinism
```

---

## Design decisions worth knowing

**The run is the inferential unit.** Transactions inside a run share a
block, a consensus round and a disk queue. Bootstrapping individual
transactions would produce artificially narrow intervals, so every metric is
reduced to run level before any confidence interval is built.

**The design is paired.** All configurations replay the same immutable
trace within a `topology × load × repeat` stratum, so the baseline is
subtracted run by run.

**One clock.** Every timestamp entering `T_visible` comes from the
generator's monotonic clock, so inter-host clock offset cannot enter the
primary metric. NTP discipline is still recorded — it just does not have to
be trusted.

**Open loop.** The load generator does not wait for a response before
issuing the next transaction. A closed loop would turn overload into a
politely self-throttling arrival process and hide the queueing behaviour the
study is about.

**Thresholds are pre-registered.** The stability rules of protocol section
12 live in `config.py` and are applied by code before any result is
inspected. Maximum sustainable load is reported under both pre-registered
variants; a disagreement between them is reported as a boundary, not
silently resolved.

---

## Reproducibility guarantees

* Every random draw comes from a seed derived from one master seed, so the
  schedule, the traces and the reference dataset regenerate byte for byte.
* `python -m alp reproduce` regenerates the dataset into a scratch tree and
  diffs every derived CSV against the committed one.
* `MANIFEST.sha256` and `MANIFEST.json` record the hash, the environment,
  the profile, the thresholds and the provenance of every artefact.
* The Zenodo archive is built deterministically: same tree in, same
  SHA-256 out.

---

## Safety

Load is directed only at the project's own permissioned L1 and isolated RPC
endpoints. The public Avalanche network is never used for high-intensity
load. `deploy/preflight.sh` refuses to start a run while a route exists from
the test segment to a declared production range, and `deploy/netem.sh`
refuses to shape an interface carrying the default route. Private keys
travel through the environment or a secret store and never reach JSONL, Git
or the published dataset.

---

## Citing

See `CITATION.cff`. The dataset and the code are archived on Zenodo; the
DOI is recorded in `.zenodo.json` and in `docs/ZENODO.md` after the first
deposition.

## Licence

Code: MIT (`LICENSE`). Data, figures and documentation: CC BY 4.0
(`LICENSE-DATA`).
