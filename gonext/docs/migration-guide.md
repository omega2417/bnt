# Migration guide: adopting GoNext in a Go module

GoNext is a superset of Go and its output is ordinary Go, so it can be
introduced one package — or one file — at a time.

## 1. Add the tool

```sh
go get -tool github.com/ORGANIZATION/gonext/cmd/gonext   # Go 1.24 tool dependency
```

or install it with `go install …/cmd/gonext@v1.0.0`.

## 2. Convert a file

Rename `foo.go` to `foo.gnx`. The file is still valid; nothing changes until
you use an extension. Run

```sh
go tool gonext translate ./pkg/...
```

which writes `foo_gnx.go`. Go files and GoNext files of the same package
see each other's declarations: Go code calls functions written in GoNext
directly, and GoNext code uses Go types (see `examples/mixed`).

## 3. Wire generation into the build

Add to one Go file of each package that contains `.gnx` files:

```go
//go:generate go tool gonext translate -q .
```

Two policies are common:

* **Commit generated files** (recommended for libraries): consumers of the
  module need no extra tool. Add a CI step that fails when they are stale:
  `go generate ./... && git diff --exit-code`.
* **Generate in CI**: add `*_gnx.go` to `.gitignore` and run
  `gonext build ./...` / `gonext test ./...` instead of `go build`/`go test`.

## 4. Editor support

Editors and `gopls` work on the generated Go files. Diagnostics of the Go
compiler and of `go vet` refer to `.gnx` lines through `//line` directives.
`gonext translate` reports GoNext-specific errors (non-exhaustive matches,
unknown named arguments, short functions whose types cannot be inferred)
with GoNext positions in the usual `file:line:column: message` format.

## 5. Idioms that GoNext replaces

| Go idiom | GoNext |
|---|---|
| functional options, configuration structs | named and default arguments |
| sealed interface + type switch | `enum` + `match` |
| `iota` constants + separate payload fields | `enum` |
| helper functions `SumInts(xs)` | extension methods `xs.Sum()` |
| top-level generic helpers `Map(xs, f)` | generic methods `xs.Map(f)` |
| `func(x int) int { return x * 2 }` | `x => x * 2` |

## 6. Choosing an enum representation

Start with the default (`compact`). Use `//gonext:repr flat` for enums with
type parameters (automatic) or when values are compared with `==`, and
`//gonext:repr interface` when the variants must be visible as separate Go
types to existing Go code. The representation can be changed without
touching GoNext code; the differential tests in `testdata/run` check that
programs behave identically under all three.

## 7. Limitations to plan for

See the [language reference](language-reference.md#limitations). In
particular, keep `match` expressions over an enum in the package that
declares it and expose behavior to other packages through methods.
