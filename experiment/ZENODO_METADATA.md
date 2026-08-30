# Zenodo deposit metadata

Fill the record with the fields below. **Do not publish the record until
`analysis/audit_provenance.py` exits 0** — the archive is built by
`analysis/make_zenodo_archive.sh`, which refuses to package a failing audit.

## Title

DTCR: reference implementation, frozen protocol and software-in-the-loop evaluation
of a digital-twin cyber-resilience framework (UMSF cyber range)

## Version

`2.0.0-experiment`

## Upload type / resource type

Software (with the dataset and documentation included in the same archive).

## Description (paste as-is)

> Reproducibility deposit for the manuscript *Digital-Twin-Enabled Cyber-Resilience
> Framework for Secure Edge-Cloud Orchestration and Data Integrity in Distributed
> Smart-Region Infrastructure*.
>
> **The physical experiment on the UMSF laboratory cyber range has not been
> performed.** Gate 0 (authorization, isolation and safety) is unsigned and Gate 1
> (inventory) is not complete, so this deposit contains no measurement of physical
> hardware. `data/real/` is empty on purpose.
>
> The deposit contains: (1) `dtcr`, a reference implementation of every equation of
> the framework; (2) a frozen pre-registration with hypotheses, randomisation plan
> and a power analysis that fixes the confirmatory sample size at 54 repetitions per
> cell; (3) a 1296-run software-in-the-loop confirmatory campaign (6 configurations
> x 4 scenarios x 54 repetitions, blocked by seed, 0 exclusions, 318 right-censored
> runs), with per-run evidence bundles and SHA-256 manifests; (4) a full statistical
> analysis with bootstrap confidence intervals, effect sizes, Holm correction,
> censoring accounting and sensitivity analysis; (5) an automatic provenance and
> consistency audit of 23 checks; and (6) a documented set of ten reproducible
> defects in the manuscript's mathematics and reporting.
>
> Every deposited run carries `data_origin = simulation`. None of it may be
> presented as a physical-testbed result. The whole deposit regenerates
> deterministically in about two minutes via `bash analysis/reproduce.sh`.

## Keywords

digital twin; cyber resilience; edge-cloud orchestration; data integrity; anomaly
detection; Mahalanobis distance; dependency-risk propagation; policy-constrained
orchestration; pre-registration; reproducibility; software-in-the-loop; cyber range

## Licences

- Software: MIT
- Dataset, figures and documentation: CC BY 4.0

## Related identifiers

- `isSupplementTo` — the manuscript DOI, once assigned
- `isNewVersionOf` — `10.5281/zenodo.22179426` (the previous release, whose data
  directory held a synthetic reference dataset that is **not** carried forward)

## Contributors

Replace the placeholder author in `CITATION.cff` with the individual authors, their
ORCIDs and CRediT roles before publishing.

## After publication

1. Record the **version DOI** (not the concept DOI) in `CITATION.cff` and in the
   manuscript's Data Availability statement, with the access date.
2. Verify in a signed-out browser that the repository link in the manuscript shows
   this code and not an unrelated default branch (defect C10).
