# GoNext language reference (version 1.0)

GoNext is Go plus eight extensions. The grammar is a superset of the Go
grammar ([The Go Programming Language Specification](https://go.dev/ref/spec));
this document describes only the additions, in the notation of the Go
specification. A program that uses none of the extensions is a Go program
with unchanged meaning.

Source files have the extension `.gnx`. All `.gnx` and `.go` files in a
directory with the same package clause form one package.

## 1. Enums with associated data

```ebnf
EnumDecl    = "enum" identifier [ TypeParameters ] "{" { Variant ";" } "}" .
Variant     = identifier [ Parameters ] .
```

`enum` is recognized only at the top level, followed by an identifier.

```gnx
enum Shape {
	Circle(r float64)
	Rect(w, h float64)
	Empty
}

enum Option[T any] {
	None
	Some(v T)
}
```

An enum declares a new defined type. A value of the type is exactly one of
its *variants*; a variant carries the *payload* declared by its parameter
list (names are optional: `Pair(int, string)` names the fields `f0`, `f1`).

**Construction.** `Shape.Circle(1.5)` constructs a variant value; a variant
without payload is written `Shape.Empty`. For a generic enum the type
arguments are inferred from the payload (`Option.Some(3)`) or given
explicitly (`Option[int].None`). When the variant name is unique among the
enums of the package and not declared otherwise, the short form
`Circle(1.5)` may be used. Each variant also has a constructor function that
Go code can call: `NewShape_Circle(1.5)` (exported enums) or
`newShape_Circle` (unexported enums).

**Representation.** The Go representation of an enum is chosen by the
transpiler flag `-repr` or per enum with a comment directly before the
declaration:

```gnx
//gonext:repr flat
enum Token { … }
```

| Representation | Go code | Notes |
|---|---|---|
| `compact` (R3, default) | tagged struct; scalar payloads of all variants share `uint64` words, pointer payloads share `unsafe.Pointer` slots | smallest; no allocation per value |
| `flat` (R2) | tagged struct with one field per payload field of every variant | no allocation; larger values |
| `interface` (R1) | sealed interface, one struct type per variant | one heap allocation per value; enum cannot have methods |

Generic enums always use the flat representation.

**Methods.** Methods can be declared on enum types in the flat and compact
representations, in the usual Go way: `func (s Shape) Area() float64`.

**Zero value.** The zero value of an enum type is not one of its variants;
matching it executes the wildcard arm, or panics with
`gonext: non-exhaustive match on Shape` if there is none.

**Equality.** Compare enum values with `match`. With the compact
representation `==` compares payload words, so two equal strings stored in
different memory compare unequal.

## 2. Pattern matching

```ebnf
MatchExpr   = "match" Expression "{" { MatchArm ( ";" | "," ) } "}" .
MatchArm    = Pattern { "|" Pattern } [ "if" Expression ] "=>" ArmBody .
Pattern     = "_" | VariantPat | ConstPat .
VariantPat  = [ identifier "." ] identifier [ "(" [ Binder { "," Binder } ] ")" ] .
Binder      = identifier | "_" .
ConstPat    = Expression .
ArmBody     = Expression | Block .
```

`match` is recognized where an expression or statement can start and the
braces contain an arm with `=>`. As with `switch`, a composite literal in
the scrutinee must be parenthesized.

```gnx
area := match s {
	Circle(r)            => math.Pi * r * r
	Rect(w, h) if w == h => w * w          // guard
	Rect(w, h)           => w * h
	Empty                => 0
}

label := match n {
	0 | 1          => "tiny"               // alternatives
	_ if n%2 == 0  => "even"
	_              => "odd"
}
```

* **Variant patterns** bind the payload fields positionally; `_` ignores a
  field. The bound names are in scope in the guard and the arm body.
  Alternatives (`A | B`) cannot bind names.
* **Constant patterns** are expressions compared with `==` (for matches over
  values that are not enums).
* Arms are tried **in source order**; the first arm whose pattern matches
  and whose guard is true is taken.
* **Exhaustiveness.** A match over an enum must cover every variant with an
  arm without guard (or a wildcard `_`); a match over other values must end
  with an unguarded wildcard. Arms that can never be taken are errors.
* **As an expression**, every arm body is an expression; the type of the
  match is the type expected by the context (assignment, return, argument)
  or the type of the first typed arm. An arm may call `panic`.
* **As a statement** (a match at the start of a statement), arm bodies may
  be simple statements or blocks; `return` and `continue` in a block arm
  refer to the enclosing function or loop. An unlabeled `break` or a
  `fallthrough` in an arm is an error (use a labeled `break` to leave a
  loop).

## 3. Named arguments

```ebnf
Arguments   = "(" [ ( ExpressionList | NamedArgs | ExpressionList "," NamedArgs ) [ "," ] ] ")" .
NamedArgs   = identifier ":" Expression { "," identifier ":" Expression } .
```

Arguments can be passed by parameter name, after the positional arguments:
`dial("example.org", retries: 5)`, `strings.Repeat(count: 3, s: "ab")`.
Named arguments work for every function or method whose parameters have
names, including Go library functions. A variadic parameter cannot be
passed by name. **Evaluation order:** arguments are evaluated in source
order, then default values in parameter order.

## 4. Default parameter values

```ebnf
ParameterDecl = [ IdentifierList ] [ "..." ] Type [ "=" Expression ] .
```

```gnx
func dial(host string, port int = 443, timeout time.Duration = 5*time.Second) Conn
```

A parameter with a default value must be declared with its own type. The
default expression is evaluated at the call site each time the call is made
and may refer to package-level declarations of the declaring package. It
cannot refer to other parameters. Defaults apply to functions, methods,
extension methods and generic methods declared in GoNext code of the same
package.

## 5. Extension methods

```ebnf
ExtDecl     = "ext" MethodDecl .
```

```gnx
ext func (s []int) sum() int { … }
ext func (s []T) Last[T any]() T { return s[len(s)-1] }
ext func (c *Counter) Inc(by int = 1) { c.n += by }
```

An extension method can be declared for any receiver type, including types
of other packages, unnamed types and type parameters. It is called with
method syntax (`xs.sum()`); a real method of the type takes precedence.
Pointer receivers take the address of addressable operands, as for methods.
Extension methods with an exported name (`Sum`) are visible in packages that
import the declaring package.

## 6. Generic methods

```ebnf
MethodDecl  = "func" Receiver MethodName [ TypeParameters ] Signature [ FunctionBody ] .
```

```gnx
func (l List[T]) map[U any](f func(T) U) List[U] { … }
ys := xs.map(x => x * 2)
```

Methods can declare their own type parameters. A generic method is called
with method syntax; its type arguments are inferred as for generic
functions. Generic methods do not belong to the method set of the type, so
they cannot satisfy interfaces. A method name may be a Go keyword (`map`,
`range`, …) because it is always used after a dot.

## 7. Short anonymous functions

```ebnf
ShortFunc   = ( identifier | "(" [ ShortParams ] ")" ) "=>" ( Expression | Block ) .
ShortParams = identifier { "," identifier } | ParameterList .
```

```gnx
xs.map(x => x * 2)
sort.Slice(v, (i, j) => v[i] < v[j])
Each(items, it => { total += it.n })
f := (a int, b int) => a * b
```

Parameter types are taken from the function type expected by the context
(a call argument, a typed variable, an assignment, a return, a composite
literal element); the result type is taken from the expected type or, if it
is still unknown, from the body. The transpiler reports an error at the
short function when

* no function type is expected (for example `f := x => x + 1`) — declare
  the parameter types;
* the result type is unknown and the body is an untyped constant
  (`x => 2`) — convert the constant (`x => int64(2)`) or declare the type.

## 8. Uniform function call syntax

If `x.f(args)` does not denote a method, field, generic method or extension
method, it denotes the call `f(x, args)` of a package-level function `f`
whose first parameter accepts `x`.

## Resolution order of `x.f(…)`

1. a method or field of the type of `x` (Go semantics),
2. a generic method of the named type of `x`,
3. an extension method of this package or of an imported package,
4. a package-level function `f` (uniform function call syntax).

## Limitations

Version 1.0 has the following known limitations:

* A `match` over an enum must be written in the package that declares the
  enum (use methods of the enum to expose matching to other packages);
  constructors, methods and the enum type itself can be used everywhere.
* Default parameter values apply to calls in the declaring package; calls
  from other packages must pass all arguments (named arguments are
  supported).
* Patterns are not nested (`Some(Circle(r))`); match the inner value in the
  arm body.
* An arm of a match expression yields one value.
* The illustrative function type syntax `fn(T) U` used in the article is
  written `func(T) U`.
* Build constraints in `.gnx` file names (`_linux.gnx`) are not honoured;
  use `//go:build` lines in a Go file of the package instead.
