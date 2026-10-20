# Lowering specification

This document specifies how each GoNext construct is translated to Go. The
generated code depends only on the Go standard library and, for a few
compact-enum payloads, on the run-time package `gnrt`.

## Pipeline

```
 .gnx ─▶ S1 parse ─▶ S2 IAST ─▶ S3 semantic analysis ⇄ S4 normalize ⇄ S5 lower ─▶ S6 emit ─▶ _gnx.go
                                   (go/types rounds)                                │
                                                                       go build / go test / go vet / gopls
```

* **S1 (`internal/syntax`)** scans the source with `go/scanner`, recognizes
  the extension productions, records them in side tables and replaces them
  by placeholder Go syntax, which `go/parser` then parses. Each byte of the
  placeholder text maps back to its GoNext offset.
* **S2 (`internal/iast`)** turns placeholders into IAST nodes: enums and
  variants, match expressions with arms and patterns, short functions,
  default parameter values, extension and generic methods.
* **S3 (`internal/sema`)** type-checks the partially lowered package with
  `go/types` in rounds. A round resolves what has become decidable
  (receivers of `x.f()` calls, callees of calls with named arguments,
  expected types of short functions, result types of match expressions);
  the rounds stop at a fixed point. Exhaustiveness is checked here.
* **S4 (`internal/normalize`)** produces positional calls, introduces
  temporaries and places the statement form of match expressions.
* **S5 (`internal/lower`)** generates enum declarations, constructors and
  decision trees, and lifts extension and generic methods.
* **S6 (`internal/emit`)** prints with `go/printer`, normalizes with
  `go/format` and adds `//line` directives.

## Syntactic extensions

| GoNext | Go |
|---|---|
| `dial("a", retries: 5)` with `func dial(host string, port int = 443, retries int = 3)` | `dial("a", 443, 5)` |
| `dial(retries: r(), host: h())` | `gnArg1 := r()` · `gnArg2 := h()` · `dial(gnArg2, 443, gnArg1)` |
| `ext func (s []int) sum() int` | `func ext_IntSlice_sum(s []int) int` |
| `ext func (s []int) Sum() int` | `func Ext_IntSlice_Sum(s []int) int` (visible to importers) |
| `xs.sum()` | `ext_IntSlice_sum(xs)` |
| `a.max3(b, c)` | `max3(a, b, c)` |

Temporaries are introduced only when positional evaluation would change
the relative order of argument expressions that may have side effects
(calls, receives, divisions); pure arguments are left in place, as Go itself
does not order their evaluation relative to calls.

Receiver type names are mangled as follows: `[]T` → `TSlice`, `*T` →
`PtrT`, `map[K]V` → `MapKV`, `pkg.T` → `PkgT`, `G[T]` → `G`.

## Structural extensions

**Generic methods** are lifted: `func (l List[T]) map[U any](f func(T) U) List[U]`
becomes `func List_map[T any, U any](l List[T], f func(T) U) List[U]`; the
constraints of the receiver type parameters are copied from the type
declaration. Calls `xs.map(f)` become `List_map(xs, f)`; Go infers the
type arguments.

**Short functions** become function literals with explicit types:
`xs.map(x => x * 2)` → `List_map(xs, func(x int) int { return x * 2 })`.
The parameter types come from the expected function type, with type
parameters of a generic callee bound by unifying the other arguments; the
result type comes from the expected type or from the body.

**Match expressions** are compiled to a result variable and a switch
statement placed before the statement that uses the match:

```go
var gnMatch1 float64
switch s.tag {
case Shape_Circle:
	r := math.Float64frombits(s.w0)
	gnMatch1 = math.Pi * r * r
…
default:
	panic("gonext: non-exhaustive match on Shape")
}
return gnMatch1
```

For `x := match …` and `x = match …` the variable `x` itself is used. The
`default` branch is unreachable for values built by constructors; it
remains as a defensive check.

Moving the evaluation of a match (or of argument temporaries) in front of
its statement is only done when it cannot change the order of effects. In
the following positions the construct remains an immediately invoked
function literal, which the Go compiler inlines when possible:

* after a call or receive that is evaluated earlier in the same statement,
* in the right operand of `&&` and `||`,
* in the condition or post statement of a `for` loop, in `case`
  expressions and in `select` cases,
* in the condition of an `if`/`switch` that has an init statement,
* in package-level variable initializers.

A match in an `else if` condition is placed in front of the inner `if`
(`else { …; if … }`).

**Decision trees.** For every variant the arms that can match it are tried
in source order; guarded arms become an `if`/`else` chain whose last element
is an unguarded arm. Variants with identical chains that bind no payload are
merged into one `case`; variants handled only by wildcard arms go to
`default`. A payload field is bound only if the guard or body uses it.

## Representational extension: enums

Tags are `uint8` constants starting at 1 (`Shape_Circle = iota + 1`), so the
zero value is not a variant.

**R1 — interface.**

```go
type Shape interface{ isShape() }
type Shape_Circle struct{ r float64 }
func (Shape_Circle) isShape() {}
func NewShape_Circle(r float64) Shape { return Shape_Circle{r: r} }
```

A match is a type switch. Every construction allocates (the payload is
boxed in the interface).

**R2 — flat.**

```go
type Shape struct {
	tag      uint8
	circle_r float64
	rect_w   float64
	rect_h   float64
	…
}
```

**R3 — compact.** Payload fields are assigned to slots per variant:

| Payload type (underlying) | Slot | Store / load |
|---|---|---|
| integers, `uintptr` | word `wN uint64` | `uint64(x)` / `T(s.wN)` |
| `float64`, `float32` | word | `math.Float64bits` / `math.Float64frombits` |
| `bool` | word | `gnrt.BoolWord(x)` / `s.wN != 0` |
| `string` | pointer slot + length word | `unsafe.StringData` / `unsafe.String` |
| `[]E` | pointer slot + length and capacity words | `unsafe.SliceData` / `unsafe.Slice(…)[:len]` |
| `*E`, `unsafe.Pointer` | pointer slot `p unsafe.Pointer` | `unsafe.Pointer(x)` / `(*E)(s.p)` |
| `map`, `chan`, `func` | pointer slot | `gnrt.Ptr(x)` / `gnrt.FromPtr[T](s.p)` |
| other (interfaces, structs, arrays, complex) | dedicated typed field | direct |

The number of words and slots of the enum is the maximum over its variants,
so scalar payloads of different variants share the same words.

**Invariant (Equation 4 of the article).** Go's collector is precise: it
scans only slots whose type contains pointers and does not treat integers
as references. Therefore every payload field whose type contains pointers
is stored in an `unsafe.Pointer` slot or a typed field, never in a word.
The lowering stage checks this when it computes the slot assignment
(`lower.ComputeLayout`); Experiment 4 (`bench/pointervis`) shows what
happens otherwise.

## Line directives

The emitter compares the statements and declarations of the lowered tree
with those of the formatted output and inserts `//line file.gnx:N` before
every line whose implicit mapping would be wrong. Synthetic code (hoisted
temporaries, switch statements, constructors) maps to the GoNext construct
it was generated from.
