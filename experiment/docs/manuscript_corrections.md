# Required corrections to `Man-V3`

Each correction was produced by executing the reference implementation, not by
re-reading the text. Every entry names the evidence that forces it. Where the code
and the manuscript disagree, **the code is the specification**: the manuscript must
be changed to match, because the code is what was executed and deposited.

Evidence paths are relative to `experiment/`.

---

## C1 - Mahalanobis threshold must use `df = p`, not `df = 2`

**Manuscript.** Eq. (6)-(7) define `d_i^2` over a feature vector whose dimension is
not fixed in the text, and Section 3 reports operation at a false-positive rate
below 2% without stating the degrees of freedom used for the threshold.

**Evidence.** The deployed feature vector has `p = 9`
(`protocol/preregistration.yaml: detector.features`). Executed:

| nominal FPR | `chi2_9` threshold | `chi2_2` threshold | actual FPR if the `p=2` threshold is applied to `p=9` data |
|---|---|---|---|
| 0.05 | 16.919 | 5.991 | **0.741** |
| 0.01 | 21.666 | 9.210 | **0.418** |
| 0.001 | 27.877 | 13.816 | **0.129** |

**Correction.** State `p` explicitly, set the threshold to the `1 - alpha` quantile of
`chi^2_p`, and report the estimator of `mu` and `Sigma` and the baseline window.
Audit check `parameters/chi2-threshold-uses-p-9` fails the build otherwise.

---

## C2 - Eq. (7) is a `p = 2` formula and saturates at the dimension actually used

**Manuscript.** `a_i(t) = 1 - exp(-d_i^2(t)/2)`, presented as a general bounded
anomaly likelihood.

**Evidence.** Under the null `d^2 ~ chi^2_p`, so the score of a **median healthy
asset** is:

| p | median `d^2` | Eq. (7) score | `F_{chi2_p}(d^2)` |
|---|---|---|---|
| 2 | 1.39 | 0.500 | 0.500 |
| 4 | 3.36 | 0.813 | 0.500 |
| 9 | 8.34 | **0.985** | 0.500 |

At `p = 9` the mapping returns ≥ 0.985 for a perfectly healthy asset, so `a_i` is
constant in practice and Eq. (8) degenerates to `R_i ≈ (1 - T_i) s_i`. The exact
agreement at `p = 2` shows the transform was derived for two dimensions.

**Correction.** Replace Eq. (7) with `a_i(t) = F_{chi^2_p}(d_i^2(t))`, which is
uniform on `[0,1]` under the null for every `p`. Implemented as
`dtcr.anomaly.anomaly_likelihood_chi2`; the printed form is retained as
`anomaly_likelihood` **only** so that the old text can be reproduced.

---

## C3 - Table 6 contradicts the claimed column normalisation of `W`

**Manuscript.** Section 2.9 states "column-normalized dependency-graph risk
propagation". Table 6 reports, for the four-node example with weights
0.70/0.80/0.40/0.60, `lambda = 0.45` and `R = (0.60, 0.10, 0.05, 0.02)`, the
propagated vector `(0.600, 0.289, 0.154, 0.114)` and `kappa = 1.502`.

**Evidence.** Re-executed with `dtcr.graph_risk.propagate`:

| variant | propagated risk | `kappa` |
|---|---|---|
| raw (un-normalised) `W` | 0.600, 0.289, 0.154, 0.1136 | 1.502 |
| column-normalised `W` | 0.600, 0.370, 0.2165, 0.1451 | 1.729 |

Table 6 is the **un-normalised** computation. The text and the table describe two
different models.

**Correction.** Choose one, state it, and regenerate the table from the code.
This deposit uses column normalisation, leaves zero columns (in-degree 0) at zero,
and reports the spectral radius and convergence margin per run.

---

## C4 - Eq. (12) is dimensionally inconsistent

**Manuscript.** `J(x) = sum_i R'_i(t|x) + mu_1 O_cpu + mu_2 O_net + mu_3 D + P_viol`.
The first term is an **absolute** sum over assets; the remaining terms are
normalised to `[0,1]`.

**Evidence.** The balance between the two terms therefore depends on the size of the
graph and on the incidental magnitude of the risk vector. Measured across the pilot
worlds (`analysis/pilot_report.json: eq12_scale_diagnostic`), the ratio of the risk
range to the cost range over the candidate action set was median 0.94 but varied
from **0.36 to 1.27** between runs of the *same* deployment - a factor of 3.5 swing
in which term decides the action, with no parameter changing.

**Correction.** Normalise the risk term by the pre-action level, so that both terms
are dimensionless; state `mu` per resource dimension. Implemented in
`harness/runner.py: twin_risk`.

---

## C5 - Eq. (13) constraints must be hard, and capacity is a vector

**Manuscript.** Eq. (13) writes admissibility as constraints, but Eq. (12) also
carries a penalty term `P_viol`, so the text does not settle whether an
inadmissible action is *removed* or merely *discouraged*. Capacity appears as a
scalar `C_j`.

**Correction.** `dtcr.orchestrator.Orchestrator.evaluate` removes inadmissible
candidates from the feasible set; `P_viol` never enters the objective of a selected
action and is retained only as a diagnostic. Capacity, demand and overhead are
vectors over `(cpu, ram, net)`. If a deployment really uses a penalty, the text must
stop calling the constraint hard.

---

## C6 - A mean detection latency is undefined when the baseline does not detect

**Manuscript.** "mean detection latency decreased from 43.1 to 8.5 s", over
20 repetitions per scenario, with no censoring statement.

**Evidence.** In the executed campaign the IDS-plus-manual baseline (A0) detected in
**2 of 54** runs of S1 and **0 of 54** runs of S2 and S4. A mean over the baseline is
not estimable in three of the four scenarios; any single reported number must have
either dropped those runs (which conditions on the outcome and biases the baseline
*towards speed*) or imputed them.

**Correction.** Make **detection rate** the primary endpoint, report detection
latency as a secondary endpoint **among detected runs only**, and print the censored
count next to every latency figure. `analysis/analyze.py` refuses to compute an
effect size on fewer than five complete pairs.

---

## C7 - Overhead is not a single percentage

**Manuscript.** "orchestration overhead remained below 6%", combining CPU and memory.

**Evidence.** The measured costs do not share a denominator and move in opposite
directions between arms: orchestration CPU per decision rose from
~0.13 ms (A0) to ~0.9-1.0 ms (A5), a factor of **5.5-9.0** depending on machine
load, while the out-of-sample
false-positive rate rose from 1.29% to 1.90% (+0.61 pp).

**Correction.** Report each cost with its own numerator, denominator, aggregation
interval and baseline. Do not aggregate CPU, RAM and network into one percentage.

---

## C8 - Shrinkage must be applied on the correlation scale

**Not a manuscript equation, but a defect any re-implementation will hit.**
Shrinking the raw covariance towards `trace(Sigma)/p * I` is unusable when telemetry
features differ by orders of magnitude in unit. Measured on the pilot: the
raw-covariance variant gave `E[d^2] = 1.54` against the correct `p = 9`, i.e. the
detector was blind. Shrinking the **correlation** matrix and rescaling by the
per-feature SD restores `E[d^2] = 8.46`.

---

## C9 - The testbed described in Man-V3 is not the UMSF cyber range

**Manuscript.** Table 2 describes 4 x Raspberry Pi 5, K3s v1.30, Kubernetes v1.30,
Eclipse Ditto 3.5, Suricata 7.0, Mosquitto 2.0, Prometheus/Grafana and a Kali
attacker host.

**Cyber-range description.** Keenetic Titan / Viva edge routers, UniFi CloudKey
Gen1/Gen2 with 54 access points, EcoFlow plus a **projected** 48 V DC circuit, and a
25-seat Kali Linux classroom. The document itself separates the base configuration
from a *recommended* neural/energy superstructure that "should be implemented and
verified before the publication asserts its actual operation".

**Correction.** These are two different facilities. Until an inventory act exists
(Gate 1), no component of Table 2 may be described as deployed. See
`inventory/inventory_status.md`.

---

## C10 - The cited development repository does not show the article's code

**Manuscript.** Data Availability names `https://github.com/omega2417/bnt` as the
development repository for the `dtcr` library.

**Evidence.** The default branch of that repository is a fork of the **Bayes Net
Toolbox for MATLAB** (`BNT/`, `KPMstats/`, `netlab3.3/`, `bntRoot.m`,
`ChangeLog.Sourceforge.txt`). A reader following the link lands on unrelated MATLAB
code and finds no `dtcr` package. This is exactly the failure mode the review
protocol flags in section 17.

**Correction.** Publish the article's code where the link points - as this deposit
does, under `experiment/` - or change the link. Verify with a signed-out browser
before submission.
