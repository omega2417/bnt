package namedargs

import "testing"

var sinkConn Conn

// BenchmarkNamedArgs measures one call with one named argument and two
// omitted defaulted parameters (Table 6 rows "Named/default call",
// Figure 4d).
func BenchmarkNamedArgs(b *testing.B) {
	b.Run("GoNext_positional", func(b *testing.B) {
		b.ReportAllocs()
		for i := 0; i < b.N; i++ {
			sinkConn = CallGoNext("example.org", 5)
		}
	})
	b.Run("Config_struct", func(b *testing.B) {
		b.ReportAllocs()
		for i := 0; i < b.N; i++ {
			sinkConn = CallConfig("example.org", 5)
		}
	})
	b.Run("Functional_options", func(b *testing.B) {
		b.ReportAllocs()
		for i := 0; i < b.N; i++ {
			sinkConn = CallOptions("example.org", 5)
		}
	})
}
