# SatQKD-Sentinel 2.0.2

**Google Colab:** open `COLAB_START.ipynb` using **File → Upload notebook**, then **Runtime → Run all**. Only this notebook is needed; all project code and tests are embedded. See [START_COLAB.md](START_COLAB.md).

A self-contained research simulation project for satellite QKD links, optical phased arrays, geostationary coverage and synthetic telemetry classification.

**Українська інструкція: [README_UK.md](README_UK.md).**

Open `results/demo/report.html` for a ready-to-view offline report. To recompute it, install Python 3.10+ (3.12 recommended), unpack this folder and run `start.bat` on Windows or `sh start.sh` on Linux/macOS. Initial dependency installation requires Internet; subsequent runs need no services, credentials, external dataset or article files.

Manual setup:

```bash
python -m venv .venv
# Activate .venv using the command for your OS.
python -m pip install -r requirements.txt
python run.py demo
```

The default experiment uses a random forest with 30 training, 10 validation and 20 independent test passes. `--full` compares gradient boosting, random forest and logistic regression. Model selection uses validation passes only. The report embeds all images and is accompanied by CSV, JSON, PNG and a trained model.

```bash
python run.py demo --full --train 40 --test 20 --output results/full
python run.py simulate --passes 20 --output results/telemetry.csv
python run.py predict --model results/demo/model.joblib --input results/telemetry.csv --output results/predictions.csv
python run.py doctor
python -m pip install -e ".[test,notebook]"
python -m pytest -q
python scripts/execute_notebook.py
```

After installation, `python -m satqkd_sentinel` and `satqkd-sentinel` are equivalent entry points. Use only trusted joblib models; retrain locally if package or scikit-learn versions differ. `requirements-tested-py312.txt` records the exact tested dependency versions for Python 3.12.

All figure scripts accept an output directory or filename, create missing directories and work without Basemap. `pip install ".[maps]"` adds optional coastlines. `make test tables figures demo` runs the main workflows where Make is available; `make notebook` executes the notebook in-process without a TCP kernel. Interactive Jupyter remains available with the notebook extras.

Optional container configuration (not exercised in this environment):

```bash
docker build -t satqkd-sentinel .
docker run --rm -v "$(pwd)/results/docker:/output" satqkd-sentinel
```

## Scientific scope

This is a simulator, not a hardware QKD implementation. All telemetry is synthetic; classifier scores are simulator results. The finite-size routine is an illustrative estimate, **not a composable security bound**. Its 50/25/25 signal/decoy pulse allocation differs from the all-signal asymptotic reference. Classification and modeled key-retention policies do not establish the security of real keys.

The geometry uses spherical Earth and two-body motion. Availability assumes independent links, not general ring connectivity. The default OPA pitch admits grating lobes; its principal steering interval is not a grating-lobe-free guarantee. The federated architecture figure is conceptual; distributed training is not implemented. All assumptions and module descriptions are in `README_UK.md`.

The original archive described the software as accompanying “AI-Driven Telemetry Analytics for Cybersecurity of Satellite Quantum Key Distribution Networks with a Geostationary Backbone and Optical Phased Arrays: Architecture, Link Modelling and Fault-Attack Discrimination.” This repair preserves the baseline link/geometry regressions but changes telemetry and finite-size estimates. Do not treat regenerated results as experimental measurements or unchanged article results.

## References and verification

- Data-isolation practice: https://scikit-learn.org/stable/common_pitfalls.html
- Decoy-state foundation: Ma et al., *Practical Decoy State for Quantum Key Distribution*, https://arxiv.org/abs/quant-ph/0503005. The simplified finite-size penalties here are not a complete implementation of that or any composable proof.
- Fixes and API changes: `CHANGELOG.md`.
- Executed checks and platform limitations: `VERIFICATION.md`.

Code: MIT. Figures and result files retain the original project's CC BY 4.0 designation. Author information is retained in `CITATION.cff`.
