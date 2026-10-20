package genericmethod

import (
	"math/rand/v2"
	"testing"
)

// Elems is the input size of Experiment 3.
const Elems = 4096

func input() []int {
	rng := rand.New(rand.NewPCG(42, 42))
	xs := make([]int, Elems)
	for i := range xs {
		xs[i] = rng.IntN(1<<20) - 1<<19
	}
	return xs
}

// handMap is the hand-written loop that a Go programmer writes instead of
// xs.map(x => x * 2).
func handMap(xs []int) []int {
	out := make([]int, len(xs))
	for i, v := range xs {
		out[i] = v * 2
	}
	return out
}

// TestEquivalence verifies that the lowered generic method and extension
// method compute the same results as the hand-written loops.
func TestEquivalence(t *testing.T) {
	xs := input()
	got := MapDouble(NewList(xs)).Items()
	want := handMap(xs)
	if len(got) != len(want) {
		t.Fatalf("length %d, want %d", len(got), len(want))
	}
	for i := range want {
		if got[i] != want[i] {
			t.Fatalf("element %d: %d, want %d", i, got[i], want[i])
		}
	}
	s := 0
	for _, v := range xs {
		s += v
	}
	if e := SumExt(xs); e != s {
		t.Fatalf("sum %d, want %d", e, s)
	}
	// A generic method whose result type differs from the receiver's.
	strs := List_map(NewList([]int{1, 22, 333}), func(x int) string { return string(rune('a' + x%26)) })
	if got := strs.Items(); len(got) != 3 || got[0] != "b" || got[1] != "w" || got[2] != "v" {
		t.Fatalf("List_map[int,string] = %q", got)
	}
}
