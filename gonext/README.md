# GoNext — a transpiler for language extensions with Go ecosystem compatibility

GoNext is an experimental dialect of Go and a source-to-source transpiler
that lowers its extensions to ordinary Go. Every valid Go file is a valid
GoNext file with the same meaning; the generated code is compiled, tested,
vetted and packaged by the **unmodified** Go toolchain, and GoNext and Go
files can live in the same package.

This repository is the software project and the reproducibility package of
the article *"GoNext: A Transpilation Architecture for Language Extensions
with Go Ecosystem Compatibility"* (P. Forkert et al., submitted to
*Electronics*, 2026).

```gnx
enum Shape {
	Circle(r float64)
	Rect(w, h float64)
	Triangle(a, b, c float64)
	Text(s string)
}

func measure(s Shape) float64 {
	return match s {
		Circle(r)         => math.Pi * r * r
		Rect(w, h)        => w * h
		Triangle(a, b, c) => heron(a, b, c)
		Text(s)           => float64(len(s))
	}
}

c := dial("example.org", retries: 5)   // named + default arguments
ys := xs.map(x => x * 2)                // generic method + short function
total := nums.sum()                     // extension method
```

## The eight extensions

| Extension | Class | Lowered to |
|---|---|---|
| Named arguments `f(x: 1)` | syntactic | positional call; temporaries if the evaluation order differs |
| Default parameter values `p int = 443` | syntactic | default expressions inserted at the call site |
| Extension methods `ext func (s []int) sum() int` | syntactic | top-level function `ext_IntSlice_sum(s []int)` |
| Uniform function call syntax `a.f(b)` | syntactic | plain call `f(a, b)` |
| Generic methods `func (l List[T]) map[U any](…)` | structural | top-level generic function `List_map[T, U any]` |
| Short anonymous functions `x => expr` | structural | function literal with types from the context |
| Pattern matching `match` | structural | decision tree of `switch` statements and bindings |
| Enums with associated data `enum E { A(x int) }` | representational | sealed interface (R1), flat tagged struct (R2) or compact tagged struct (R3) |

See [`docs/language-reference.md`](docs/language-reference.md) for the
syntax and semantics, [`docs/lowering.md`](docs/lowering.md) for the
lowering specification and [`docs/migration-guide.md`](docs/migration-guide.md)
for adopting GoNext in an existing Go module.

## Install and use

Requirements: Go 1.24 or newer. No other dependencies (the transpiler and
the generated code use only the Go standard library and, when needed, the
small run-time package `gnrt`).

```sh
go install github.com/ORGANIZATION/gonext/cmd/gonext@latest

gonext translate ./...           # shapes.gnx -> shapes_gnx.go
gonext build ./...               # translate, then go build
gonext test ./...                # translate, then go test
gonext run ./examples/calc       # translate, then go run
gonext translate -repr flat .    # choose the enum representation
gonext translate -n file.gnx     # print the generated code
gonext clean ./...               # remove generated files
```

GoNext sources use the extension `.gnx`; the generated file for
`shapes.gnx` is `shapes_gnx.go` (`x_test.gnx` → `x_gnx_test.go`). The
generation step can be wired into `go generate`:

```go
//go:generate go run github.com/ORGANIZATION/gonext/cmd/gonext translate -q .
```

Generated files carry `//line` directives, so compiler errors, `go vet`
reports, panics and stack traces refer to the GoNext source:

```
panic: runtime error: integer divide by zero
	main.gnx:13
```

## Repository structure

The structure follows the transpiler pipeline (Table 3 of the article).

| Path | Responsibility |
|---|---|
| `cmd/gonext` | Command-line tool: `translate`, `build`, `test`, `vet`, `run`, `clean`; integration with `go generate` |
| `internal/syntax` | S1 — pre-parser for the GoNext productions on top of `go/scanner` and `go/parser`; position map back to GoNext sources |
| `internal/iast` | S2 — internal AST: `go/ast` nodes plus enum, variant, match, arm, pattern, lambda, default-parameter, extension and generic-method nodes |
| `internal/sema` | S3 — partial semantic analysis in `go/types` rounds: receiver types, expected function types, match result types, exhaustiveness |
| `internal/normalize` | S4 — named/default arguments, evaluation order, statement form of match expressions |
| `internal/lower` | S5 — enum representations R1–R3 and slot assignment, decision trees, lifting of extension and generic methods |
| `internal/emit` | S6 — printing with `go/printer`/`go/format` and `//line` directives |
| `internal/driver` | The pipeline over packages; golden, quality-gate, diagnostics and differential tests |
| `internal/astx` | Shared `go/ast` utilities |
| `gnrt` | Small run-time helper package in pure Go, imported by generated code only when needed |
| `testdata/golden` | GoNext inputs and reviewed Go outputs (including Listings 1–6 of the article) |
| `testdata/diagnostics` | Programs with expected diagnostics (`// ERROR "…"`) |
| `testdata/run` | Programs run under all enum representations (differential tests) |
| `examples` | `shapes` (Listing 5), `calc` (an expression DSL), `mixed` (Go and GoNext in one package) |
| `bench` | Micro-experiments 1–4 of the article |
| `data`, `scripts`, `results`, `figures` | Criterion scores, analysis scripts, raw and derived results, figures |
| `docs` | Language reference, lowering specification, migration guide, architecture |

## Quality gates

Every change has to pass four gates (`make check`, run in CI):

1. **Golden tests** — generated code is compared with reviewed expectations
   (`go test ./internal/driver -run Golden`; `-update` rewrites them).
2. **Generated-code checks** — every generated file is gofmt-formatted and
   accepted by `go vet` and the Go type checker without warnings.
3. **Differential tests** — the programs in `testdata/run` are translated
   with each enum representation, run, and their outputs compared.
4. **Regression benchmarks** — `bench/` is run and its results are stored
   with each release (`results/`).

```sh
make check        # gofmt, vet, unit, golden, diagnostics and differential tests
make reproduce    # benchmarks, statistics, Tables 6–7, Figures 2 and 4
```

## Reproducing the article

`bash scripts/reproduce.sh` (or `make reproduce`) runs the equivalence tests
and the micro-benchmarks of Experiments 1–3 (`go test -bench . -benchmem
-count 10`, `GOMAXPROCS=2`), the pointer-visibility Experiment 4, the
platform ranking with the Dirichlet sensitivity analysis (Section 3.1) and
regenerates Figures 2 and 4. Python 3 with NumPy and Matplotlib is needed
for the analysis (`pip install -r scripts/requirements.txt`). Raw outputs,
the measurement environment and derived tables are in
[`results/`](results/README.md). Benchmark numbers depend on the machine.

## Status and limitations

GoNext is a research prototype (version 1.0.0, milestone M1 of the roadmap
in the article). Known limitations are listed in the
[language reference](docs/language-reference.md#limitations); the most
important ones are that a `match` must be in the package that declares the
enum, and default parameter values apply to calls within the declaring
package.

## Citing

If you use GoNext, please cite the software (see [`CITATION.cff`](CITATION.cff);
the DOI is assigned by Zenodo) and the article.

## License

Apache License 2.0, see [`LICENSE`](LICENSE).

## Use of generative AI

Claude (Anthropic) assisted in writing the transpiler, the benchmark
programs and the analysis scripts. All benchmark results are produced by
executing these programs. The authors reviewed the code.
