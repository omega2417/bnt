package genericmethod

import "testing"

var (
	sinkList  List[int]
	sinkSlice []int
	sinkInt   int
)

// BenchmarkMap compares the lowered generic method with lambda
// (Listing 4) with a hand-written loop on 4096 elements (Table 6).
func BenchmarkMap(b *testing.B) {
	xs := NewList(input())
	b.Run("GoNext_generic_method", func(b *testing.B) {
		b.ReportAllocs()
		for i := 0; i < b.N; i++ {
			sinkList = List_map(xs, func(x int) int { return x * 2 })
		}
	})
	b.Run("Handwritten_loop", func(b *testing.B) {
		b.ReportAllocs()
		for i := 0; i < b.N; i++ {
			out := make([]int, len(xs.items))
			for j, v := range xs.items {
				out[j] = v * 2
			}
			sinkSlice = out
		}
	})
}

// BenchmarkSum compares the lowered extension method (Listing 2) with a
// hand-written summation loop on 4096 elements (Table 6).
func BenchmarkSum(b *testing.B) {
	xs := input()
	b.Run("GoNext_extension_method", func(b *testing.B) {
		b.ReportAllocs()
		for i := 0; i < b.N; i++ {
			sinkInt += ext_IntSlice_sum(xs)
		}
	})
	b.Run("Handwritten_sum", func(b *testing.B) {
		b.ReportAllocs()
		for i := 0; i < b.N; i++ {
			t := 0
			for _, v := range xs {
				t += v
			}
			sinkInt += t
		}
	})
}
