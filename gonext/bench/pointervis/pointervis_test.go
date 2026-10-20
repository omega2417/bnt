package pointervis

import "testing"

// TestPointerVisibility checks invariant (4): pointer payloads stored in
// an unsafe.Pointer slot or an interface value keep their nodes alive.
// The uintptr result is only logged, because whether the collector
// reclaims the nodes depends on GC timing.
func TestPointerVisibility(t *testing.T) {
	const n, cycles, trials = 10000, 5, 2
	for _, m := range Modes {
		for i := 0; i < trials; i++ {
			f, err := RunTrial(m, n, cycles)
			if err != nil {
				t.Fatal(err)
			}
			t.Logf("mode=%s trial=%d finalized=%d/%d", m, i+1, f, n)
			if (m == ModeUnsafePointer || m == ModeInterface) && f != 0 {
				t.Errorf("mode %s: %d nodes finalized while still referenced", m, f)
			}
		}
	}
	if _, err := RunTrial("bogus", 1, 1); err == nil {
		t.Error("expected error for unknown mode")
	}
}
