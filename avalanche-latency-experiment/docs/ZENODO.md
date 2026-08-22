# Depositing on Zenodo

## Build the archive

```bash
make pipeline PROFILE=demo     # or full, for the complete campaign
make verify
make package                   # -> dist/avalanche-latency-experiment.zip
cat dist/avalanche-latency-experiment.zip.sha256
```

`python -m alp package` writes three files:

| File | Contents |
| --- | --- |
| `…zip` | the deposition archive |
| `…zip.sha256` | its checksum, to quote in the record description |
| `…contents.json` | the entry list, the checksum and whether raw data is included |

The build is deterministic — sorted entries, timestamps pinned to
1980-01-01, fixed compression — so the same tree always produces the same
SHA-256. Zenodo mints a DOI for the exact bytes it receives, which is why
this matters.

To publish the code and derived results without the raw dataset (much
smaller, still fully regenerable from the master seed):

```bash
python -m alp package --no-raw --out dist/avalanche-latency-experiment-code.zip
```

## What is in the archive

Everything needed to re-run the study: the executable protocol (English and
Ukrainian), the package, the measurement client, the smart contract, the
node and netem configurations, the field scripts, the Colab notebook, the
test suite, the derived results with their figures and reports, the SHA-256
manifests, and — unless `--no-raw` was used — the raw dataset.

## Deposition checklist

1. **Metadata.** `.zenodo.json` is picked up automatically when the record is
   created through the GitHub integration. When uploading by hand, copy the
   title, description, keywords, licence and related identifiers from it.
2. **Fill the placeholders.** `.zenodo.json` and `CITATION.cff` contain
   `[DATA REQUIRED]` markers for the authors, ORCID, repository URL and DOI.
   Complete them before publishing.
3. **Licences.** Code is MIT; data, figures and documentation are CC BY 4.0.
   Zenodo takes a single licence field — declare MIT there and state the dual
   licensing in the description, as `.zenodo.json` already does.
4. **Provenance.** If the archive contains a `SIMULATED` dataset, keep the
   provenance paragraph of the description. It is what stops a reader from
   mistaking reference-model output for measurements. Do not remove it until
   the deposition actually carries campaign logs.
5. **Reserve the DOI** on Zenodo before publishing, write it into
   `CITATION.cff`, `.zenodo.json` and `LICENSE-DATA`, rebuild the archive,
   and upload that build. Record the new checksum in the description.
6. **Versioning.** Use Zenodo's *New version* for updates so the concept DOI
   keeps resolving to the latest one. Bump `version` in `pyproject.toml`,
   `CITATION.cff`, `.zenodo.json` and `alp.__version__` together — the
   archive's top-level directory is named from `alp.__version__`.
7. **Link the article.** After acceptance, add the article DOI to
   `related_identifiers` with relation `isSupplementTo`, and add the Zenodo
   DOI to the article's data-availability statement.

## Suggested data-availability statement

> The experimental protocol, the measurement and analysis software, the
> complete dataset and the code that generates every table and figure in this
> article are archived on Zenodo at https://doi.org/[DOI] under MIT (code) and
> CC BY 4.0 (data and documentation). The analysis can be reproduced end to
> end in a browser through the included Google Colab notebook; SHA-256
> manifests and a re-derivation check are part of the deposition.
