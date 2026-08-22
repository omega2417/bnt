# Reproducing this work

Three levels, depending on how much you want to verify.

| Level | Command | Time | What it proves |
| --- | --- | --- | --- |
| Check the artefacts | `make verify` | seconds | the shipped results match their SHA-256 manifests |
| Re-derive the results | `make reproduce` | ~1 min | regenerating from the master seed yields byte-identical tables |
| Rebuild everything | `make pipeline` | ~1 min (`demo`) | the full pipeline runs from scratch on your machine |

## In Google Colab

Open `notebooks/Avalanche_Latency_Colab.ipynb` and run all cells. It installs
the dependencies, runs the pipeline, renders every table and figure, verifies
the manifests, re-derives the results and builds the Zenodo archive.

The notebook exports `PYTHONPATH` in its setup cell, because the `!python -m
alp ...` cells run in subprocesses that do not inherit `sys.path`.

## Locally

```bash
git clone <repository-url>
cd avalanche-latency-experiment
pip install -r requirements.txt
export PYTHONPATH=src            # or: pip install -e .

make info PROFILE=full           # the campaign arithmetic
make pipeline PROFILE=demo       # schedule, dataset, statistics, figures, report
make verify                      # re-hash and compare
make reproduce PROFILE=demo      # regenerate and diff every derived table
make test                        # 43 tests
```

## Campaign profiles

| Profile | Runs | Window | Scheduled TX | Purpose |
| --- | --- | --- | --- | --- |
| `full` | 750 | 300 s | 34 875 000 | the pre-registered protocol |
| `demo` | 225 | 20 s | 697 500 | every factor level, notebook-sized |
| `smoke` | 40 | 5 s | 12 500 | continuous integration |

All three keep the five configurations; `full` and `demo` also keep all three
topologies and all five loads. Only the window length and the repeat count
shrink, so the shape of the analysis is identical at every size.

The shortened window has one visible consequence: a p99 estimated from a
20-second window is noisier than one from 300 seconds, so boundary cells can
flip between the strict and majority stability rules. The report says so
explicitly where it happens, rather than hiding it — that is exactly the
condition the protocol's precision rule exists to handle.

## What determinism rests on

* One master seed (`alp.config.MASTER_SEED`); every stream draws a sub-seed
  through `derive_seed`, keyed by what the stream *is*, not by execution order.
  Running the campaign in a different order changes nothing.
* No wall-clock time, hostname or path enters any generated artefact.
* Gzip files are written with `mtime=0`, CSVs with an explicit line terminator
  and float format, JSON with sorted keys.
* The Zenodo archive pins entry order, timestamps and compression level.

If `make reproduce` reports a difference, the diff names the file. The usual
causes are a different `PROFILE` between the committed tree and the run, or a
NumPy version whose default quantile behaviour differs — the pipeline pins the
method explicitly (`inverted_cdf`, equation 8) precisely to avoid that.

## Analysing a real campaign

```bash
# raw logs in place under data/raw/tx/ (see protocol/DATA_DICTIONARY.md)
make measured
```

which is `python -m alp pipeline --profile full --skip-simulation
--provenance MEASURED`. The analysis code is unchanged: it reads the
`provenance` field from the records and propagates it into every table,
figure and report. Complete `protocol/DATA_REQUIRED.md` before publishing any
number.
