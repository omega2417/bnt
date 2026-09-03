# Ready-to-paste manuscript text

Every snippet below must use the DOI of the **published version** of the Zenodo
record. Replace `[ZENODO-DOI]` and every other bracketed field with real values
only. Related manuscript: *Provenance-Aware Cyber-Range Modelling for Critical
Infrastructure: A Set-Theoretic Resilience Framework and Reproducible Synthetic
Evaluation* (working title; the earlier title claiming a controlled two-site
cyber-range evaluation should not be used while the evidence is SIM-only).

## Data Availability Statement

> The software, scenario configurations, seed policy, synthetic telemetry,
> scenario-generated ground truth, alerts, summaries, manifests, tests, and
> analysis scripts supporting this study are available in Zenodo at
> https://doi.org/[ZENODO-DOI]. All numerical records in this repository are
> synthetic outputs of the SIM-mode software model; the repository contains no
> measurements from the physical UMSF cyber range. The archived release used for
> this article is version 2.0.0.

Українською:

> Програмне забезпечення, конфігурації сценаріїв, seed-політика, синтетична
> телеметрія, сформований сценарним контролером ground truth, alerts, summaries,
> manifests, тести та скрипти аналізу, що підтримують це дослідження, доступні в
> Zenodo за адресою https://doi.org/[ZENODO-DOI]. Усі числові записи репозиторію
> є синтетичними виходами програмної моделі в режимі SIM; репозиторій не містить
> вимірювань фізичного кіберполігону УМСФ. У статті використано архівну версію
> 2.0.0.

## Code Availability

> The executable software artifact and the exact configurations used in the
> reported SIM campaign are archived in Zenodo (version 2.0.0):
> https://doi.org/[ZENODO-DOI]. The archive includes reproducibility
> instructions, automated tests, environment information, and SHA-256 manifests.

## Supplementary Materials

> Supplementary reproducibility materials are available in Zenodo at
> https://doi.org/[ZENODO-DOI]. The deposit contains the versioned software
> package, five executed SIM scenarios, a three-replicate demonstration run, an
> eight-point exploratory DoE, a demonstration Monte Carlo workflow,
> machine-readable outputs, data dictionaries, and integrity manifests.

## Methods — study design and reproducibility

> This study is a computational, pre-experimental investigation and a
> reproducibility check of a modular software prototype of a cyber-range digital
> twin. The experimental part was executed exclusively in SIM mode; all numerical
> outputs were produced by the software model. The work separates verification of
> the implementation from validation against a physical system throughout.
>
> All experiments reported in this section were executed in SIM mode using
> software release 2.0.0 and base seed 20260903. The unit of analysis was a
> software run/replicate rather than an individual telemetry row. Each run
> produced a resolved scenario configuration, telemetry, scenario-generated ground
> truth, alerts, summary metrics, and a manifest containing configuration, source,
> environment, and file hashes. The archived artifact is available at
> https://doi.org/[ZENODO-DOI].

## Methods — remote organisation of the work

> Because of the security and logistical constraints of martial law and the
> full-scale armed aggression of the Russian Federation against Ukraine, the
> preparation of configurations, the entry of model parameters, the execution of
> SIM runs and the analysis of artifacts were carried out remotely. Remote entry
> of configuration parameters is a way of organising software work; it is not a
> source of physical measurements. Any value not confirmed by physical
> inventory, by a device datasheet or by real telemetry retained the status
> SYNTHETIC_DEMO or UNKNOWN.

## Results — evidence boundary

> The archived campaign passed 40/40 automated software checks and reproduced
> 86/86 enumerated behavioural reference values of the executable specification.
> These results demonstrate internal software verification and reproducibility
> relative to that specification. They do not constitute calibration or validation
> against the physical UMSF cyber range.

## Limitations

> The Zenodo deposit contains synthetic SIM-mode outputs only. No parameter in
> the reported inventory is classified as MEASURED; 194 parameters are
> SYNTHETIC_DEMO and four are UNKNOWN. EMU, replay of real telemetry, HIL,
> passive physical baselining, and independent sim-to-real validation were
> outside the scope of this release. Consequently, the archived metrics must not
> be interpreted as field performance of the physical network, Wi-Fi, VPN,
> backup-power system, or detectors.

## Generative-AI disclosure

> Generative AI was used for language editing, text structuring and drafting of
> program code. The author verified the methodology, the implementation, the
> provenance of the data and every claim, and takes full responsibility for the
> content.

## Citation of the archive

> Prokopovych-Tkachenko, D., [further authors]. (2026). *UMSF Cyber-Range Digital
> Twin: Reproducible SIM Experiment, Synthetic Telemetry, and Provenance-Aware
> Verification Package* (Version 2.0.0) [Software]. Zenodo.
> https://doi.org/[ZENODO-DOI]

After publication, copy the citation directly from the Zenodo record page and
check author order, year, resource type, version and DOI.

## Related identifiers to declare in Zenodo

| Object | Relation | When to fill |
|---|---|---|
| The article | *Is supplement to* / *Is referenced by* — pick the semantically exact one | after the article DOI exists, or at a later metadata update |
| A previous package version | *Is new version of* | only if a previous published record exists |
| The executable specification | *Is derived from* / *Is documented by* | if it has a stable DOI or URL |
| A separate dataset record | *Is supplement to* / *Is part of* | only if code and data are split into two records |
