# Contributing to GoNext

Thank you for your interest. GoNext is a research prototype; issues and
pull requests are welcome.

## Before you send a change

Every change has to pass the quality gates:

```sh
make check
```

runs `gofmt`, `go vet`, the unit tests and

1. the golden tests (`testdata/golden`): if a change of the generated code
   is intended, run `go test ./internal/driver -run Golden -update` and
   review the diff of the `.golden` files in the pull request;
2. the generated-code checks (gofmt, `go vet`, type checker);
3. the differential tests (`testdata/run`, all enum representations);
4. the diagnostics tests (`testdata/diagnostics`).

Changes that can affect performance should include the output of
`make bench` before and after the change.

## Adding a language feature

1. Describe the syntax and semantics in `docs/language-reference.md` and the
   lowering in `docs/lowering.md`; classify it as syntactic, structural or
   representational.
2. Recognize the syntax in `internal/syntax`, add IAST nodes in
   `internal/iast`, and implement the lowering.
3. Add golden inputs, diagnostics for its errors and, if it has run-time
   behavior, a program in `testdata/run`.

## Releases

Releases follow semantic versioning. A release is a tag `vX.Y.Z` on GitHub;
the GitHub–Zenodo integration archives it and assigns a DOI. Update
`CHANGELOG.md`, `CITATION.cff`, `.zenodo.json`, `internal/driver.Version`
and the regression benchmark results in `results/` before tagging.
