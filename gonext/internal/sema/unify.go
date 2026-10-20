package sema

import "go/types"

// unify matches parameter type p against argument type a and records
// bindings of the type parameters in tps.
func unify(p, a types.Type, tps *types.TypeParamList, m map[*types.TypeParam]types.Type) bool {
	if tp, ok := p.(*types.TypeParam); ok && inList(tp, tps) {
		if b, ok := m[tp]; ok {
			return types.Identical(b, a)
		}
		m[tp] = a
		return true
	}
	switch p := p.(type) {
	case *types.Pointer:
		if q, ok := under(a).(*types.Pointer); ok {
			return unify(p.Elem(), q.Elem(), tps, m)
		}
	case *types.Slice:
		if q, ok := under(a).(*types.Slice); ok {
			return unify(p.Elem(), q.Elem(), tps, m)
		}
	case *types.Array:
		if q, ok := under(a).(*types.Array); ok && q.Len() == p.Len() {
			return unify(p.Elem(), q.Elem(), tps, m)
		}
	case *types.Map:
		if q, ok := under(a).(*types.Map); ok {
			return unify(p.Key(), q.Key(), tps, m) && unify(p.Elem(), q.Elem(), tps, m)
		}
	case *types.Chan:
		if q, ok := under(a).(*types.Chan); ok {
			return unify(p.Elem(), q.Elem(), tps, m)
		}
	case *types.Signature:
		if q, ok := under(a).(*types.Signature); ok {
			return unifyTuple(p.Params(), q.Params(), tps, m) && unifyTuple(p.Results(), q.Results(), tps, m)
		}
	case *types.Named:
		if q, ok := types.Unalias(a).(*types.Named); ok && q.Origin() == p.Origin() {
			pa, qa := p.TypeArgs(), q.TypeArgs()
			if pa.Len() != qa.Len() {
				return false
			}
			for i := 0; i < pa.Len(); i++ {
				if !unify(pa.At(i), qa.At(i), tps, m) {
					return false
				}
			}
			return true
		}
	}
	if !mentions(p, tps) {
		return types.AssignableTo(a, p)
	}
	return false
}

func unifyTuple(p, a *types.Tuple, tps *types.TypeParamList, m map[*types.TypeParam]types.Type) bool {
	if p.Len() != a.Len() {
		return false
	}
	for i := 0; i < p.Len(); i++ {
		if !unify(p.At(i).Type(), a.At(i).Type(), tps, m) {
			return false
		}
	}
	return true
}

func under(t types.Type) types.Type { return types.Unalias(t).Underlying() }

func inList(tp *types.TypeParam, l *types.TypeParamList) bool {
	for i := 0; l != nil && i < l.Len(); i++ {
		if l.At(i) == tp {
			return true
		}
	}
	return false
}

// mentions reports whether t refers to a type parameter in l.
func mentions(t types.Type, l *types.TypeParamList) bool {
	found := false
	walk(t, func(tp *types.TypeParam) {
		if inList(tp, l) {
			found = true
		}
	})
	return found
}

// unresolved reports whether t mentions a type parameter of l that has no
// binding in m.
func unresolved(t types.Type, l *types.TypeParamList, m map[*types.TypeParam]types.Type) bool {
	found := false
	walk(t, func(tp *types.TypeParam) {
		if inList(tp, l) {
			if _, ok := m[tp]; !ok {
				found = true
			}
		}
	})
	return found
}

func walk(t types.Type, f func(*types.TypeParam)) {
	switch t := t.(type) {
	case *types.TypeParam:
		f(t)
	case *types.Pointer:
		walk(t.Elem(), f)
	case *types.Slice:
		walk(t.Elem(), f)
	case *types.Array:
		walk(t.Elem(), f)
	case *types.Map:
		walk(t.Key(), f)
		walk(t.Elem(), f)
	case *types.Chan:
		walk(t.Elem(), f)
	case *types.Signature:
		for i := 0; i < t.Params().Len(); i++ {
			walk(t.Params().At(i).Type(), f)
		}
		for i := 0; i < t.Results().Len(); i++ {
			walk(t.Results().At(i).Type(), f)
		}
	case *types.Named:
		for i := 0; i < t.TypeArgs().Len(); i++ {
			walk(t.TypeArgs().At(i), f)
		}
	case *types.Tuple:
		for i := 0; i < t.Len(); i++ {
			walk(t.At(i).Type(), f)
		}
	}
}

// subst replaces bound type parameters in t.
func subst(t types.Type, m map[*types.TypeParam]types.Type) types.Type {
	switch t := t.(type) {
	case *types.TypeParam:
		if b, ok := m[t]; ok {
			return b
		}
	case *types.Pointer:
		return types.NewPointer(subst(t.Elem(), m))
	case *types.Slice:
		return types.NewSlice(subst(t.Elem(), m))
	case *types.Array:
		return types.NewArray(subst(t.Elem(), m), t.Len())
	case *types.Map:
		return types.NewMap(subst(t.Key(), m), subst(t.Elem(), m))
	case *types.Chan:
		return types.NewChan(t.Dir(), subst(t.Elem(), m))
	case *types.Signature:
		return types.NewSignatureType(nil, nil, nil, substTuple(t.Params(), m), substTuple(t.Results(), m), t.Variadic())
	case *types.Named:
		args := t.TypeArgs()
		if args.Len() == 0 {
			return t
		}
		var nargs []types.Type
		for i := 0; i < args.Len(); i++ {
			nargs = append(nargs, subst(args.At(i), m))
		}
		if inst, err := types.Instantiate(nil, t.Origin(), nargs, false); err == nil {
			return inst
		}
	}
	return t
}

func substTuple(t *types.Tuple, m map[*types.TypeParam]types.Type) *types.Tuple {
	var vs []*types.Var
	for i := 0; i < t.Len(); i++ {
		v := t.At(i)
		vs = append(vs, types.NewVar(v.Pos(), v.Pkg(), v.Name(), subst(v.Type(), m)))
	}
	return types.NewTuple(vs...)
}
