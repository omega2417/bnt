# Changes in 2.0.2 — Google Colab

- Reproduced the original standalone notebook failure: its first cell imported a package from a sibling directory absent in Colab.
- Added `COLAB_START.ipynb` and made the existing demo notebook an identical standalone copy.
- Embedded the actual module source and test suite; bootstrap validates its checksum and imports only from the extracted project directory.
- Added conditional dependency installation without unnecessarily replacing Colab's scientific libraries.
- Added 34-cell sequential execution, automatic tests, 13 figure exports, portable HTML/CSV/JSON/model results and a Colab download button.
- Added `scripts/build_colab_notebook.py` for reproducible notebook regeneration, and `scripts/verify_colab.py` for isolated cell-by-cell execution evidence.
- Retained the computational models from 2.0.1; Colab adaptation changes initialization, presentation and export, not model equations.
- Google-hosted execution has not been claimed. See the new verification record for actual runtime evidence.

# Changes in 2.0.1

## Reproducible execution

- Added a real CLI (`demo`, `simulate`, `predict`, `doctor`), source/module/installed entry points and Windows/POSIX launchers.
- Added an embedded-image HTML report, CSV/JSON export, saved-model inference and explicit schema/version checks.
- Corrected dependency setup, removed self-referential `all` extra, added wheel/source packaging, tested-version constraints and optional Docker/CI configuration.
- Made all original figure/table scripts directly executable from source, with automatic output directory creation and no mandatory Basemap dependency.
- Added a notebook executor that does not require TCP kernel startup; retained normal Jupyter support. Notebook evaluation is reused instead of training twice.

## Correctness

- Removed use of test labels when extracting `anomaly_distance`; replaced per-batch fitted values with a fixed, documented RMS of normalized physical residuals.
- Made derivatives and rolling windows causal and pass-isolated. Added one-row/empty-data support, real time differences, range-aware residuals and invalid-data errors.
- Moved Mahalanobis threshold calibration to nominal training data. Predictions no longer depend on other rows in the prediction batch.
- Selected classifiers on independent validation passes. Static-threshold baseline now requires `X_nominal_train`; using test labels to calibrate is rejected.
- Fixed rounded pass counts and zero-weight classes. Allocation totals exactly `n_passes`; each positive-weight state is represented when the requested budget permits.
- Fixed onset at 100%, invalid states, invalid severity, and invalid sampling parameters.
- Corrected `signal_count` to signal detection probability, updated modeled rates after anomalies, and exported explicit `window_s` and `key_bits`.
- Implemented `block_size_s` for the finite-size estimate, split epsilon across blocks, included observed signal errors in the phase-error approximation and validated counts/intensities.
- Corrected continuous-latitude handling for one/two GEO nodes; added empty-site shape handling and invalid-time checks.
- Added Link parameter validation and stable zero-signal/zero-background behavior.
- Fixed impossible network redundancy and invalid store-model parameters.
- Clarified OPA peak-to-null/FWHM terminology and grating-lobe limitations; stabilized periodic array-factor maxima.

## Compatibility and interpretation

- Package/module names and baseline link/geometry regression targets are retained.
- Previously trained models must be retrained: the feature and telemetry semantics changed.
- `anomaly_distance` is a fixed-scale diagnostic, not a Mahalanobis distance. The separately trained Mahalanobis detector remains available.
- `finite_key_pass(..., block_size_s=N)` now uses N-second blocks; N must be a positive integer. It remains a simplified research estimate, not a security proof.
- `static_threshold_baseline` requires the keyword argument `X_nominal_train`.
- Evaluation defaults are reduced for a practical demonstration; tree count and feature-importance repetitions are explicit parameters.
- Generated ML/finite-size results must be re-evaluated before use in an article. Source references describe foundations, not an independent scientific validation of this simulator.
