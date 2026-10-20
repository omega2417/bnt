package gnrt

import (
	"runtime"
	"sync/atomic"
	"testing"
	"time"
	"unsafe"
)

func TestBoolWord(t *testing.T) {
	type flag bool
	if BoolWord(true) != 1 || BoolWord(false) != 0 || BoolWord(flag(true)) != 1 {
		t.Error("BoolWord")
	}
}

func TestPtrRoundTrip(t *testing.T) {
	m := map[string]int{"a": 1}
	if FromPtr[map[string]int](Ptr(m))["a"] != 1 {
		t.Error("map round trip")
	}
	f := func(x int) int { return x + 1 }
	if FromPtr[func(int) int](Ptr(f))(1) != 2 {
		t.Error("func round trip")
	}
	c := make(chan int, 1)
	FromPtr[chan int](Ptr(c)) <- 3
	if <-c != 3 {
		t.Error("chan round trip")
	}
}

// TestPtrKeepsObjectsAlive checks that a value stored through Ptr in an
// unsafe.Pointer slot stays visible to the garbage collector.
func TestPtrKeepsObjectsAlive(t *testing.T) {
	var finalized atomic.Int32
	slots := make([]unsafe.Pointer, 100)
	for i := range slots {
		m := map[int]*int{0: new(int)}
		runtime.SetFinalizer(m[0], func(*int) { finalized.Add(1) })
		slots[i] = Ptr(m)
	}
	for i := 0; i < 3; i++ {
		runtime.GC()
		time.Sleep(10 * time.Millisecond)
	}
	if n := finalized.Load(); n != 0 {
		t.Errorf("%d objects reachable only through Ptr slots were finalized", n)
	}
	runtime.KeepAlive(slots)
}

func TestNonExhaustive(t *testing.T) {
	if (NonExhaustive{"Shape"}).Error() != "gonext: non-exhaustive match on Shape" {
		t.Error("message")
	}
}
