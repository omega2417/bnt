# Availability blocks — ready-to-paste Markdown

Canonical links for this project. Edit them here and copy from here, so the article, the
README and the deposit metadata cannot drift apart.

| Resource | URL |
| --- | --- |
| Zenodo record (DOI) | <https://doi.org/10.5281/zenodo.2220368> |
| GitHub repository | <https://github.com/omega2417/bnt> |
| Project directory | <https://github.com/omega2417/bnt/tree/master/acp-sme> |
| Permalink to the reviewed commit | <https://github.com/omega2417/bnt/tree/6ce47dbffabf0219dc796476e2c4018815ba16e5/acp-sme> |

> **Before publishing, confirm the DOI resolves to this deposit.** Zenodo record identifiers
> are assigned sequentially, and `2220368` is in the range Zenodo issued in late 2018, so it
> is unlikely to belong to a record created for this software. If the DOI shown above opens
> a different record, replace it everywhere it appears: in this file, in `../README.md`, in
> `../CITATION.cff`, and in the article's Data availability statement.
>
> Prefer the **concept DOI** (the "Cite all versions" DOI on the Zenodo record page) rather
> than a version DOI. A concept DOI always resolves to the newest version, so a later
> release of the software does not invalidate the citation printed in the article.

---

## 1. Data availability statement — for the article

Replace the current statement ("available from the corresponding author on reasonable
request") with this:

```markdown
**Data availability statement:** All scenario definitions, parameters, aggregate results and
reproducibility details required to interpret the synthetic experiment are reported in the
article and Appendix A. The executable Python prototype, the machine-readable synthetic
outputs and the complete reproduction package are openly available on Zenodo at
<https://doi.org/10.5281/zenodo.2220368> and are developed at
<https://github.com/omega2417/bnt/tree/master/acp-sme>. A single command, `acp-sme
reproduce`, regenerates every reported table and figure. No confidential, personal or
real-enterprise data were used.
```

### Shorter variant

```markdown
**Data availability statement:** The executable prototype, the synthetic outputs and the full
reproduction package are openly available on Zenodo
(<https://doi.org/10.5281/zenodo.2220368>) and on GitHub
(<https://github.com/omega2417/bnt/tree/master/acp-sme>). All scenario definitions and
parameters are additionally reported in Appendix A. No confidential, personal or
real-enterprise data were used.
```

### Plain-text variant, for journals that do not accept Markdown

```
Data availability statement: All scenario definitions, parameters, aggregate results and
reproducibility details required to interpret the synthetic experiment are reported in the
article and Appendix A. The executable Python prototype, the machine-readable synthetic
outputs and the complete reproduction package are openly available on Zenodo at
https://doi.org/10.5281/zenodo.2220368 and are developed at
https://github.com/omega2417/bnt/tree/master/acp-sme. No confidential, personal or
real-enterprise data were used.
```

---

## 2. Software availability section — for the article or a supplement

```markdown
### Software availability

**Name:** ACP-SME — Adaptive Cybersecurity Protector for SMEs, version 0.1.0
**Archived version (citable):** <https://doi.org/10.5281/zenodo.2220368>
**Development repository:** <https://github.com/omega2417/bnt/tree/master/acp-sme>
**License:** MIT (source code); CC BY 4.0 (documentation and figures)
**Requirements:** Python 3.9 or newer; no third-party dependencies. `matplotlib` is optional
and required only to render figures.
**Reproduce every reported result:**

```bash
python -m pip install -e ".[figures]"
acp-sme reproduce
```

All outputs are synthetic model results. They verify internal behaviour under encoded
assumptions and demonstrate neither real-world incident reduction, nor standards conformity,
nor certification readiness.
```

---

## 3. README header — badges

```markdown
[![DOI](https://zenodo.org/badge/DOI/10.5281/zenodo.2220368.svg)](https://doi.org/10.5281/zenodo.2220368)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.9+](https://img.shields.io/badge/python-3.9%2B-blue.svg)](https://www.python.org/downloads/)
[![Dependencies: none](https://img.shields.io/badge/dependencies-none-brightgreen.svg)](#requirements)
```

---

## 4. README availability section

```markdown
## Availability

| | |
| --- | --- |
| Archived release (citable) | [10.5281/zenodo.2220368](https://doi.org/10.5281/zenodo.2220368) |
| Development repository | [github.com/omega2417/bnt](https://github.com/omega2417/bnt/tree/master/acp-sme) |
| License | MIT (code), CC BY 4.0 (docs and figures) |

The Zenodo record is the archived, citable snapshot; GitHub carries ongoing development.
Cite the DOI in publications.
```

---

## 5. Citation block

```markdown
## Citation

If you use this software, please cite both the article and the software record.

**Software:**

> Prokopovych-Tkachenko, D. (2026). *ACP-SME: A Metadata-Driven Adaptive Cybersecurity
> Protector for SMEs — Reference Prototype and Reproduction Package* (Version 0.1.0)
> [Computer software]. Zenodo. https://doi.org/10.5281/zenodo.2220368

**Article:**

> Prokopovych-Tkachenko, D. (2026). A Metadata-Driven Adaptive Cybersecurity Protector for
> SMEs in Metaverse-Enabled Ecosystems: Resource-Aware Tailoring of NIST CSF 2.0,
> ISO/IEC 27001:2022, and CIS Controls v8.1.

Machine-readable metadata is in [`CITATION.cff`](../CITATION.cff).
```

### BibTeX

```bibtex
@software{prokopovych_tkachenko_acp_sme_2026,
  author    = {Prokopovych-Tkachenko, Dmytro},
  title     = {{ACP-SME}: A Metadata-Driven Adaptive Cybersecurity Protector
               for {SMEs} --- Reference Prototype and Reproduction Package},
  version   = {0.1.0},
  year      = {2026},
  publisher = {Zenodo},
  doi       = {10.5281/zenodo.2220368},
  url       = {https://doi.org/10.5281/zenodo.2220368},
  note      = {Development repository:
               \url{https://github.com/omega2417/bnt/tree/master/acp-sme}}
}
```

---

## 6. One-line footer

```markdown
ACP-SME v0.1.0 · [DOI 10.5281/zenodo.2220368](https://doi.org/10.5281/zenodo.2220368) · [GitHub](https://github.com/omega2417/bnt/tree/master/acp-sme) · MIT
```

---

## Note on the project-directory URL

The project lives in the `acp-sme/` subdirectory of the `omega2417/bnt` repository. The
`tree/master/acp-sme` links above assume the work has been merged into the default branch.
Until then, use the branch URL:

<https://github.com/omega2417/bnt/tree/claude/zenodo-zip-project-64c3xu/acp-sme>

For a link that never breaks — the one to prefer in a published article if the repository
layout might change — use the commit permalink:

<https://github.com/omega2417/bnt/tree/6ce47dbffabf0219dc796476e2c4018815ba16e5/acp-sme>
