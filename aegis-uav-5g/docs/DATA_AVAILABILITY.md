# Data availability & Zenodo-ready release

All results in the manuscript are produced by this repository from configuration
files and random seeds alone — there are no external datasets and no hand-entered
numbers.

## Reproducing every result with one command

```bash
python -m pip install -e .
aegis campaign --config configs/experiments/paper_v1.yaml   # full campaign
# or, fast: aegis campaign --config configs/experiments/smoke.yaml
```

Outputs land in `artifacts/`:

- `metrics/<run-group>/*.csv` — machine-readable metrics (the source of every table/figure)
- `tables/<run-group>/*.{csv,tex,md}` — Tables 2–6, statistical report, error analysis
- `tables/<run-group>/manuscript_data_map.{md,json}` — each `[DATA REQUIRED]`
  manuscript item mapped to its computed value and evidence file
- `figures/<run-group>/*.{svg,pdf,png}` — Figs 4/5, sensitivity, scalability
- `logs/<run-group>/incidents/*.json` — per-incident explanation objects
- `manifests/*.json` — run + report manifests (run ID, seed, git commit, config hash, environment)

## Preparing the Zenodo deposit

1. Run the full `paper_v1` campaign so `artifacts/` is populated.
2. Create an archive of the code, configs, seeds and a dataset snapshot:

   ```bash
   git archive --format=zip -o aegis-uav-5g-src.zip HEAD
   zip -r aegis-uav-5g-artifacts.zip artifacts/metrics artifacts/tables \
       artifacts/figures artifacts/manifests
   ```

3. Upload both archives to Zenodo. The included [`.zenodo.json`](../.zenodo.json)
   supplies the deposit metadata (title, description, keywords, license, and the
   `isSupplementTo` link to the article).
4. Zenodo mints a DOI; add it to `CITATION.cff` and the article's Data
   Availability statement.

## Provenance guarantees

- A single master seed drives all randomness; every run records its seed, git
  commit, config hash and environment manifest.
- The test split is evaluated exactly once, after tuning; no test data is used to
  select thresholds or hyperparameters.
- Every figure is rendered from a CSV/Parquet under `artifacts/metrics/`.
