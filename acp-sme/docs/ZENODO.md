# Zenodo deposition metadata

Ready-to-paste text for the Zenodo upload form. The same values are held
machine-readably in `../.zenodo.json` and `../CITATION.cff`; if you edit one, edit all
three.

---

## Title

```
ACP-SME: A Metadata-Driven Adaptive Cybersecurity Protector for SMEs — Reference Prototype and Reproduction Package
```

Shorter variant, if the record title must stay compact:

```
ACP-SME: Adaptive Cybersecurity Protector for SMEs (reference prototype and reproduction package)
```

## Upload type

Software · Version `0.1.0` · License MIT · Language English

## Abstract (description)

ACP-SME (Adaptive Cybersecurity Protector for SMEs), version 0.1, is a privacy-oriented
governance decision-support prototype that keeps a small or medium-sized enterprise's
approved cybersecurity profile current as the business itself changes. This deposit is the
reference implementation and the complete reproduction package for the article "A
Metadata-Driven Adaptive Cybersecurity Protector for SMEs in Metaverse-Enabled Ecosystems:
Resource-Aware Tailoring of NIST CSF 2.0, ISO/IEC 27001:2022, and CIS Controls v8.1".

The artifact treats an approved profile as a versioned decision object rather than a static
checklist. A minimized vector of organizational and technical metadata is processed locally;
a material change in business state is detected; a typed capability layer explains why that
change matters across three complementary standards; a constrained optimizer ranks profile
changes under a resource-unit budget and dependency constraints; and an authorized person
decides whether the baseline actually changes. Every recommendation carries its trigger,
rationale, standards provenance, expected burden, and approval or rollback path.

The package implements: the Minimum Necessary Metadata Model and its fail-closed local
metadata guard (field allowlist, banding, tenant-keyed pseudonyms, retention deadlines,
verification tasks for missing or stale evidence); a typed, directional, versioned
capability-to-standards crosswalk of 43 edges spanning NIST CSF 2.0 outcomes, ISO/IEC
27001:2022 clauses and Annex A references, and CIS Controls v8.1; a material-change detector
combining a weighted approved-profile distance, five deterministic critical predicates, a
two-of-three persistence rule, and a periodic timer; an exact resource-constrained profile
selector evaluated over all 919 dependency-valid subsets of 14 shared capabilities; a
hash-chained, replayable and rollback-capable human-authorized profile ledger with role
separation; the seeded synthetic experiment over 90 traces and 10,800 enterprise-days
comparing the adaptive loop against static and 30-day-review baselines; the
threshold-by-budget sensitivity grid; figure rendering; a worked end-to-end governance
walkthrough; and 140 tests mapped to the eight artifact requirements stated in the article.

Reproducibility. The core artifact, the full experiment, and the entire test suite run on a
bare Python 3.9+ standard-library installation with no third-party dependencies; matplotlib
is optional and needed only to render figures. A single command, "acp-sme reproduce",
regenerates every reported table, the per-trace outcome data, and the figures in seconds.
Every value produced falls inside the confidence interval reported in the article; the
documentation records the side-by-side comparison, the mechanical details the article leaves
unspecified and how each was resolved, and one documented deviation in the finite-sample
false-alert counts of the sensitivity grid.

Claims boundary. ACP-SME is a governance decision-support artifact. It is not an
anti-malware packer, vulnerability scanner, SIEM, autonomous enforcement engine, actuarial
loss model, or certification system. All results are model output over explicitly synthetic
traces: no real enterprise, employee, customer, supplier, or incident is represented, and no
confidential or personal data were used. Modeled coverage is a capability-demand index, not
a probability of avoiding an incident. Review hours are assigned accounting constants, not
observed labour. A standards reference states why a recommendation is relevant; it does not
prove conformity or certification readiness. The software cannot implement a safeguard,
change an approved profile, or accept risk — only an authorized human decision does, and the
code enforces that boundary. No ISO/IEC control text is reproduced; only identifiers and
author-generated summaries are cited, and mappings should be independently reviewed and
regression-tested before operational use.

## Additional notes

All reported results are synthetic model output. They verify internal behaviour under
encoded assumptions and do not demonstrate real-world incident reduction, standards
conformity, or certification readiness. No confidential, personal, or real-enterprise data
were used.

## Keywords

cybersecurity governance; organizational profiles; control prioritization; small and
medium-sized enterprises; SME; NIST Cybersecurity Framework 2.0; ISO/IEC 27001:2022; CIS
Controls v8.1; digital twins; extended reality; metaverse; Internet of Things; privacy by
design; data minimization; human-in-the-loop; concept drift; cyber resilience; design
science; reproducible research; synthetic data

## Related identifiers

| Relation | Identifier |
| --- | --- |
| `is supplement to` | the article DOI, once minted |
| `is supplement to` | <https://github.com/omega2417/bnt/tree/master/acp-sme> |

## Assigned DOI

`10.5281/zenodo.2220368` — recorded in `../.zenodo.json`, `../CITATION.cff` and
`AVAILABILITY.md`. Verify it resolves to this deposit before publication; see the note at
the top of `AVAILABILITY.md`. Prefer the concept DOI ("Cite all versions") over a
version-specific DOI so that later releases do not invalidate the printed citation.

## After deposition

The article's Data availability statement currently reads "available from the corresponding
author on reasonable request". Replace it with one of the ready-made blocks in
`AVAILABILITY.md`, which cite both the Zenodo DOI and the GitHub repository.
