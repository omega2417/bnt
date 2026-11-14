# Verification — 2.0.2, Colab adaptation

The original first code cell failed with `ModuleNotFoundError: satqkd_sentinel` when executed as a standalone notebook in a clean directory. This failure was reproduced using the uploaded 2.0.1 ZIP, not inferred from a previous result.

The new initialization cell embeds the module source and tests, verifies the payload SHA-256, extracts it to a fresh runtime folder, checks dependency minimums and explicitly imports from that folder. Relative parent-directory imports have been removed. A single `.ipynb` is sufficient.

## Executed verification

- Every one of the **34 code cells** was executed in sequence, without skipping cells or predefining their scientific variables.
- The first isolated environment had **no installed satqkd_sentinel package**. Tested scientific versions: Python 3.12.14, NumPy 1.26.4, SciPy 1.13.1, pandas 2.2.2, Matplotlib 3.9.2, scikit-learn 1.5.2, joblib 1.4.2.
- An additional pass executed the standalone calculation notebook with the NumPy 2.3.5 / pandas 2.2.3 / scikit-learn 1.8.0 stack, exercising explicit override of a previously installed project version. The final release pass additionally checks installation of the initially missing ipywidgets dependency.
- The notebook itself runs all **67 project tests** in a subprocess and stops if any fail.
- **13 inline PNG figures** and their exported copies are verified. CSV, JSON, HTML, saved-model and ZIP exports are produced by executed cells.
- `verification/colab_cells.json` records the status and duration of every final notebook code cell. `verification/colab_summary.json` records the actual environment. The supplied `notebooks/COLAB_VERIFIED.ipynb` retains outputs of that execution.
- `COLAB_START.ipynb` and `notebooks/demo_satqkd_sentinel.ipynb` are identical. The verified notebook has the same code-cell source as the delivered start notebook.

## What this does and does not establish

Execution used isolated local IPython, **not a hosted Google Colab VM**. Google login, Google's hosted runtime, and the frontend download-button click were not exercised. The local fallback of the final download cell was executed. This is not represented as a live Colab certification.

The notebook targets Colab's normal Python/CPU workflow, requires no Drive mount or separate project upload, and installs missing packages only. Network access is required if a dependency must be installed. Unsupported older scientific packages produce an explicit upgrade/restart instruction instead of silently altering the running environment.

Cells must be executed in order with Run all. An arbitrary cell executed after a runtime reset can still need variables from preceding cells; this is normal notebook dependency behavior.

No mathematical-model changes were made for the Colab adaptation. All outputs remain synthetic research simulations, not hardware measurements or a composable cryptographic security proof. Existing local CLI/figure workflows are retained; Windows/macOS and Docker are not newly certified.
