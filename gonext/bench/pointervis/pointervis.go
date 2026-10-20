// Package pointervis reproduces Experiment 4 of the GoNext manuscript
// (Section 2.6, Section 3.5, invariant (4) of Section 2.3, Table 7): an
// enum variant Ref(node *Node) whose pointer payload is stored in three
// ways:
//
//   - ModeUnsafePointer: in an unsafe.Pointer slot of the compact tagged
//     struct (representation R3, Listing 6) - visible to the collector;
//   - ModeInterface: as a boxed interface value (representation R1) -
//     visible to the collector;
//   - ModeUintptr: in a uintptr word, which is what a layout overlapping
//     all payloads in an integer buffer amounts to - invisible to the
//     collector.
//
// Each trial creates n nodes with finalizers, keeps them reachable only
// through the enum values, forces several GC cycles and counts how many
// nodes were finalized while the enum values were still alive.
//
// The uintptr variant never converts the integer back to a pointer, so
// the program never dereferences freed memory and go vet stays silent;
// the experiment only observes that the collector reclaimed the nodes.
package pointervis

import (
	"fmt"
	"runtime"
	"sync/atomic"
	"time"
	"unsafe"
)

// Mode selects how the pointer payload of variant Ref is stored.
type Mode string

// Storage modes of Experiment 4 (rows of Table 7).
const (
	ModeUnsafePointer Mode = "unsafe_pointer"
	ModeInterface     Mode = "interface"
	ModeUintptr       Mode = "uintptr"
)

// Modes lists the storage modes in the order of Table 7.
var Modes = []Mode{ModeUnsafePointer, ModeInterface, ModeUintptr}

// Node is the referenced object. It is larger than 16 bytes and contains
// a pointer, so it is never placed in the tiny allocator (finalizers on
// tiny objects may be delayed indefinitely).
type Node struct {
	ID   int
	Next *Node
	Pad  [4]int
}

// Tag of variant Ref.
const tagRef uint8 = 1

// refR3 is variant Ref under the compact representation R3 (Listing 6):
// the pointer payload lives in the unsafe.Pointer slot p.
type refR3 struct {
	tag        uint8
	w0, w1, w2 uint64
	p          unsafe.Pointer
	n          int
}

// refR1 is variant Ref under the sealed-interface representation R1.
type refR1 interface{ isRef() }

// refR1Node is the variant struct of Ref under R1.
type refR1Node struct{ node *Node }

func (refR1Node) isRef() {}

// refWord is variant Ref under a C-union-like layout in which all
// payloads overlap in integer words; the pointer is stored as a uintptr
// and is therefore invisible to Go's precise collector (violates (4)).
type refWord struct {
	tag        uint8
	w0, w1, w2 uintptr
}

// Result is the outcome of one trial.
type Result struct {
	Mode      Mode
	Trial     int
	Nodes     int
	Finalized int64
}

// newNode allocates a node whose finalizer increments counter.
func newNode(id int, counter *atomic.Int64) *Node {
	n := &Node{ID: id}
	runtime.SetFinalizer(n, func(*Node) { counter.Add(1) })
	return n
}

// The builders are not inlined so that no pointer to a node survives in
// the caller's stack frame: after they return, the nodes are reachable
// only through the enum values.

//go:noinline
func buildR3(n int, c *atomic.Int64) []refR3 {
	xs := make([]refR3, n)
	for i := range xs {
		xs[i] = refR3{tag: tagRef, p: unsafe.Pointer(newNode(i, c))}
	}
	return xs
}

//go:noinline
func buildR1(n int, c *atomic.Int64) []refR1 {
	xs := make([]refR1, n)
	for i := range xs {
		xs[i] = refR1Node{node: newNode(i, c)}
	}
	return xs
}

//go:noinline
func buildWord(n int, c *atomic.Int64) []refWord {
	xs := make([]refWord, n)
	for i := range xs {
		xs[i] = refWord{tag: tagRef, w0: uintptr(unsafe.Pointer(newNode(i, c)))}
	}
	return xs
}

// collect forces cycles garbage collections, pausing after each one so
// that the finalizer goroutine can run queued finalizers.
func collect(cycles int, pause time.Duration) {
	for i := 0; i < cycles; i++ {
		runtime.GC()
		time.Sleep(pause)
	}
}

// RunTrial runs one trial of Experiment 4: it creates n nodes reachable
// only through enum values stored in the given mode, forces cycles GC
// cycles and returns the number of nodes finalized while the enum values
// were still alive.
func RunTrial(mode Mode, n, cycles int) (int64, error) {
	counter := new(atomic.Int64) // one counter per trial
	const pause = 20 * time.Millisecond
	var finalized int64
	switch mode {
	case ModeUnsafePointer:
		xs := buildR3(n, counter)
		collect(cycles, pause)
		finalized = counter.Load()
		runtime.KeepAlive(xs)
	case ModeInterface:
		xs := buildR1(n, counter)
		collect(cycles, pause)
		finalized = counter.Load()
		runtime.KeepAlive(xs)
	case ModeUintptr:
		xs := buildWord(n, counter)
		collect(cycles, pause)
		finalized = counter.Load()
		runtime.KeepAlive(xs)
	default:
		return 0, fmt.Errorf("pointervis: unknown mode %q", mode)
	}
	// Release this trial's objects before the next trial starts.
	collect(2, pause)
	return finalized, nil
}

// Run executes trials trials for every mode with n nodes and cycles GC
// cycles per trial.
func Run(trials, n, cycles int) ([]Result, error) {
	var out []Result
	for _, m := range Modes {
		for t := 1; t <= trials; t++ {
			f, err := RunTrial(m, n, cycles)
			if err != nil {
				return nil, err
			}
			out = append(out, Result{Mode: m, Trial: t, Nodes: n, Finalized: f})
		}
	}
	return out, nil
}
