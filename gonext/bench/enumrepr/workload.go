package enumrepr

import (
	"math/rand/v2"

	"github.com/ORGANIZATION/gonext/bench/enumrepr/r1"
	"github.com/ORGANIZATION/gonext/bench/enumrepr/r2"
	"github.com/ORGANIZATION/gonext/bench/enumrepr/r3"
)

// N is the number of enum values in the workload of Experiment 1.
const N = 65536

// Seed is the fixed workload seed of Experiment 1 (Table 2).
const Seed = 42

// Variant kinds of the workload (independent of any representation).
const (
	KindCircle uint8 = iota
	KindRect
	KindTriangle
	KindText
	numKinds
)

// Spec describes one value of the workload before it is lowered to a
// particular representation.
type Spec struct {
	Kind    uint8
	A, B, C float64
	S       string
}

// textPool holds the strings used by Text values. The strings are
// created once, so construction never allocates string data.
var textPool = func() []string {
	words := []string{
		"a", "go", "enum", "shape", "gonext", "variant", "transpile",
		"rectangle", "dispatching", "pattern match", "representation",
		"garbage collector", "sealed interface", "tagged union value",
		"compact tagged struct", "algebraic data types in Go",
	}
	return words
}()

// Workload returns the deterministic workload of Experiment 1: N values
// with variants drawn uniformly from {Circle, Rect, Triangle, Text} by a
// PCG generator seeded with Seed. Triangles always satisfy the triangle
// inequality, so Heron's formula is well defined.
func Workload() []Spec {
	rng := rand.New(rand.NewPCG(Seed, Seed))
	specs := make([]Spec, N)
	for i := range specs {
		k := uint8(rng.IntN(int(numKinds)))
		s := Spec{Kind: k}
		switch k {
		case KindCircle:
			s.A = 0.5 + 9.5*rng.Float64()
		case KindRect:
			s.A = 0.5 + 9.5*rng.Float64()
			s.B = 0.5 + 9.5*rng.Float64()
		case KindTriangle:
			a := 1 + 9*rng.Float64()
			b := 1 + 9*rng.Float64()
			lo, hi := a-b, a+b
			if lo < 0 {
				lo = -lo
			}
			// c strictly inside (|a-b|, a+b)
			c := lo + (hi-lo)*(0.05+0.9*rng.Float64())
			s.A, s.B, s.C = a, b, c
		case KindText:
			s.S = textPool[rng.IntN(len(textPool))]
		}
		specs[i] = s
	}
	return specs
}

// BuildR1 constructs the workload with representation R1 into dst.
func BuildR1(dst []r1.Shape, specs []Spec) {
	_ = dst[len(specs)-1]
	for i, s := range specs {
		switch s.Kind {
		case KindCircle:
			dst[i] = r1.NewShape_Circle(s.A)
		case KindRect:
			dst[i] = r1.NewShape_Rect(s.A, s.B)
		case KindTriangle:
			dst[i] = r1.NewShape_Triangle(s.A, s.B, s.C)
		default:
			dst[i] = r1.NewShape_Text(s.S)
		}
	}
}

// BuildR2 constructs the workload with representation R2 into dst.
func BuildR2(dst []r2.Shape, specs []Spec) {
	_ = dst[len(specs)-1]
	for i, s := range specs {
		switch s.Kind {
		case KindCircle:
			dst[i] = r2.NewShape_Circle(s.A)
		case KindRect:
			dst[i] = r2.NewShape_Rect(s.A, s.B)
		case KindTriangle:
			dst[i] = r2.NewShape_Triangle(s.A, s.B, s.C)
		default:
			dst[i] = r2.NewShape_Text(s.S)
		}
	}
}

// BuildR3 constructs the workload with representation R3 into dst.
func BuildR3(dst []r3.Shape, specs []Spec) {
	_ = dst[len(specs)-1]
	for i, s := range specs {
		switch s.Kind {
		case KindCircle:
			dst[i] = r3.NewShape_Circle(s.A)
		case KindRect:
			dst[i] = r3.NewShape_Rect(s.A, s.B)
		case KindTriangle:
			dst[i] = r3.NewShape_Triangle(s.A, s.B, s.C)
		default:
			dst[i] = r3.NewShape_Text(s.S)
		}
	}
}

// SumR1 applies the exhaustive match (measure) to every R1 value.
func SumR1(xs []r1.Shape) float64 {
	t := 0.0
	for _, x := range xs {
		t += r1.Measure(x)
	}
	return t
}

// SumR2 applies the exhaustive match (measure) to every R2 value.
func SumR2(xs []r2.Shape) float64 {
	t := 0.0
	for _, x := range xs {
		t += r2.Measure(x)
	}
	return t
}

// SumR3 applies the exhaustive match (measure) to every R3 value.
func SumR3(xs []r3.Shape) float64 {
	t := 0.0
	for _, x := range xs {
		t += r3.Measure(x)
	}
	return t
}
