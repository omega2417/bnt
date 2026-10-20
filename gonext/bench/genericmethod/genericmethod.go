// Package genericmethod reproduces Experiment 3 of the GoNext manuscript
// (Section 2.6, Sections 3.3.1-3.3.2, Listings 1-4, Table 6): a generic
// method with a short anonymous function, xs.map(x => x * 2), lifted to a
// top-level generic function, and an extension method xs.sum() lowered to
// a top-level function, each compared with a hand-written loop.
package genericmethod

// List is the generic list of Listing 3/Listing 4.
type List[T any] struct{ items []T }

// NewList wraps items in a List.
func NewList[T any](items []T) List[T] { return List[T]{items: items} }

// Items returns the elements of l.
func (l List[T]) Items() []T { return l.items }

// List_map is the lifted generic method of Listing 4: the receiver
// becomes the first parameter and the type parameters of the receiver and
// of the method are concatenated.
func List_map[T, U any](l List[T], f func(T) U) List[U] {
	out := make([]U, len(l.items))
	for i, v := range l.items {
		out[i] = f(v)
	}
	return List[U]{out}
}

// MapDouble is the lowered call site of Listing 4:
// ys := xs.map(x => x * 2) becomes
// ys := List_map(xs, func(x int) int { return x * 2 }).
func MapDouble(xs List[int]) List[int] {
	return List_map(xs, func(x int) int { return x * 2 })
}

// ext_IntSlice_sum is the extension method of Listing 1 lowered as in
// Listing 2: ext func (s []int) sum() int becomes a top-level function
// with the receiver as first argument.
func ext_IntSlice_sum(s []int) int {
	t := 0
	for _, v := range s {
		t += v
	}
	return t
}

// SumExt is the lowered call site total := xs.sum() of Listing 2.
func SumExt(xs []int) int { return ext_IntSlice_sum(xs) }
