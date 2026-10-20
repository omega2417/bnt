# Changelog

All notable changes to this project are documented in this file. The
project follows [Semantic Versioning](https://semver.org/).

## [1.0.0] — 2026-10-20

First release (milestone M1 of the roadmap).

### Transpiler
- Six-stage pipeline: S1 parsing (pre-parser on top of `go/scanner` and
  `go/parser`), S2 internal AST, S3 partial semantic analysis in `go/types`
  rounds, S4 normalization, S5 lowering to `go/ast`, S6 emission with
  `go/printer`, `go/format` and `//line` directives.
- Extensions: enums with associated data, `match` with guards, alternatives,
  wildcard and constant patterns, named arguments, default parameter values,
  extension methods (also exported across packages), generic methods,
  short anonymous functions with contextual typing, uniform function call
  syntax.
- Enum representations: sealed interface (R1), flat tagged struct (R2),
  compact tagged struct (R3, default) with checked slot assignment; selected
  with `-repr` or `//gonext:repr`.
- Exhaustiveness and unreachable-arm checks; diagnostics at GoNext positions.
- Command `gonext` with `translate`, `build`, `test`, `vet`, `run`, `clean`.
- Run-time helper package `gnrt`.

### Quality gates
- Golden tests (including Listings 1–6 of the article), generated-code
  checks (gofmt, go vet, type checker), diagnostics tests, differential tests
  under all enum representations, unit tests.

### Reproducibility package
- Micro-experiments 1–4 (`bench/`), criterion scores (`data/`), analysis and
  plotting scripts (`scripts/`), raw and derived results (`results/`),
  Figures 2 and 4 (`figures/`).
