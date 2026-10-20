// Package r3 is representation R3 of Experiment 1 (Section 3.3.3): the
// GoNext enum Shape of Listing 5 lowered to the compact tagged struct of
// Listing 6. Scalar payloads of different variants share three machine
// words; the only pointer payload (the string data of Text) is kept in a
// slot of type unsafe.Pointer so that it stays visible to the collector
// (invariant (4) of Section 2.3).
package r3

import (
	"math"
	"unsafe"
)

// Tag constants of enum Shape (scheme R3). The zero tag is invalid.
const (
	Shape_Circle uint8 = 1 + iota
	Shape_Rect
	Shape_Triangle
	Shape_Text
)

// Shape is the compact tagged struct of Listing 6 (48 bytes on 64-bit
// platforms).
type Shape struct {
	tag        uint8
	w0, w1, w2 uint64         // scalar payload words shared by variants
	p          unsafe.Pointer // pointer payload: visible to the collector
	n          int
}

// NewShape_Circle is the generated constructor for Circle (Listing 6).
func NewShape_Circle(r float64) Shape {
	return Shape{tag: Shape_Circle, w0: math.Float64bits(r)}
}

// NewShape_Rect is the generated constructor for Rect (scheme R3).
func NewShape_Rect(w, h float64) Shape {
	return Shape{tag: Shape_Rect, w0: math.Float64bits(w), w1: math.Float64bits(h)}
}

// NewShape_Triangle is the generated constructor for Triangle (scheme R3).
func NewShape_Triangle(a, b, c float64) Shape {
	return Shape{tag: Shape_Triangle,
		w0: math.Float64bits(a), w1: math.Float64bits(b), w2: math.Float64bits(c)}
}

// NewShape_Text is the generated constructor for Text (scheme R3): the
// string is stored as its data pointer in p and its length in n.
func NewShape_Text(s string) Shape {
	return Shape{tag: Shape_Text, p: unsafe.Pointer(unsafe.StringData(s)), n: len(s)}
}

// text reconstructs the string payload of a Text value.
func (s Shape) text() string { return unsafe.String((*byte)(s.p), s.n) }

// Measure is the lowering of measure from Listing 5 shown in Listing 6.
func Measure(s Shape) float64 {
	var r float64
	switch s.tag {
	case Shape_Circle:
		rad := math.Float64frombits(s.w0)
		r = math.Pi * rad * rad
	case Shape_Rect:
		r = math.Float64frombits(s.w0) * math.Float64frombits(s.w1)
	case Shape_Triangle:
		r = heron(math.Float64frombits(s.w0), math.Float64frombits(s.w1), math.Float64frombits(s.w2))
	case Shape_Text:
		r = float64(len(s.text()))
	default:
		panic("gonext: non-exhaustive match on Shape")
	}
	return r
}

func heron(a, b, c float64) float64 {
	p := (a + b + c) / 2
	return math.Sqrt(p * (p - a) * (p - b) * (p - c))
}
