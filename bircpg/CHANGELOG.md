# Changelog

## 1.0.0

First release: the reference implementation accompanying the manuscript
*Bio-Inspired Resource-Constrained Potential Games for Adaptive Coordination in
Autonomous Multi-Agent Systems*.

### Implemented

* **Section 4** — feasible action sets under energy, computation, memory and
  latency caps (Eq 1); the dimensionless cost (Eq 2); payoffs with reward
  sharing and congestion (Eq 3); aggregate model welfare (Eq 4).
* **Section 5.1** — the exact potential (Eq 5); Proposition 1 verified on every
  feasible unilateral deviation; Corollary 1 as terminating improvement paths;
  pure equilibria, potential and welfare maximisers, price of anarchy.
* **Section 5.2** — bounded payoff-estimation error (Eq 7); Proposition 2; the
  uncertainty gate (Eq 8) with its `4δ + θ` stopping certificate; calibration
  coverage reporting.
* **Section 5.3** — trace update with decay and delay (Eq 9); frozen
  full-support reference distributions (Eq 10); the reference-biased logit rule
  (Eq 11); Proposition 3's stationary law (Eq 12) cross-checked by detailed
  balance against an independently built transition matrix; Corollary 2 (Eq 13).
* **Section 5.4** — Algorithm 1, with the robust and logit branches kept as
  mutually exclusive alternatives and termination reasons recorded separately.
* **Section 6** — the constructed two-agent example in exact rational
  arithmetic, reproducing Table 2, the price of anarchy and Equation (15).
* **Section 7** — the Level I verification sweep with its edge cases; the Level
  II synthetic generator and Table 3 factors; baselines B1–B5 with oracle
  advantages labelled; endpoints with censoring; paired bootstrap over whole
  runs; Holm correction.
* Figure 3 regenerated from the code, with a CSV table view.
* A Colab-ready notebook and a Zenodo deposition archive builder.

### Deliberately not implemented

Level III: trained controllers, physical platforms, and measured energy or
latency. No experiment reported in the manuscript has been executed, and the
package asserts no empirical performance claim.
