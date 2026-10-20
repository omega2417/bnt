// Package enumrepr reproduces Experiment 1 of the GoNext manuscript
// (Section 2.6, Section 3.3.3, Listings 5 and 6, Table 6, Figure 4a-c):
// the GoNext enum
//
//	enum Shape {
//	    Circle(r float64)
//	    Rect(w float64, h float64)
//	    Triangle(a float64, b float64, c float64)
//	    Text(s string)
//	}
//
// lowered to standard Go with three representations:
//
//   - R1 (package r1): sealed interface, one struct type per variant,
//     match lowered to a type switch;
//   - R2 (package r2): flat tagged struct holding the union of all
//     variant fields;
//   - R3 (package r3): compact tagged struct with three shared scalar
//     words, one unsafe.Pointer slot and a length word (Listing 6).
//
// This package holds the deterministic workload (65,536 values, uniform
// variants, seed 42), the construction/match drivers, the equivalence
// test and the benchmarks.
package enumrepr
