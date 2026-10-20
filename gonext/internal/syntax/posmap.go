package syntax

import "sort"

// segment maps a run of the rewritten text starting at Out to the original
// source starting at Orig. Synthetic segments map every byte to Orig.
type segment struct {
	Out, Orig int
	Synthetic bool
}

// PosMap translates byte offsets in the rewritten Go text back to offsets in
// the original GoNext source.
type PosMap struct {
	segs []segment
}

func (m *PosMap) add(out, orig int, synthetic bool) {
	if n := len(m.segs); n > 0 && m.segs[n-1].Out == out {
		m.segs[n-1] = segment{out, orig, synthetic}
		return
	}
	m.segs = append(m.segs, segment{out, orig, synthetic})
}

// Orig returns the original offset for the rewritten offset out.
func (m *PosMap) Orig(out int) int {
	i := sort.Search(len(m.segs), func(i int) bool { return m.segs[i].Out > out }) - 1
	if i < 0 {
		return out
	}
	s := m.segs[i]
	if s.Synthetic {
		return s.Orig
	}
	return s.Orig + out - s.Out
}
