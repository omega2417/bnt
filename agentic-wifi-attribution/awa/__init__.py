"""Agentic Wi-Fi Spatial Attribution Readiness Platform (reference core).

``awa`` is a compact, reproducible reference implementation of the core
scientific machinery described in the design prompt *Agentic Wi-Fi Spatial
Attribution Readiness Platform for Critical Information Infrastructure*:

* explainable Bayesian localisation on a spatial grid, fusing three
  modalities (RSSI fingerprinting, FTM/RTT ranging, IEEE 802.11bf WLAN
  sensing) with robust likelihoods and an explicit *missing-modality* mask;
* uncertainty quantification (posterior, HPD region, entropy, sharpness,
  zone probabilities, multimodality, calibration);
* cross-modal consistency (Jensen-Shannon divergence, MAP Mahalanobis
  distance) yielding ``CONSISTENT`` / ``UNCERTAIN`` / ``CONFLICT``;
* a lightweight digital twin of the radio environment used for synthetic
  telemetry, drift injection and twin-residual threat cues;
* a minimal event-driven multi-agent orchestrator;
* a Technology / Commercialisation / Integration / Operational Readiness
  model with non-compensatory gate rules;
* a machine-readable, hash-anchored Spatial Attribution Record (SAR).

The package is intentionally dependency-light (NumPy + SciPy) so that it runs
unmodified in Google Colab and in offline reproducibility environments.

This is a research/reference artefact.  It deliberately uses **synthetic**
telemetry only and contains no real coordinates or configurations of any
critical information infrastructure, per the design prompt.
"""

from __future__ import annotations

__version__ = "0.1.0"
__all__ = ["__version__"]
