package enumrepr

import (
	"math"
	"testing"
	"unsafe"

	"github.com/ORGANIZATION/gonext/bench/enumrepr/r1"
	"github.com/ORGANIZATION/gonext/bench/enumrepr/r2"
	"github.com/ORGANIZATION/gonext/bench/enumrepr/r3"
)

// TestEquivalence verifies that R1, R2 and R3 compute bit-identical
// results of measure for every value of the workload (Section 2.6).
func TestEquivalence(t *testing.T) {
	specs := Workload()
	x1 := make([]r1.Shape, N)
	x2 := make([]r2.Shape, N)
	x3 := make([]r3.Shape, N)
	BuildR1(x1, specs)
	BuildR2(x2, specs)
	BuildR3(x3, specs)
	var counts [numKinds]int
	for i, s := range specs {
		counts[s.Kind]++
		m1, m2, m3 := r1.Measure(x1[i]), r2.Measure(x2[i]), r3.Measure(x3[i])
		if math.Float64bits(m1) != math.Float64bits(m2) || math.Float64bits(m1) != math.Float64bits(m3) {
			t.Fatalf("value %d (%+v): R1=%v R2=%v R3=%v", i, s, m1, m2, m3)
		}
		if math.IsNaN(m1) || m1 < 0 {
			t.Fatalf("value %d (%+v): invalid measure %v", i, s, m1)
		}
	}
	if a, b, c := SumR1(x1), SumR2(x2), SumR3(x3); a != b || a != c {
		t.Fatalf("sums differ: %v %v %v", a, b, c)
	}
	for k, c := range counts {
		// uniform distribution: each variant close to N/4
		if c < N/4-1000 || c > N/4+1000 {
			t.Errorf("variant %d occurs %d times, expected about %d", k, c, N/4)
		}
	}
	t.Logf("variant counts (Circle, Rect, Triangle, Text): %v", counts)
}

// TestWorkloadDeterministic checks that the workload depends only on Seed.
func TestWorkloadDeterministic(t *testing.T) {
	a, b := Workload(), Workload()
	for i := range a {
		if a[i] != b[i] {
			t.Fatalf("workload differs at %d", i)
		}
	}
}

// TestSizes checks the per-element footprints reported in Section 3.4.
func TestSizes(t *testing.T) {
	if unsafe.Sizeof(uintptr(0)) != 8 {
		t.Skip("sizes are documented for 64-bit platforms")
	}
	if s := unsafe.Sizeof(r1.Shape(nil)); s != 16 {
		t.Errorf("R1 element size %d, want 16", s)
	}
	if s := unsafe.Sizeof(r2.Shape{}); s != 72 {
		t.Errorf("R2 element size %d, want 72", s)
	}
	if s := unsafe.Sizeof(r3.Shape{}); s != 48 {
		t.Errorf("R3 element size %d, want 48", s)
	}
}

// TestDefaultArmPanics checks the defensive default branch of the
// lowered match for values not built by a constructor.
func TestDefaultArmPanics(t *testing.T) {
	for name, f := range map[string]func(){
		"R1": func() { r1.Measure(nil) },
		"R2": func() { r2.Measure(r2.Shape{}) },
		"R3": func() { r3.Measure(r3.Shape{}) },
	} {
		func() {
			defer func() {
				if r := recover(); r != "gonext: non-exhaustive match on Shape" {
					t.Errorf("%s: recovered %v", name, r)
				}
			}()
			f()
		}()
	}
}
