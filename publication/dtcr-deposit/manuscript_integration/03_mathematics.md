# Mathematical corrections

Fold into §2.4–2.5. Each item states the printed form, the problem, and the
correction the code implements.

## Eq. (7) — anomaly likelihood

**Printed:** a_i(t) = 1 − exp(−d_i²(t)/2).

**Problem:** this is a bounded monotone score, not the anomaly probability of a
p-dimensional feature vector; it ignores the dimension entirely.

**Correction (implemented in `dtcr.anomaly.score_chi2`):** under the Gaussian
assumption of §2.4 with dimension p,

    a_i(t) = F_{χ²_p}(d_i²(t)),

the CDF of the chi-square distribution with p = 9 degrees of freedom. Report,
per §5.1 of the review: the number of normal samples (normal window 1800 s),
the disjoint train/calibration/test split, the Kolmogorov–Smirnov goodness-of-fit
of d² against χ²_p on the calibration window
(`dtcr.anomaly.gaussian_fit_check`), and the covariance shrinkage 0.05 used for
Σ⁻¹. If the KS test rejects Gaussianity, fall back to the empirical calibration
(`dtcr.anomaly.empirical_calibration`) and describe a_i as a calibrated tail
probability. The printed exponential form is retained in the code as
`score_legacy` only for comparison.

## Eq. (8) — local risk aggregation

**Printed:** R_i = a_i (1 − T_i) s_i — a hard AND that zeroes the risk whenever
any single factor is zero.

**Correction:** choose the aggregation empirically. `dtcr.risk.select_aggregation`
compares the multiplicative form against the additive form

    R_i = s_i [ w_a a_i + w_t (1 − T_i) + w_at a_i (1 − T_i) ],  w_a+w_t+w_at = 1,

by AUC on labelled calibration data and reports the winner. The deposit uses the
additive form with (0.45, 0.35, 0.20); state that this was selected by ROC/AUC on
the calibration set, not postulated.

## Graph-risk propagation (Eq. 9–11)

Corrections implemented in `dtcr.risk`:

- **Normalisation of W:** column-stochastic on outgoing influence mass
  (`row_normalise`), so the operator norm is controlled and λ is the only knob.
- **Spectral radius and margin:** report ρ(λWᵀ) and the convergence margin
  1 − ρ(λWᵀ) for the actual graph (`spectral_radius`, `convergence_margin`);
  Figure 8(b) shows both the acyclic chain (nilpotent, ρ = 0) and a cyclic
  variant whose margin reaches zero at λ* = 1/ρ(Wᵀ), with the operating point
  λ = 0.45 well inside it.
- **‖R‖₁ = 0 behaviour:** κ is defined as 1 in that case (`amplification`).
- **Score is not a probability:** after column normalisation the propagated score
  is bounded by 1/(1−λ) = 1.818, so it is an exposure index. θ is defined on
  [0, 1.818], stated explicitly in `framework_parameters.yaml`.

## Eq. (12)–(13) — orchestration objective

Corrections implemented in `dtcr.orchestration`:

- Use μ1, μ2, μ3 = 0.20, 0.15, 0.25 consistently; the single-μ worked example in
  the text is labelled illustrative.
- Define every term as dimensionless in [0, 1] (residual propagated risk,
  normalised CPU and network overhead, normalised disruption).
- Replace the finite penalty P_viol with a **hard admissibility constraint**
  (`admissible`), matching Algorithm 1's rejection of policy-violating
  candidates.
- Generalise the scalar capacity constraint to a **CPU/RAM/storage/network vector
  constraint** (`ResourceVector`).
- State the solver (exhaustive enumeration over the affected subgraph),
  deterministic tie-breaking (lowest disruption, then compute overhead, then
  action name), the 2 s timeout, and the policy revalidation against live state
  immediately before enforcement.
