# Architecture

GoNext follows one design rule: every stage either produces information
required by a later stage or removes extension constructs; everything that
the Go toolchain can check by itself is delegated to it. The transpiler
therefore depends only on the public, stable surface of the Go toolchain —
the grammar, the `go/ast`, `go/parser`, `go/types`, `go/printer` and
`go/format` packages, and the `//line` directive convention — and never
modifies the Go compiler.

| Stage | Package | Input → output |
|---|---|---|
| S1 Parsing | `internal/syntax` | GoNext text → Go text with placeholders + side tables + position map → `go/ast` |
| S2 IAST | `internal/iast` | `go/ast` + side tables → IAST (Go nodes + extension nodes) |
| S3 Partial semantic analysis | `internal/sema` | IAST → types of receivers, callees, short functions, match results; exhaustiveness |
| S4 Normalization | `internal/normalize` | named/default arguments → positional calls; match → statements |
| S5 Lowering | `internal/lower` | enums, decision trees, lifted methods → `go/ast` |
| S6 Emission | `internal/emit` | `go/ast` → formatted Go source with `//line` directives |

`internal/driver` runs the stages for each package; packages of a module are
translated in dependency order so that the source importer of `go/types`
sees the generated files of GoNext packages that a package imports.

## Why rounds of go/types

S3 does not reimplement the Go type checker. Instead the partially lowered
package is type-checked with `go/types`; the errors of this check are
ignored and only the recorded information is used. Some facts become
available only after a rewrite: the receiver of `xs.map(…)` is known in
round 1, the call is rewritten to `List_map(xs, …)`, the parameter type of
the short function is known in round 2, and its result type (from the body)
in round 3, after which Go's own inference instantiates `List_map`. The
loop ends when a round changes nothing; constructs that are still
unresolved are reported as errors at their GoNext position.

## Correctness obligations

The transpiler is responsible for the semantics of extension constructs
(evaluation order of arguments, exhaustiveness and order of match arms,
the pointer-visibility invariant of compact enums); type safety of the rest
of the program is established by the Go compiler on the generated code.
The tests in `internal/driver` check these obligations: golden tests,
generated-code checks (gofmt, vet, types), diagnostics tests, and
differential tests that run programs under every enum representation.
