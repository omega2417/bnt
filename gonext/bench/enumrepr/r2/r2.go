// Package r2 is representation R2 of Experiment 1 (Section 3.3.3): the
// GoNext enum Shape of Listing 5 lowered to one flat tagged struct that
// contains the union of all variant fields.
package r2

import "math"

// Tag constants of enum Shape (scheme R2). The zero tag is invalid, so a
// zero Shape value reaches the defensive default arm of a match.
const (
	Shape_Circle uint8 = 1 + iota
	Shape_Rect
	Shape_Triangle
	Shape_Text
)

// Shape is the flat tagged struct for enum Shape (scheme R2): every
// variant field has its own slot (72 bytes on 64-bit platforms).
type Shape struct {
	tag        uint8
	circle_r   float64
	rect_w     float64
	rect_h     float64
	triangle_a float64
	triangle_b float64
	triangle_c float64
	text_s     string
}

// NewShape_Circle is the generated constructor for Circle (scheme R2).
func NewShape_Circle(r float64) Shape { return Shape{tag: Shape_Circle, circle_r: r} }

// NewShape_Rect is the generated constructor for Rect (scheme R2).
func NewShape_Rect(w, h float64) Shape { return Shape{tag: Shape_Rect, rect_w: w, rect_h: h} }

// NewShape_Triangle is the generated constructor for Triangle (scheme R2).
func NewShape_Triangle(a, b, c float64) Shape {
	return Shape{tag: Shape_Triangle, triangle_a: a, triangle_b: b, triangle_c: c}
}

// NewShape_Text is the generated constructor for Text (scheme R2).
func NewShape_Text(s string) Shape { return Shape{tag: Shape_Text, text_s: s} }

// Measure is the lowering of measure from Listing 5 under scheme R2: the
// exhaustive match becomes a switch on the tag.
func Measure(s Shape) float64 {
	var r float64
	switch s.tag {
	case Shape_Circle:
		r = math.Pi * s.circle_r * s.circle_r
	case Shape_Rect:
		r = s.rect_w * s.rect_h
	case Shape_Triangle:
		r = heron(s.triangle_a, s.triangle_b, s.triangle_c)
	case Shape_Text:
		r = float64(len(s.text_s))
	default:
		panic("gonext: non-exhaustive match on Shape")
	}
	return r
}

func heron(a, b, c float64) float64 {
	p := (a + b + c) / 2
	return math.Sqrt(p * (p - a) * (p - b) * (p - c))
}
