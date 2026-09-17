# Depositing this package on Zenodo

The archive is ready to upload. Four things must be completed by the authors
first — they are placeholders on purpose, because inventing them would be worse
than leaving them visible.

## Before you upload

1. **Authors.** Replace every `REPLACE BEFORE DEPOSITION` entry in
   `.zenodo.json` (`creators`) and `CITATION.cff` (`authors`, `references`) with
   real names, affiliations and ORCIDs. The manuscript itself still carries
   `[Firstname Lastname]` placeholders, so none could be filled in here.
2. **Repository URL.** `repository-code` in `CITATION.cff` currently points at
   the working branch,
   `github.com/omega2417/bnt/tree/claude/publication-zenodo-project-w2iwa0/bircpg`.
   Update it if the code moves to its own repository or to a merged default
   branch — a branch URL can disappear, and a citation that rots is worse than
   one that is obviously provisional.
3. **Article identifier.** Once the article is assigned a DOI, put it in
   `.zenodo.json` under `related_identifiers` with relation `isSupplementTo`.
   Until then, leave it — Section 7.6 of the manuscript is explicit that a public
   archive should receive a persistent identifier only *after* deposition, and no
   DOI is asserted anywhere in this package.
4. **Funding.** The manuscript's funding statement is "This research received no
   external funding", flagged for the authors to confirm. Confirm it, and add a
   `grants` entry to `.zenodo.json` if that changes.

## Uploading

1. Build the archive:

   ```bash
   python tools/make_archive.py           # writes dist/bircpg-1.0.0.zip
   ```

   The script excludes caches, build artefacts and generated `results/`, and
   prints the SHA-256 of the archive it writes. Record that checksum — it is what
   lets a reader confirm the archive they downloaded is the one you deposited.

2. On <https://zenodo.org>, choose **New upload**, drop in the zip, and click
   the button to import metadata from the archive's `.zenodo.json`. Check that
   the upload type is *Software* and the licence is *MIT*.

3. Publish. Zenodo mints two DOIs: one for this version and one *concept DOI*
   that always resolves to the latest version. **Cite the concept DOI in the
   article** and the version DOI in a "this analysis used version 1.0.0" note.

4. After publication, add the DOI badge to `README.md` and fill in
   `doi:` in `CITATION.cff`.

## Linking GitHub to Zenodo (optional, recommended)

If the code lives on GitHub, enable the repository in your Zenodo account's
GitHub settings *before* creating a release. Every subsequent GitHub release is
then archived automatically and versioned under the same concept DOI, so the
citation in the article keeps working as the code evolves.

## What a reader gets

* An exact reproduction of Table 2, the Equation (6) identity, the price of
  anarchy and Equation (15) — in seconds, with `bircpg section6`.
* Figure 3 regenerated from the code, with its underlying numbers as CSV.
* The Section 7.1 verification sweep, including the required edge cases.
* A runnable Level II harness with all five baselines and the analysis plan.
* A Colab notebook that needs no local installation.

## What a reader does not get, and should not be told they do

No executed experiment, no measured energy, no hardware result, and no
demonstrated advantage for the proposed method. Keep the Zenodo description
honest about this; the draft description in `.zenodo.json` already is.
