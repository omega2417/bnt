# Changelog

## 1.0.0 — 2026-11-23

First public release, prepared for submission to *Computers & Security*.

* Simulator with structural separation of generator, operator, test module and evaluator.
* 13 conditions (C0–C12) defined in one JSON file; five separated PCG64 streams with a fixed,
  documented consumption order.
* Byte-reproducible primary logs and SHA-256 manifest of 95 output files.
* Analysis module that does not import the simulator; 95% percentile bootstrap over whole
  trajectories (10,000 resamples, seed 20261124).
* 27 implementation checks, 100 automated tests, dependency-free worked-example script.
* Figures 1–5 as vector PDF, 1000 dpi TIFF and 600 dpi PNG at Elsevier column widths.
* Claim-to-evidence register comparing 410 numbers printed in the manuscript draft with the
  recomputed values.
