# Corrected equations and definitions for `Man-V3`

These edits depend only on mathematics and on the deposited implementation, not on
any measurement. They can be applied to the manuscript immediately, before the
physical campaign. Each is verified by a unit check in `../tests/test_dtcr.py`.

Notation: `p` is the telemetry feature dimension actually deployed (`p = 9` in the
deposited configuration).

---

## §2.4, Eq. (6) - anomaly statistic and threshold

**Replace the surrounding text with:**

> Validated telemetry is transformed into a feature vector `z_i(t) ∈ R^p`. A baseline
> mean `mu_i` and covariance `Sigma_i` are estimated on a designated baseline window
> that precedes, and never overlaps, the evaluation interval. To keep `Sigma_i`
> invertible and well conditioned for telemetry whose features differ by orders of
> magnitude in unit, shrinkage is applied on the **correlation** scale: the sample
> correlation matrix is shrunk towards the identity with a fixed coefficient `s`, and
> the result is rescaled by the per-feature standard deviations. Shrinking the raw
> covariance towards `tr(Sigma)/p · I` is not admissible here, because the target is
> then dominated by the largest-variance feature and the statistic collapses.
>
> The squared Mahalanobis distance is
>
>     d_i^2(t) = (z_i(t) − mu_i)^T Sigma_i^{−1} (z_i(t) − mu_i),        (6)
>
> and an asset is flagged when `d_i^2(t)` exceeds `chi^2_{p, 1−alpha}`, the
> `1 − alpha` quantile of the chi-square distribution with **`p` degrees of
> freedom**, where `p` is the feature dimension and `alpha` is the nominal
> per-sample false-positive rate. For the deployed configuration `p = 9` and
> `alpha = 0.01`, giving a threshold of 21.666. A firing requires `k` consecutive
> exceedances.

**Add as a footnote or remark:**

> Using the two-dimensional threshold `chi^2_{2, 0.99} = 9.210` on a nine-dimensional
> statistic yields an actual per-sample false-positive rate of 0.418 rather than the
> intended 0.01.

**Report alongside:** `p`, the feature list, the baseline window length, the
shrinkage coefficient, `alpha`, `k`, and the **out-of-sample** false-positive rate
measured on a clean window that was not used for calibration.

---

## §2.4, Eq. (7) - anomaly likelihood

**Replace**

    a_i(t) = 1 − exp(−d_i^2(t)/2)                                       (7)

**with**

    a_i(t) = F_{chi^2_p}(d_i^2(t)),                                     (7)

where `F_{chi^2_p}` is the chi-square cumulative distribution function with `p`
degrees of freedom.

**Justification to include:** under the null hypothesis `d_i^2 ~ chi^2_p`, so the
corrected score is uniform on `[0,1]` for every `p` and remains graded, while
tending to 1 under attack. The printed form is a two-dimensional special case: at
`p = 9` it assigns a score of 0.985 to a *median healthy* asset, so `a_i` is
effectively constant and Eq. (8) degenerates to `R_i ≈ (1 − T_i) s_i`.

---

## §2.4, Eq. (9)-(11) and §3.5 - graph risk propagation

**State the normalisation explicitly and make the worked example agree with it.**

> `W` is column-normalised: each column is divided by its sum, so the incoming
> dependency weight of every asset totals one. Columns that are entirely zero -
> assets of in-degree zero - are left at zero, so such an asset receives no
> propagated contribution and keeps `R'_i = R_i`. Eq. (10) is used only when the
> spectral radius satisfies `rho(lambda W^T) < 1`; the convergence margin
> `1 − rho(lambda W^T)` is recorded for every run.

**Table 6 must be regenerated.** As printed, its values (0.600, 0.289, 0.154, 0.114;
`kappa = 1.502`) are the **un-normalised** computation and contradict the text.
Under column normalisation the same example gives 0.600, 0.370, 0.2165, 0.1451 with
`kappa = 1.729`.

Keep Eq. (8) multiplicative, `R_i = a_i (1 − T_i) s_i`, exactly as printed - the
implementation contains no additive variant.

---

## §2.5, Eq. (12) - orchestration objective

**Replace** the absolute risk term with a relative one, so that both terms of the
objective are dimensionless:

    J(x) = [ Σ_i R'_i(t | x) / Σ_i R'_i(t | ∅) ] + μ^T O(x) + D(x),     (12)

where `∅` is the no-action baseline, `O(x) ∈ [0,1]^3` is the normalised overhead
vector over (cpu, ram, net) and `μ ∈ R^3` weights it.

**Justification to include:** as printed, the first term is an absolute sum over
assets while the remaining terms are normalised to `[0,1]`, so the balance between
them depends on the size of the dependency graph and on the incidental magnitude of
the risk vector. Measured across the deposited campaign, the ratio of the risk range
to the cost range over the candidate action set varied from 0.36 to 1.27 between
runs of the *same* deployment, with no parameter changing.

**Remove `P_viol` from the objective** - see the next item.

---

## §2.5, Eq. (13) - admissibility

**State that the constraints are hard, and vectorise capacity:**

> An action is admissible only if
>
>     Σ_j z_ij = 1,  z_ij ∈ {0,1},
>     z_ij = 1 ⟹ r_i ≼ C_j − u_j   (element-wise over cpu, ram, net),
>     z_ij = 1 ⟹ l_j ≽ l_i  and  T_j ≥ tau_i.                          (13)
>
> Inadmissible candidates are **removed from the feasible set**; they are not
> penalised inside Eq. (12). Consequently no violation term appears in the objective
> of a selected action.

If a deployment really uses a soft penalty instead, the text must stop describing
the constraint as hard and must report the penalty weight.

---

## §2.8 - metric definitions

1. **Detection.** Make the **detection rate** the primary endpoint. Report detection
   latency only as a secondary endpoint, computed over detected runs, always beside
   the number of runs in which detection did not occur. A mean detection latency is
   undefined when the comparator does not detect; dropping those runs conditions on
   the outcome and biases the comparator towards speed.

2. **Recovery.** Eq. (15) returns no value when availability never meets the
   criterion inside the observation window. Such runs are **right-censored**, and
   must be reported as censored - never deleted, never imputed to the window end.

3. **False positives.** Measure on a clean window **held out** from the window used
   to fit `mu`, `Sigma` and any rule threshold. Report the nominal rate and the
   realised out-of-sample rate side by side; they differ.

4. **Overhead.** Report each resource separately with its own numerator,
   denominator, aggregation interval and baseline. Do not combine CPU, memory and
   network into a single percentage. State whether a timing figure is a property of
   the method or a measurement of the machine that ran it.

5. **Eq. (23).** With per-run data retained, report `n`, mean ± SD, median [IQR] and
   a 95% confidence interval for every cell. For skewed time metrics prefer a
   percentile bootstrap interval to the Student-t form.

---

## Verification

Every statement above is checked by `../tests/test_dtcr.py`:

```
python3 tests/test_dtcr.py
```

The suite asserts, among other things, that `E[d^2] ≈ p`, that the threshold uses
`df = p`, that the printed Eq. (7) scores a median healthy asset above 0.98 at
`p = 9`, that Table 6 matches the un-normalised computation, that divergent `lambda`
raises rather than returning a value, and that an inadmissible candidate is removed
rather than penalised.
