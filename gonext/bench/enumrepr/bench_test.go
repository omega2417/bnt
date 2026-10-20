package enumrepr

import (
	"runtime"
	"testing"
	"unsafe"

	"github.com/ORGANIZATION/gonext/bench/enumrepr/r1"
	"github.com/ORGANIZATION/gonext/bench/enumrepr/r2"
	"github.com/ORGANIZATION/gonext/bench/enumrepr/r3"
)

var sinkF float64

// perValue reports the elapsed time of the benchmark loop per enum value.
func perValue(b *testing.B) {
	b.ReportMetric(float64(b.Elapsed().Nanoseconds())/(float64(b.N)*N), "ns/value")
}

// BenchmarkConstruct measures construction of N values into a
// preallocated slice (Table 6 rows "Enum construction", Figure 4a).
func BenchmarkConstruct(b *testing.B) {
	specs := Workload()
	b.Run("R1_interface", func(b *testing.B) {
		dst := make([]r1.Shape, N)
		b.ReportAllocs()
		b.ResetTimer()
		for i := 0; i < b.N; i++ {
			BuildR1(dst, specs)
		}
		perValue(b)
	})
	b.Run("R2_flat", func(b *testing.B) {
		dst := make([]r2.Shape, N)
		b.ReportAllocs()
		b.ResetTimer()
		for i := 0; i < b.N; i++ {
			BuildR2(dst, specs)
		}
		perValue(b)
	})
	b.Run("R3_compact", func(b *testing.B) {
		dst := make([]r3.Shape, N)
		b.ReportAllocs()
		b.ResetTimer()
		for i := 0; i < b.N; i++ {
			BuildR3(dst, specs)
		}
		perValue(b)
	})
}

// BenchmarkMatch measures the exhaustive match (measure) per value
// (Table 6 rows "Exhaustive match", Figure 4b).
func BenchmarkMatch(b *testing.B) {
	specs := Workload()
	b.Run("R1_interface", func(b *testing.B) {
		xs := make([]r1.Shape, N)
		BuildR1(xs, specs)
		b.ReportAllocs()
		b.ResetTimer()
		for i := 0; i < b.N; i++ {
			sinkF += SumR1(xs)
		}
		perValue(b)
	})
	b.Run("R2_flat", func(b *testing.B) {
		xs := make([]r2.Shape, N)
		BuildR2(xs, specs)
		b.ReportAllocs()
		b.ResetTimer()
		for i := 0; i < b.N; i++ {
			sinkF += SumR2(xs)
		}
		perValue(b)
	})
	b.Run("R3_compact", func(b *testing.B) {
		xs := make([]r3.Shape, N)
		BuildR3(xs, specs)
		b.ReportAllocs()
		b.ResetTimer()
		for i := 0; i < b.N; i++ {
			sinkF += SumR3(xs)
		}
		perValue(b)
	})
}

// memoryPerValue runs build b.N times on a preallocated slice and
// reports the slice footprint per element (unsafe.Sizeof) together with
// the heap bytes and heap allocations per value measured from
// runtime.MemStats over the whole benchmark loop (Figure 4c).
func memoryPerValue(b *testing.B, elemSize uintptr, build func()) {
	var before, after runtime.MemStats
	runtime.GC()
	runtime.ReadMemStats(&before)
	b.ResetTimer()
	for i := 0; i < b.N; i++ {
		build()
	}
	b.StopTimer()
	runtime.ReadMemStats(&after)
	values := float64(b.N) * N
	b.ReportMetric(float64(elemSize), "B/value-slice")
	b.ReportMetric(float64(after.TotalAlloc-before.TotalAlloc)/values, "B/value-heap")
	b.ReportMetric(float64(after.Mallocs-before.Mallocs)/values, "allocs/value")
}

// BenchmarkMemory reports the memory footprint per value.
func BenchmarkMemory(b *testing.B) {
	specs := Workload()
	b.Run("R1_interface", func(b *testing.B) {
		dst := make([]r1.Shape, N)
		memoryPerValue(b, unsafe.Sizeof(dst[0]), func() { BuildR1(dst, specs) })
	})
	b.Run("R2_flat", func(b *testing.B) {
		dst := make([]r2.Shape, N)
		memoryPerValue(b, unsafe.Sizeof(dst[0]), func() { BuildR2(dst, specs) })
	})
	b.Run("R3_compact", func(b *testing.B) {
		dst := make([]r3.Shape, N)
		memoryPerValue(b, unsafe.Sizeof(dst[0]), func() { BuildR3(dst, specs) })
	})
}
