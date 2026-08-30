# Вставка в публікацію `Man-V3`

Готовий до вставки текст англійською (стиль *Electronics*) із редакційними
примітками українською про місце кожного блоку.

**Депозит:** <https://doi.org/10.5281/zenodo.22181264> · версія `2.0.0-experiment`

> ⚠ **Перед подачею перевірити вручну.** У середовищі, де готувався цей текст,
> вихід у мережу до `doi.org` і `zenodo.org` заблоковано, тому DOI **не було
> перевірено автоматично**. Відкрийте посилання в браузері без авторизації і
> звірте: назву, версію `2.0.0-experiment`, авторів, ліцензії (MIT + CC BY 4.0)
> і те, що це **version DOI**, а не concept DOI. Якщо `10.5281/zenodo.22181264`
> виявиться concept DOI (посилання «all versions»), у статті треба вказати саме
> version DOI конкретного релізу.

---

## Блок 1 — замінює §2.9 «Software Implementation and Reproducibility»

> ### 2.9. Software Implementation, Data and Reproducibility
>
> A reference implementation of the framework, the complete analysis pipeline and
> the verification dataset are openly available in Zenodo at
> https://doi.org/10.5281/zenodo.22181264 (version 2.0.0-experiment) [33]. The
> `dtcr` Python library implements each block of the mathematical model as a
> separate module: probabilistic block auditing (Equations (4) and (5));
> provenance-aware dynamic trust (Equations (2) and (3)); Mahalanobis-distance
> anomaly scoring with chi-square calibration at the deployed feature dimension
> (Equations (6) and (7)); column-normalised dependency-graph risk propagation
> with an explicit spectral-radius and convergence-margin check (Equations
> (8)–(11)); policy-constrained orchestration with hard admissibility constraints
> and a vector-valued capacity limit (Equations (12) and (13)); and the
> RTO-bounded normalized resilience index (Equations (15), (18) and (19)).
>
> The deposit separates data by origin into `real/`, `pilot/`, `simulation/` and
> `synthetic/` directories. Each run record carries an explicit `data_origin`
> field, and an automated provenance audit fails the build if a record of one
> origin is used to support a claim about another. The `real/` directory is empty:
> the framework has not yet been evaluated on physical infrastructure, and no
> value reported in this paper as a hardware measurement may be traced to the
> deposit until that campaign is complete.
>
> The deposit further contains the frozen pre-registration, the hypotheses, the
> randomisation plan, the per-run evidence bundles with SHA-256 digests, a data
> dictionary, the environment lock file, and 37 unit checks of the mathematical
> modules. The whole analysis, including every figure, regenerates
> deterministically from the run table with a single documented command
> (`bash analysis/reproduce.sh`); two independent executions are bit-identical.
> Applying the same pipeline to new measurements requires only that they be placed
> in the documented schema; no analysis code changes.

*Примітка.* Стару фразу про «executable Google Colab notebook» і про
«K3s, Kubernetes, Suricata and Eclipse Ditto configurations» вилучити — ці
компоненти не розгорталися й не підтверджені інвентаризацією.

---

## Блок 2 — нова §2.10 «Implementation Verification Campaign»

*(стару §2.10 «Use of Generative Artificial Intelligence» перенумерувати на §2.11)*

> ### 2.10. Implementation Verification Campaign
>
> Before any deployment on physical infrastructure, the implementation was
> subjected to a pre-registered software-in-the-loop (SIL) verification campaign.
> Its purpose is narrow and should not be mistaken for an evaluation of the
> framework in operation: it establishes that each mechanism behaves as the model
> specifies, that the mechanisms are separable, and that the analysis pipeline is
> reproducible. It does **not** measure hardware, network or operator behaviour.
>
> The protocol, hypotheses, primary endpoints, exclusion rules, randomisation plan
> and parameter values were frozen before the confirmatory series was executed and
> are deposited unchanged. Telemetry was generated as a nine-dimensional stream
> over a twenty-asset dependency graph comprising twelve sensors, four edge nodes,
> three cloud nodes and one civil service. Four incident scenarios were injected:
> compromise of an edge node with a resource and sequencing signature but no
> traffic signature (S1); telemetry integrity violation by injection, replacement
> and replay, in which tampered records are drawn from the node's own baseline
> window and are therefore statistically indistinguishable by construction (S2); a
> rate-limited volumetric disruption with a strong traffic signature (S3); and a
> placement request violating one randomly selected admissibility dimension, with
> no telemetry signature at all (S4). Ground truth is written by the injector and
> never derived from detector output.
>
> Six configurations were compared: an intrusion-detection system with manual
> response (A0); an intrusion-detection system with an automated playbook and no
> twin (A1); a twin with automated response but without trust, provenance or
> graph-based what-if analysis (A2); the full system without integrity, trust and
> provenance (A3); the full system without graph risk propagation and what-if
> planning (A4); and the full proposed system (A5). All configurations observe the
> same telemetry, the same injected ground truth, the same resources and the same
> candidate action set; they differ only in which mechanisms are enabled, and no
> configuration-specific latency or accuracy constant exists anywhere in the code.
>
> The design is blocked: the scenario and repetition index fix the random seed, so
> every configuration observes an identical realisation and every comparison is
> paired. A pilot of five repetitions per cell was used to estimate variance and
> to size the confirmatory series; a power analysis for a minimum practically
> relevant effect of 25 percentage points for proportions and 15 s for times, at
> alpha = 0.05 and 80% power, fixed the confirmatory sample at 54 repetitions per
> cell, giving 1296 runs. Detector thresholds were calibrated on a 240 s baseline
> window, and false positives were measured on a separate 60 s clean window that
> was never used for calibration.
>
> Primary endpoints are detection rate, containment latency, policy-violation
> rate, out-of-sample false-positive rate and what-if prediction error. Detection
> rate rather than mean detection latency is primary because a mean latency is not
> estimable when the comparator does not detect at all. Runs in which detection,
> containment or restoration did not occur inside the observation window are
> right-censored and reported as censored; they are never deleted and never
> imputed. Proportions are reported as risk differences with Newcombe intervals,
> continuous outcomes with percentile-bootstrap intervals, Hedges' g and Cliff's
> delta, and the hypothesis family is corrected by the Holm procedure. Effect
> sizes are not reported for cells with fewer than five complete pairs.
> Scenarios are never averaged into a single figure.

---

## Блок 2b — виправлення рівнянь у Methods

*Вставити в §2.4 після Рів. (6):*

> The detection threshold is the (1 − alpha) quantile of the chi-square
> distribution with p degrees of freedom, where p is the deployed feature
> dimension. For the configuration evaluated here p = 9 and alpha = 0.01, giving a
> threshold of 21.666. The mean and covariance are estimated on a designated
> baseline window that never overlaps the evaluation interval; shrinkage is
> applied on the correlation scale and rescaled by the per-feature standard
> deviations, because shrinking the raw covariance towards a scaled identity is
> not admissible for telemetry whose features differ by orders of magnitude in
> unit. A detection requires k = 3 consecutive exceedances.

*Замінити Рів. (7):*

> a_i(t) = F_{chi^2_p}(d_i^2(t)),
>
> where F_{chi^2_p} is the chi-square cumulative distribution function with p
> degrees of freedom. Under the null hypothesis d_i^2 follows chi^2_p, so this
> score is uniform on [0,1] for every p and remains graded as the dimension grows.

*Вставити в §2.4 після Рів. (11):*

> W is column-normalised, so the incoming dependency weight of every asset totals
> one; columns that are entirely zero, corresponding to assets of in-degree zero,
> are left at zero, and such assets keep R'_i = R_i. Equation (10) is used only
> when rho(lambda W^T) < 1, and the convergence margin is recorded for every run.

*Замінити ризиковий доданок у Рів. (12) і додати:*

> The risk term is expressed relative to the no-action level, so that both terms
> of the objective are dimensionless. An absolute risk sum compared against
> normalised costs makes the balance between the two terms depend on the size of
> the dependency graph and on the incidental magnitude of the risk vector.

*Вставити після Рів. (13):*

> Inadmissible candidates are removed from the feasible set; they are not
> penalised inside the objective, and consequently no violation term appears in
> the objective of a selected action. Capacity, demand and overhead are vectors
> over the compute, memory and network dimensions, and the capacity comparison is
> element-wise.

*Примітка.* Table 6 і §3.5 перерахувати з нормалізованою `W`: значення в поточній
таблиці (0.600, 0.289, 0.154, 0.114; κ = 1.502) відповідають **не**нормалізованій
матриці і суперечать тексту §2.9. З нормалізацією: 0.600, 0.370, 0.2165, 0.1451;
κ = 1.729.

---

## Блок 3 — нова §3.7 «Results of the implementation verification campaign»

> ### 3.7. Results of the Implementation Verification Campaign
>
> The confirmatory series comprised 1296 runs across 24 cells at 54 repetitions
> per cell, with no run excluded and 318 runs right-censored on service
> restoration. All values in this subsection carry `data_origin = simulation` and
> describe the behaviour of the implemented mechanisms, not of physical
> infrastructure.
>
> **Table N.** Detection and containment rate by scenario and configuration
> (n = 54 per cell). Risk differences are A5 minus A0 with 95% Newcombe intervals;
> the Holm-adjusted p-value for the family is below 1e-11.
>
> | Scenario | Detection A0 | Detection A5 | Risk difference [95% CI] | Containment A0 | Containment A5 |
> |---|---|---|---|---|---|
> | S1 edge compromise | 0.037 | 1.000 | +0.963 [0.852, 0.990] | 0.037 | 1.000 |
> | S2 telemetry integrity | 0.000 | 1.000 | +1.000 [0.906, 1.000] | 0.000 | 1.000 |
> | S3 volumetric disruption | 1.000 | 1.000 | +0.000 [−0.066, 0.066] | 1.000 | 1.000 |
> | S4 placement violation | 0.000 | 1.000 | +1.000 [0.906, 1.000] | 1.000 | 1.000 |
>
> The advantage of the full configuration arises precisely where network traffic
> remains within normal variation. Under a purely volumetric disruption the
> traffic-only detector is not outperformed: both configurations detect with a
> median latency of 5.5 s, and the risk difference is indistinguishable from zero.
> This null result is reported as observed.
>
> Integrity and provenance evidence is the only mechanism able to expose replayed
> telemetry. In S2 the configuration without that layer (A3) detected in 5.6% of
> runs against 100% for the full system, a risk difference of +0.944
> [0.828, 0.981], Holm-adjusted p = 3.7e-12.
>
> Hard admissibility constraints reduced the policy-violation rate in S4
> monotonically with the number of implemented constraint dimensions: 1.000 for
> A0 and A1, which implement none; 0.667 for A2, which checks capacity only;
> 0.426 for A3, which adds the security label; and 0.000 for A4 and A5, which
> check host trust as well. The A2-to-A5 risk difference is −0.667
> [−0.778, −0.518], Holm-adjusted p = 2.0e-09.
>
> Graph risk propagation improved localisation of the true impacted asset set.
> Recall rose from 0.417 to 0.717 in S1 (difference +0.300 [0.224, 0.376]), from
> 0.444 to 0.519 in S3 (+0.075 [0.037, 0.119]) and from 0.383 to 0.457 in S4
> (+0.074 [0.037, 0.115]); in S2, where the compromised asset is a leaf sensor
> whose cascade is too weak to cross the threshold, no benefit was observed
> (+0.004 [−0.006, 0.012], p = 0.56). What-if prediction error against the
> realised relative residual risk averaged 0.0495 [0.0438, 0.0557] for the full
> system, within the pre-set tolerance of 0.10, against 0.206 and 0.216 in S1 and
> S3 for the configuration lacking trust and provenance evidence.
>
> Two limits of the campaign must be stated with the results. First, containment
> latency is not comparable in S1 and S2, because the playbook configuration fails
> to contain the incident in 52 and 54 of 54 runs respectively; the meaningful
> contrast there is the containment rate, not a latency. Second, the mechanisms
> improved state estimation and policy enforcement but did not measurably improve
> action ranking: the truly optimal action was selected in almost every run by
> every configuration, so no benefit of what-if planning to action selection could
> be demonstrated in this environment.
>
> The added detection layer carries a measurable cost. The out-of-sample
> per-sample false-positive rate rose from 1.29% to 1.90%, an increase of 0.61
> percentage points [0.56, 0.64]. This is statistically significant and within the
> pre-set non-inferiority margin of 2 percentage points; non-inferiority is
> therefore supported, and equivalence is not claimed. Both configurations exceed
> the 1% nominal rate, indicating that the chi-square threshold is
> anti-conservative at a finite baseline length. Orchestration cost, measured as
> processor time per decision, was five to seven times higher for the
> configurations performing graph propagation and what-if evaluation (ratios of
> 5.45 to 7.18 over five independent executions of the campaign). This is a
> property of the machine that executed the code, not of the method, and is
> reported as a range rather than as a single figure or as a fraction of cluster
> capacity.

*Примітка.* Разом із цією підсекцією **вилучити** з §3.1–§3.3, Table 4, Fig. 5,
Fig. 6, анотації та висновків числа `43.1 s`, `8.5 s`, `399 s`, `122 s`, `0.71`,
`0.93`, `98.7%`, `<6%` — вони не відтворені й не мають трасування до первинних
даних. Повне рішення щодо кожного — у файлі
`docs/issue_evidence_correction_matrix.md` депозиту.

---

## Блок 4 — доповнення до §4.3 «Threats to Validity»

> The evaluation reported in Section 3.7 is a software-in-the-loop verification of
> the implementation, not a field evaluation. Telemetry was generated from a
> multivariate normal model; real telemetry exhibits drift, seasonality, heavy
> tails and heteroscedasticity, under which the performance of a Mahalanobis
> detector will differ and is likely to degrade. Roughly half of the timing
> quantities are declared model assumptions rather than measurements: actuation
> latency, operator response, degradation depth and the recovery ramp are
> constants of the harness, and the deposit labels every metric with its
> provenance class accordingly. The endogenous quantities, which do measure the
> method, are the detection and containment rates, the out-of-sample false
> positive rate, the what-if prediction error, impact-set recall, the
> policy-violation rate and the measured orchestration cost.
>
> The dependency graph used is acyclic, so the spectral radius is zero and the
> convergence condition of Equation (10) holds trivially; a real graph containing
> feedback may approach the limit, and this was not exercised. The manual
> configuration is modelled rather than staffed, so no claim is made about human
> operator behaviour. A single topology of twenty assets, a single injection
> intensity per scenario, and no adaptive, multi-stage or insider adversary were
> considered, and attacks against the twin itself remain out of scope.

---

## Блок 5 — Data Availability і Code Availability

> **Data Availability Statement.** The reference implementation, the frozen
> experimental protocol, the verification dataset, the analysis pipeline and all
> figures are openly available in Zenodo at
> https://doi.org/10.5281/zenodo.22181264 (version 2.0.0-experiment, accessed on
> [DD Month 2026]) [33]. The deposit contains 1296 verification runs with per-run
> evidence bundles and SHA-256 digests. Every record is labelled by data origin;
> all deposited runs are software-in-the-loop and none is a measurement of
> physical infrastructure. The `real/` directory is reserved for the field
> campaign and is empty. Code and configuration are released under the MIT
> License; data, figures and documentation under CC BY 4.0.
>
> **Code Availability Statement.** The `dtcr` library, the experiment harness, the
> analysis pipeline, the unit tests and the provenance audit are included in the
> deposit cited above and released under the MIT License. The complete analysis,
> including every reported figure, is regenerated by a single documented command.

*Примітка.* Стару фразу «The data directory of the current release contains a
synthetic reference dataset…» вилучити повністю: синтетичний набір у цю версію не
переноситься. Дату доступу проставити після перевірки посилання в браузері.

---

## Блок 6 — джерело [33]

> 33. DTCR: Digital-Twin Cyber-Resilience Framework — Reference Implementation,
>     Pre-Registered Protocol and Software-in-the-Loop Evaluation, version
>     2.0.0-experiment; Zenodo, 2026. https://doi.org/10.5281/zenodo.22181264

*Примітка.* Звірити назву з фактичним записом Zenodo — у списку літератури має
стояти саме та назва, що на сторінці запису.

---

## Блок 7 — заява про генеративний ШІ (§2.11)

> During the preparation of this work the authors used Claude (Anthropic) and
> ChatGPT (OpenAI) for language editing, for assistance with mathematical
> exposition, and for implementing and executing the software-in-the-loop
> verification campaign and its analysis pipeline reported in Sections 2.10 and
> 3.7. The design of that campaign, its pre-registration, its hypotheses and the
> interpretation of its results are the authors'. No experimental observation
> attributed to physical infrastructure, and no bibliographic reference, was
> generated by these tools. All outputs were reviewed and verified against the
> deposited code and data, and the authors take full responsibility for the
> content of this publication.

---

## Що ця вставка **не** дозволяє стверджувати

1. Що систему перевірено на реальному обладнанні. Не перевірено.
2. Що числа §3.7 стосуються кіберполігону. Вони стосуються реалізації.
3. Що заявлені в Table 2 компоненти (Raspberry Pi, K3s, Kubernetes, Eclipse
   Ditto, Suricata, Mosquitto, Prometheus) розгорнуто. Інвентаризації немає —
   §2.6 переписати за фактичним актом або вилучити ці рядки.
4. Що NRI 0.694 → 0.938 із симуляції підтверджує заявлені 0.71 → 0.93. Це збіг
   двох різних величин: одна декларована модель доступності, друга — непідтверджене
   вимірювання.

Порядок робіт для повної кампанії — `manuscript/README.md`; повний перелік
виправлень із доказами — `docs/manuscript_corrections.md`.
