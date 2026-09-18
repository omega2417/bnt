# Elsevier submission checklist for the software side

A Q1 Elsevier journal will not review the code line by line, but reviewers and
the production system do check a specific short list. This file is that list,
with the state of each item in this repository.

## Mandatory statements in the manuscript

| Item | State | Where |
|---|---|---|
| CRediT authorship contribution statement | in the manuscript | `docs/publication/declarations.md` (copy) |
| Declaration of competing interest | in the manuscript | `docs/publication/declarations.md` |
| Data availability statement | **needs the Zenodo DOI** | `docs/publication/declarations.md` |
| Funding statement | in the manuscript (Halmstad University) | `docs/publication/declarations.md` |
| Declaration of generative AI in the writing process | in the manuscript | `docs/publication/declarations.md` |
| Highlights (3–5 bullets, ≤ 85 characters each) | drafted, **check the character limit** | `docs/publication/highlights.md` |

## Software and data availability

| Requirement | State |
|---|---|
| Code publicly archived with a persistent identifier | `make zenodo` produces the archive; DOI reserved on deposit |
| License stated and permissive enough for reuse | MIT (code), CC BY 4.0 (docs and figures) |
| Version of the code matched to the article | `evoproto 0.1.0`, recorded in `CITATION.cff`, `codemeta.json`, `.zenodo.json` |
| Dependencies pinned | `requirements-lock.txt` plus loose bounds in `pyproject.toml` |
| Instructions to reproduce every figure and table | `docs/reproducibility.md`, `make all` |
| No third-party data redistributed without license | no biological records are shipped; see `docs/datasheet.md` |
| FAIR metadata | `CITATION.cff`, `codemeta.json`, `.zenodo.json` |

## Figures

- Vector PDF for every figure (`figures/fig*.pdf`), 600 dpi PNG alongside.
- Fonts embedded (`pdf.fonttype = 42`).
- Single-column figures sized to 90 mm, double-column to 190 mm.
- Every figure regenerable from code: `evoproto figures`.
- Figures that show generated data carry a SYNTHETIC marker in the panel text
  as well as in the caption, so a screenshot cannot lose the qualifier.
- **Check before submission**: the journal's own minimum resolution and colour
  model (some titles require CMYK for print); colours here are chosen to remain
  distinguishable in greyscale but were not checked against a specific colour
  policy.

## References

- Machine-readable list: `docs/references/references.json` (63 entries).
- `evoproto verify-dois` resolves every DOI through CrossRef and compares the
  returned title with the stored one, so a transposed digit that resolves to a
  *different* paper is caught. **Run it with network access before submission**;
  in the environment that produced this archive CrossRef was unreachable and
  only the offline structural check ran (all 63 entries pass; 8 have no DOI,
  which is correct for books and web resources).
- Reference [24] is flagged `[[VERIFY DOI]]` in the manuscript and is still open.

## Ethics and transparency specific to this paper

- Every number in the article carries a provenance tag; the package enforces the
  distinction in code (`data.Tag`), not just in prose.
- The dry run is labelled SYNTHETIC in the table caption, in the figure panels
  and in the results JSON, and no inference about H1–H3 is drawn from it.
- The pre-registration (`docs/preregistration.md`) is frozen before any physical
  build and archived with the code, as Section 7.8 requires.
- Abstentions are reported alongside recommendations, so the abstention rate is
  a measured quantity rather than a hidden one.

## Still open

1. The target journal is not fixed in the metadata (`CITATION.cff`,
   `.zenodo.json` carry placeholders).
2. ORCIDs are missing for all three authors.
3. Table 7 of the manuscript does not match the output of this implementation;
   see `docs/reproducibility.md` for the comparison and the two options.
4. T2 and T3 evaluators are unimplemented by design and declared as such.
