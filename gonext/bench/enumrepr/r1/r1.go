// Package r1 is representation R1 of Experiment 1 (Section 3.3.3): the
// GoNext enum Shape of Listing 5 lowered to a sealed interface with one
// struct type per variant; match is lowered to a type switch.
package r1

import "math"

// Shape is the sealed interface for enum Shape (Listing 5, scheme R1).
// The unexported method seals the set of variants to this package.
type Shape interface{ isShape() }

// Shape_Circle is variant Circle(r float64).
type Shape_Circle struct{ R float64 }

// Shape_Rect is variant Rect(w, h float64).
type Shape_Rect struct{ W, H float64 }

// Shape_Triangle is variant Triangle(a, b, c float64).
type Shape_Triangle struct{ A, B, C float64 }

// Shape_Text is variant Text(s string).
type Shape_Text struct{ S string }

func (Shape_Circle) isShape()   {}
func (Shape_Rect) isShape()     {}
func (Shape_Triangle) isShape() {}
func (Shape_Text) isShape()     {}

// NewShape_Circle is the generated constructor for Circle (scheme R1).
func NewShape_Circle(r float64) Shape { return Shape_Circle{R: r} }

// NewShape_Rect is the generated constructor for Rect (scheme R1).
func NewShape_Rect(w, h float64) Shape { return Shape_Rect{W: w, H: h} }

// NewShape_Triangle is the generated constructor for Triangle (scheme R1).
func NewShape_Triangle(a, b, c float64) Shape { return Shape_Triangle{A: a, B: b, C: c} }

// NewShape_Text is the generated constructor for Text (scheme R1).
func NewShape_Text(s string) Shape { return Shape_Text{S: s} }

// Measure is the lowering of measure from Listing 5 under scheme R1: the
// exhaustive match becomes a type switch with a defensive default arm.
func Measure(s Shape) float64 {
	var r float64
	switch v := s.(type) {
	case Shape_Circle:
		r = math.Pi * v.R * v.R
	case Shape_Rect:
		r = v.W * v.H
	case Shape_Triangle:
		r = heron(v.A, v.B, v.C)
	case Shape_Text:
		r = float64(len(v.S))
	default:
		panic("gonext: non-exhaustive match on Shape")
	}
	return r
}

func heron(a, b, c float64) float64 {
	p := (a + b + c) / 2
	return math.Sqrt(p * (p - a) * (p - b) * (p - c))
}
