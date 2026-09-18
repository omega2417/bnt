# Contributing

This repository backs a scientific article, so contributions are judged by one
extra criterion beyond the usual: **can a reader still reproduce the published
numbers after your change?**

## Ground rules

1. **Never change a seed derivation, a default weight or a threshold silently.**
   Those values are pre-registered (`docs/preregistration.md`). If a change is
   warranted, change it in the pre-registration too, bump the version, and say so
   in `CHANGELOG.md`.
2. **Every number keeps its provenance tag.** If you add a quantity, tag it
   (`MEASURED`, `MODELED`, `PROXY`, `EXTERNAL`, `SYNTHETIC`) and propagate the
   tag to anything computed from it.
3. **No biological records in the repository.** Connectors describe requests;
   corpus assembly happens outside, under the sources' licenses.
4. **An equation in the article gets a test.** Add the mapping row to
   `docs/paper_mapping.md` as well.

## Workflow

```bash
git switch -c feature/short-name
pip install -e ".[dev]"
# ... change something ...
make lint test
make dryrun figures     # if your change can move any published number
```

Open a pull request describing: what changed, which article section it touches,
and whether any published number moves. If one does, include the before/after.

## Style

- Ruff enforces the lint rules (`make lint`); line length 100.
- Docstrings carry the article's equation numbers — that cross-reference is how
  reviewers navigate, so keep it accurate.
- Prefer clarity over cleverness: this code is read by reviewers who are
  engineers and biologists, not only by Python programmers.

## Reporting problems

Open an issue with the command you ran, the output, and your `evoproto env`
record. A discrepancy in a published number is the highest-priority kind of bug
here — say so in the title.
