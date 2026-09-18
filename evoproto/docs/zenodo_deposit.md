# Depositing this archive on Zenodo

The archive built by `make zenodo` (or `python scripts/make_zenodo_archive.py`)
is a self-contained snapshot: source, tests, documentation, notebooks, the
regenerated figures, the dry-run results, the exact dependency pins, a manifest
and SHA-256 checksums for every file.

## Before you upload

1. **Close the open items** in `docs/paper_mapping.md` (the weights and
   thresholds the manuscript pins, and the `NEEDS INPUT` markers).
2. **Run the online DOI check**: `evoproto verify-dois` — it needs access to
   `api.crossref.org`.
3. **Regenerate everything** so the archive matches the article:
   `make all` (tests, dry run, figures) then `make zenodo`.
4. **Add ORCIDs** to `CITATION.cff`, `codemeta.json` and `.zenodo.json`.
5. Check `ARCHIVE_MANIFEST.md` inside the archive: it lists every file with its
   size, SHA-256 and role.

## Upload

1. Sign in at <https://zenodo.org> (an ORCID login makes attribution cleaner).
2. **New upload** → upload `evoproto-v0.1.0.zip`.
3. Zenodo reads `.zenodo.json` when the deposit comes through the GitHub
   integration; for a manual upload, fill the form to match that file:
   - Upload type: **Software**
   - Title, description, keywords, creators and affiliations: as in `.zenodo.json`
   - License: **MIT** (documentation and figures are CC BY 4.0, stated in
     `LICENSE-DOCS`)
   - Version: **0.1.0**
   - Language: English
4. **Reserve a DOI** *before* publishing (Zenodo offers "Reserve DOI"). This is
   the DOI you put into the article's Data/Code availability statement, and into
   `CITATION.cff`, `codemeta.json` and `pyproject.toml`.
5. Add the article as a **related identifier**: relation *is supplement to*, with
   the article DOI once it is assigned. Zenodo's concept DOI always resolves to
   the newest version; cite the **version DOI** in the article so that readers
   land on the exact code that produced the results.
6. Publish. Publishing is irreversible — files cannot be changed afterwards,
   only superseded by a new version.

## Alternative: the GitHub–Zenodo integration

Enabling the repository in Zenodo's GitHub settings and cutting a release tag
(`v0.1.0`) makes Zenodo archive the tarball automatically and read `.zenodo.json`
for metadata. This keeps the DOI tied to a tag, which is the most auditable
option when reviewers ask "which commit produced Table 7?". The manual ZIP route
above exists because it does not require the repository to be public.

## After publication

- Put the version DOI into the article's **Data availability** statement,
  replacing `[[NEEDS INPUT: Zenodo DOI / repository URL]]`:

  > The reference implementation (evoproto v0.1.0), the figure-generation
  > scripts and the synthetic dry-run outputs are available at
  > https://doi.org/10.5281/zenodo.XXXXXXX under the MIT license
  > (documentation and figures: CC BY 4.0).

- Add the DOI badge to `README.md`.
- Every later release repeats this cycle: bump the version in `pyproject.toml`,
  `CITATION.cff`, `codemeta.json` and `.zenodo.json`, update `CHANGELOG.md`,
  rebuild, deposit as a **new version** of the same concept record.
