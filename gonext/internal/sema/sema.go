// Package sema implements stage S3 of the GoNext transpiler: partial
// semantic analysis. The transpiler does not reimplement the Go type
// checker. It type-checks the partially lowered package with go/types in
// rounds and uses the recorded information only where lowering needs it:
// payload types of enums, the receiver type of extension, generic-method and
// UFCS calls, the callee of calls with named and default arguments, the
// expected function type of short anonymous functions and the result type of
// match expressions. Each round rewrites what has become decidable; the
// rounds stop at a fixed point.
package sema

import (
	"fmt"
	"go/ast"
	"go/token"
	"go/types"
	"strings"

	"github.com/ORGANIZATION/gonext/internal/astx"
	"github.com/ORGANIZATION/gonext/internal/iast"
	"github.com/ORGANIZATION/gonext/internal/lower"
	"github.com/ORGANIZATION/gonext/internal/normalize"
	"github.com/ORGANIZATION/gonext/internal/syntax"
)

// Config configures the analysis of a package.
type Config struct {
	Path     string         // import path of the package
	Importer types.Importer // importer for dependencies
	Repr     iast.Repr      // default enum representation
	MaxRound int
}

// Analyzer runs S3–S5 on one package.
type Analyzer struct {
	Cfg  Config
	Pkg  *iast.Package
	L    *lower.Lowerer
	N    *normalize.Normalizer
	Info *types.Info
	TPkg *types.Package
	// Errors of the last type-checking round.
	TypeErrs []types.Error

	defs             map[types.Object]*iast.Func
	parents          map[ast.Node]ast.Node
	pendingLambdaErr map[*ast.FuncLit]string
}

// New returns an analyzer for pkg.
func New(cfg Config, pkg *iast.Package) *Analyzer {
	if cfg.MaxRound == 0 {
		cfg.MaxRound = 40
	}
	a := &Analyzer{Cfg: cfg, Pkg: pkg}
	a.L = lower.New(pkg)
	a.L.TypeExpr = a.TypeExpr
	a.N = normalize.New(a.L)
	return a
}

func (a *Analyzer) files() []*ast.File {
	var fs []*ast.File
	for _, f := range a.Pkg.Files {
		fs = append(fs, f.AST)
	}
	return append(fs, a.Pkg.GoFiles...)
}

// check type-checks the current state of the package.
func (a *Analyzer) check() {
	a.Info = &types.Info{
		Types:      map[ast.Expr]types.TypeAndValue{},
		Defs:       map[*ast.Ident]types.Object{},
		Uses:       map[*ast.Ident]types.Object{},
		Selections: map[*ast.SelectorExpr]*types.Selection{},
		Instances:  map[*ast.Ident]types.Instance{},
		Implicits:  map[ast.Node]types.Object{},
	}
	a.TypeErrs = nil
	conf := types.Config{
		Importer: a.Cfg.Importer,
		Error: func(err error) {
			if te, ok := err.(types.Error); ok {
				a.TypeErrs = append(a.TypeErrs, te)
			}
		},
	}
	a.TPkg, _ = conf.Check(a.Cfg.Path, a.Pkg.Fset, a.files(), a.Info)
	a.defs = map[types.Object]*iast.Func{}
	for fd, fi := range a.Pkg.Funcs {
		if obj := a.Info.Defs[fd.Name]; obj != nil {
			a.defs[obj] = fi
		}
	}
}

// Run performs semantic analysis, normalization and lowering of the package.
func (a *Analyzer) Run() error {
	p := a.Pkg
	if err := p.Errs.Err(); err != nil {
		return err
	}
	a.L.LiftMethods()
	fix := map[ast.Node]ast.Node{}
	a.L.RewriteConstructors(fix)
	for _, m := range p.Matches {
		if r, ok := fix[m.Scrut]; ok {
			m.Scrut = r.(ast.Expr)
		}
		for _, arm := range m.Arms {
			if r, ok := fix[arm.Body]; ok {
				arm.Body = r.(ast.Expr)
			}
			if r, ok := fix[arm.Guard]; ok {
				arm.Guard = r.(ast.Expr)
			}
		}
	}
	// Round 0: payload types, using the flat representation.
	for _, e := range p.Enums {
		want := e.Repr
		if want == "" {
			want = a.Cfg.Repr
		}
		if e.Generic() && want != iast.ReprFlat {
			if e.Repr != "" {
				p.Errs = append(p.Errs, &syntax.Error{Pos: e.Decl.Pos, Msg: fmt.Sprintf("generic enum %s supports only the flat representation", e.Name)})
			}
			want = iast.ReprFlat
		}
		e.Repr = iast.ReprFlat
		if err := a.L.GenEnum(e); err != nil {
			return err
		}
		e.Repr = want
	}
	a.check()
	for _, e := range p.Enums {
		obj := a.TPkg.Scope().Lookup(e.Name)
		if obj == nil {
			continue
		}
		st, _ := obj.Type().Underlying().(*types.Struct)
		for _, v := range e.Variants {
			for _, fl := range v.Fields {
				for i := 0; st != nil && i < st.NumFields(); i++ {
					if st.Field(i).Name() == lower.FlatField(v, fl) {
						fl.T = st.Field(i).Type()
					}
				}
			}
		}
		if e.Repr == iast.ReprInterface {
			for _, f := range p.Files {
				for _, d := range f.AST.Decls {
					if fd, ok := d.(*ast.FuncDecl); ok && fd.Recv != nil && recvName(fd) == e.Name {
						p.Errorf(f, fd.Pos(), "enum %s in the interface representation cannot have methods; use the flat or compact representation", e.Name)
					}
				}
			}
		}
		if e.Repr == iast.ReprCompact {
			if err := a.L.ComputeLayout(e); err != nil {
				p.Errs = append(p.Errs, &syntax.Error{Pos: e.Decl.Pos, Msg: err.Error()})
				continue
			}
		}
		if e.Repr != iast.ReprFlat {
			if err := a.L.GenEnum(e); err != nil {
				return err
			}
		}
	}
	a.L.Matches()
	if err := p.Errs.Err(); err != nil {
		return err
	}
	// Rounds until a fixed point.
	for round := 0; round < a.Cfg.MaxRound; round++ {
		a.check()
		a.buildParents()
		changed := false
		for _, f := range p.Files {
			if a.resolveCalls(f) {
				changed = true
			}
		}
		if a.inferLambdas() {
			changed = true
		}
		if a.inferMatches() {
			changed = true
		}
		if err := p.Errs.Err(); err != nil {
			return err
		}
		if !changed {
			break
		}
	}
	a.reportUnresolved()
	if err := p.Errs.Err(); err != nil {
		return err
	}
	fz := &normalize.Finalizer{N: a.N, Info: a.Info, ResultType: a.resultType}
	fz.Run()
	return p.Errs.Err()
}

// Verify type-checks the final package and returns the errors reported by
// go/types at GoNext positions.
func (a *Analyzer) Verify() error {
	a.check()
	var errs syntax.ErrorList
	for _, te := range a.TypeErrs {
		pos := a.Pkg.Fset.Position(te.Pos)
		if f := a.Pkg.FileOf(te.Pos); f != nil {
			pos = f.Syn.Position(te.Pos)
		}
		errs = append(errs, &syntax.Error{Pos: pos, Msg: te.Msg})
	}
	return errs.Err()
}

func recvName(fd *ast.FuncDecl) string {
	t := fd.Recv.List[0].Type
	if st, ok := t.(*ast.StarExpr); ok {
		t = st.X
	}
	if id, ok := t.(*ast.Ident); ok {
		return id.Name
	}
	return ""
}

// TypeExpr converts t into a type expression valid in file f, adding imports
// as needed.
func (a *Analyzer) TypeExpr(f *iast.File, t types.Type) ast.Expr {
	t = types.Default(t)
	q := func(p *types.Package) string {
		if p == a.TPkg || p == nil {
			return ""
		}
		return astx.AddImport(f.AST, p.Path(), p.Name())
	}
	s := types.TypeString(t, q)
	x, err := iast.ParseExpr(s)
	if err != nil {
		return astx.Ident("invalid_type")
	}
	return x
}

func (a *Analyzer) buildParents() {
	a.parents = map[ast.Node]ast.Node{}
	for _, f := range a.Pkg.Files {
		var stack []ast.Node
		ast.Inspect(f.AST, func(n ast.Node) bool {
			if n == nil {
				stack = stack[:len(stack)-1]
				return false
			}
			if len(stack) > 0 {
				a.parents[n] = stack[len(stack)-1]
			}
			stack = append(stack, n)
			return true
		})
	}
}

func (a *Analyzer) resultType(f *iast.File, c *ast.CallExpr) *ast.FieldList {
	tv, ok := a.Info.Types[c]
	if !ok || tv.Type == nil {
		return nil
	}
	fl := &ast.FieldList{}
	if tup, ok := tv.Type.(*types.Tuple); ok {
		for i := 0; i < tup.Len(); i++ {
			fl.List = append(fl.List, &ast.Field{Type: a.TypeExpr(f, tup.At(i).Type())})
		}
		return fl
	}
	fl.List = []*ast.Field{{Type: a.TypeExpr(f, tv.Type)}}
	return fl
}

// imported returns the packages imported by file f and their local names.
func (a *Analyzer) imported(f *iast.File) map[*types.Package]string {
	out := map[*types.Package]string{}
	if a.TPkg == nil {
		return out
	}
	byPath := map[string]*types.Package{}
	for _, p := range a.TPkg.Imports() {
		byPath[p.Path()] = p
	}
	for _, is := range f.AST.Imports {
		path := strings.Trim(is.Path.Value, "\"`")
		p := byPath[path]
		if p == nil {
			continue
		}
		name := p.Name()
		if is.Name != nil {
			name = is.Name.Name
		}
		if name == "_" || name == "." {
			continue
		}
		out[p] = name
	}
	return out
}

// resolveCalls resolves extension, generic-method and UFCS calls and
// normalizes named and default arguments in file f.
func (a *Analyzer) resolveCalls(f *iast.File) bool {
	changed := false
	var calls []*ast.CallExpr
	ast.Inspect(f.AST, func(n ast.Node) bool {
		if c, ok := n.(*ast.CallExpr); ok {
			calls = append(calls, c)
		}
		return true
	})
	for _, c := range calls {
		if sel, ok := c.Fun.(*ast.SelectorExpr); ok {
			if a.resolveSelector(f, c, sel) {
				changed = true
				continue
			}
		}
		if a.normalizeCall(f, c) {
			changed = true
		}
	}
	return changed
}

func baseNamed(t types.Type) *types.Named {
	t = types.Unalias(t)
	if p, ok := t.(*types.Pointer); ok {
		t = types.Unalias(p.Elem())
	}
	n, _ := t.(*types.Named)
	return n
}

func (a *Analyzer) resolveSelector(f *iast.File, c *ast.CallExpr, sel *ast.SelectorExpr) bool {
	if _, ok := a.Info.Selections[sel]; ok {
		return false
	}
	if id, ok := sel.X.(*ast.Ident); ok {
		if _, isPkg := a.Info.Uses[id].(*types.PkgName); isPkg {
			return false
		}
	}
	tv, ok := a.Info.Types[sel.X]
	if !ok || tv.Type == nil || tv.IsType() || tv.Type == types.Typ[types.Invalid] {
		return false
	}
	tx := tv.Type
	if b, ok := tx.(*types.Basic); ok && b.Info()&types.IsUntyped != 0 {
		tx = types.Default(tx)
	}
	name := strings.TrimPrefix(sel.Sel.Name, syntax.KeywordPfx)
	imports := a.imported(f)
	qualify := func(fn *types.Func) ast.Expr {
		if fn.Pkg() == a.TPkg {
			return astx.Ident(fn.Name())
		}
		return astx.Sel(astx.Ident(imports[fn.Pkg()]), fn.Name())
	}
	var cands []*types.Func
	// generic method lifted to a top-level function
	if n := baseNamed(tx); n != nil && n.Obj().Pkg() != nil {
		pkg := n.Obj().Pkg()
		if pkg == a.TPkg || imports[pkg] != "" {
			if fn, ok := pkg.Scope().Lookup(lower.MethodName(n.Obj().Name(), name)).(*types.Func); ok && (pkg == a.TPkg || fn.Exported()) {
				cands = append(cands, fn)
			}
		}
	}
	// extension methods of this package and of imported packages
	if len(cands) == 0 {
		var exts []*types.Func
		for _, e := range a.Pkg.Exts {
			if e.Name == name {
				if fn, ok := a.Info.Defs[e.Decl.Name].(*types.Func); ok {
					exts = append(exts, fn)
				}
			}
		}
		for p := range imports {
			for _, n := range p.Scope().Names() {
				if strings.HasPrefix(n, "Ext_") && strings.HasSuffix(n, "_"+name) {
					if fn, ok := p.Scope().Lookup(n).(*types.Func); ok {
						exts = append(exts, fn)
					}
				}
			}
		}
		for _, fn := range exts {
			if a.recvMatches(tx, fn) {
				cands = append(cands, fn)
			}
		}
		if len(cands) > 1 {
			a.Pkg.Errorf(f, sel.Sel.Pos(), "ambiguous extension method %s for type %s", name, tx)
			return false
		}
	}
	// uniform function call syntax
	if len(cands) == 0 && a.TPkg != nil {
		if fn, ok := a.TPkg.Scope().Lookup(name).(*types.Func); ok && a.recvMatches(tx, fn) {
			cands = append(cands, fn)
		}
	}
	if len(cands) == 0 {
		return false
	}
	fn := cands[0]
	recv := sel.X
	p0 := fn.Type().(*types.Signature).Params().At(0).Type()
	_, wantPtr := under(p0).(*types.Pointer)
	_, havePtr := under(tx).(*types.Pointer)
	switch {
	case wantPtr && !havePtr:
		recv = &ast.UnaryExpr{Op: token.AND, X: recv}
	case !wantPtr && havePtr && baseNamed(tx) != nil && baseNamed(p0) == nil || (!wantPtr && havePtr && baseNamed(p0) != nil && !types.AssignableTo(tx, p0)):
		recv = &ast.StarExpr{X: recv}
	}
	a.N.Recv[c] = a.N.Recv[c] + 1
	c.Fun = qualify(fn)
	a.Pkg.Mark(c.Fun, sel.Pos())
	c.Args = append([]ast.Expr{recv}, c.Args...)
	return true
}

// recvMatches reports whether a value of type tx can be passed as the first
// argument of fn (allowing an implicit & or *).
func (a *Analyzer) recvMatches(tx types.Type, fn *types.Func) bool {
	sig := fn.Type().(*types.Signature)
	if sig.Params().Len() == 0 {
		return false
	}
	p0 := sig.Params().At(0).Type()
	try := func(t types.Type) bool {
		if sig.TypeParams().Len() > 0 {
			return unify(p0, t, sig.TypeParams(), map[*types.TypeParam]types.Type{})
		}
		return types.AssignableTo(t, p0)
	}
	if try(tx) {
		return true
	}
	if p, ok := under(tx).(*types.Pointer); ok && try(p.Elem()) {
		return true
	}
	return try(types.NewPointer(tx))
}

// callee returns the function object and signature of a call.
func (a *Analyzer) callee(c *ast.CallExpr) (types.Object, *types.Signature) {
	fun := ast.Unparen(c.Fun)
	switch x := fun.(type) {
	case *ast.IndexExpr:
		fun = x.X
	case *ast.IndexListExpr:
		fun = x.X
	}
	var obj types.Object
	switch x := fun.(type) {
	case *ast.Ident:
		obj = a.Info.Uses[x]
	case *ast.SelectorExpr:
		if s, ok := a.Info.Selections[x]; ok {
			obj = s.Obj()
		} else {
			obj = a.Info.Uses[x.Sel]
		}
	}
	if tv, ok := a.Info.Types[c.Fun]; ok && tv.Type != nil {
		if sig, ok := tv.Type.Underlying().(*types.Signature); ok && !tv.IsType() {
			// a failed inference records invalid type arguments; fall
			// back to the generic signature and unify ourselves
			if fn, isFn := obj.(*types.Func); !hasInvalid(sig) || !isFn {
				return obj, sig
			} else if gs := fn.Type().(*types.Signature); gs.TypeParams().Len() == 0 {
				return obj, sig
			}
		}
	}
	if fn, ok := obj.(*types.Func); ok {
		return obj, fn.Type().(*types.Signature)
	}
	if v, ok := obj.(*types.Var); ok {
		if sig, ok := v.Type().Underlying().(*types.Signature); ok {
			return obj, sig
		}
	}
	return obj, nil
}

func (a *Analyzer) normalizeCall(f *iast.File, c *ast.CallExpr) bool {
	named := normalize.HasNamed(c)
	obj, sig := a.callee(c)
	var fi *iast.Func
	if obj != nil {
		fi = a.defs[obj]
	}
	if !named && (fi == nil || c.Ellipsis.IsValid()) {
		return false
	}
	if sig == nil {
		return false
	}
	nparams := sig.Params().Len()
	if !named && len(c.Args) >= nparams {
		return false
	}
	var names []string
	for i := 0; i < nparams; i++ {
		names = append(names, sig.Params().At(i).Name())
	}
	defaults := map[int]ast.Expr{}
	if fi != nil {
		off := 0
		if fi.Lifted {
			off = 1
		}
		for i, d := range fi.Defaults {
			defaults[i+off] = d
		}
	}
	a.N.Call(f, c, names, sig.Variadic(), defaults)
	return true
}

// expected returns the type that the context of x expects, if known.
func (a *Analyzer) expected(x ast.Expr) types.Type {
	var child ast.Node = x
	parent := a.parents[x]
	for {
		if pe, ok := parent.(*ast.ParenExpr); ok {
			child, parent = pe, a.parents[pe]
			continue
		}
		break
	}
	switch p := parent.(type) {
	case *ast.CallExpr:
		if _, _, ok := normalize.NamedArg(p); ok {
			return nil
		}
		idx := -1
		for i, arg := range p.Args {
			if arg == child {
				idx = i
			}
		}
		if idx < 0 {
			return nil
		}
		return a.expectedArg(p, idx)
	case *ast.ValueSpec:
		if p.Type != nil {
			if tv, ok := a.Info.Types[p.Type]; ok {
				return tv.Type
			}
		}
	case *ast.AssignStmt:
		if p.Tok == token.ASSIGN && len(p.Lhs) == len(p.Rhs) {
			for i, r := range p.Rhs {
				if r == child {
					if tv, ok := a.Info.Types[p.Lhs[i]]; ok && tv.Type != nil {
						return tv.Type
					}
				}
			}
		}
	case *ast.ReturnStmt:
		for i, r := range p.Results {
			if r != child {
				continue
			}
			for n := a.parents[p]; n != nil; n = a.parents[n] {
				var sig *types.Signature
				switch fn := n.(type) {
				case *ast.FuncDecl:
					if obj := a.Info.Defs[fn.Name]; obj != nil {
						sig, _ = obj.Type().(*types.Signature)
					}
				case *ast.FuncLit:
					if a.isOpenLit(fn) {
						return nil
					}
					if tv, ok := a.Info.Types[fn]; ok {
						sig, _ = tv.Type.(*types.Signature)
					}
				default:
					continue
				}
				if sig != nil && i < sig.Results().Len() {
					return sig.Results().At(i).Type()
				}
				return nil
			}
		}
	case *ast.KeyValueExpr:
		if p.Value != child {
			return nil
		}
		if cl, ok := a.parents[p].(*ast.CompositeLit); ok {
			return a.elemType(cl, p.Key)
		}
	case *ast.CompositeLit:
		return a.elemType(p, nil)
	}
	return nil
}

func (a *Analyzer) isOpenLit(fl *ast.FuncLit) bool {
	if m := a.Pkg.Lambdas[fl]; m != nil {
		return iast.IsInfer(firstResult(fl))
	}
	for _, m := range a.Pkg.Matches {
		if m.Lit == fl {
			return iast.IsInfer(m.Result)
		}
	}
	return false
}

func firstResult(fl *ast.FuncLit) ast.Expr {
	if fl.Type.Results == nil || len(fl.Type.Results.List) == 0 {
		return nil
	}
	return fl.Type.Results.List[0].Type
}

func (a *Analyzer) elemType(cl *ast.CompositeLit, key ast.Expr) types.Type {
	tv, ok := a.Info.Types[cl]
	if !ok || tv.Type == nil {
		return nil
	}
	switch u := under(tv.Type).(type) {
	case *types.Slice:
		return u.Elem()
	case *types.Array:
		return u.Elem()
	case *types.Map:
		return u.Elem()
	case *types.Struct:
		if id, ok := key.(*ast.Ident); ok {
			for i := 0; i < u.NumFields(); i++ {
				if u.Field(i).Name() == id.Name {
					return u.Field(i).Type()
				}
			}
		}
	}
	return nil
}

// expectedArg returns the parameter type for argument idx of call c, with
// the type parameters of a generic callee bound from the other arguments.
// Parameters that remain unbound are returned as type parameters.
func (a *Analyzer) expectedArg(c *ast.CallExpr, idx int) types.Type {
	if normalize.HasNamed(c) {
		return nil
	}
	_, sig := a.callee(c)
	if sig == nil {
		return nil
	}
	n := sig.Params().Len()
	param := func(i int) types.Type {
		if sig.Variadic() && i >= n-1 {
			if c.Ellipsis.IsValid() {
				return sig.Params().At(n - 1).Type()
			}
			return sig.Params().At(n - 1).Type().(*types.Slice).Elem()
		}
		if i >= n {
			return nil
		}
		return sig.Params().At(i).Type()
	}
	pt := param(idx)
	if pt == nil {
		return nil
	}
	tps := sig.TypeParams()
	if tps.Len() == 0 {
		return pt
	}
	m := map[*types.TypeParam]types.Type{}
	for i, arg := range c.Args {
		if i == idx {
			continue
		}
		if fl, ok := arg.(*ast.FuncLit); ok && a.Pkg.Lambdas[fl] != nil && isOpen(fl) {
			continue
		}
		tv, ok := a.Info.Types[arg]
		if !ok || tv.Type == nil || tv.Type == types.Typ[types.Invalid] {
			continue
		}
		if p := param(i); p != nil {
			unify(p, types.Default(tv.Type), tps, m)
		}
	}
	return subst(pt, m)
}

func isOpen(fl *ast.FuncLit) bool {
	for _, p := range fl.Type.Params.List {
		if iast.IsInfer(p.Type) {
			return true
		}
	}
	return fl.Type.Results != nil && len(fl.Type.Results.List) > 0 && iast.IsInfer(fl.Type.Results.List[0].Type)
}

func (a *Analyzer) setLambdaType(fl *ast.FuncLit, f *iast.File, sig *types.Signature, inScope func(types.Type) bool) bool {
	changed := false
	j := 0
	for _, prm := range fl.Type.Params.List {
		n := len(prm.Names)
		if n == 0 {
			n = 1
		}
		if iast.IsInfer(prm.Type) && j < sig.Params().Len() {
			pt := sig.Params().At(j).Type()
			if inScope(pt) {
				prm.Type = a.TypeExpr(f, pt)
				changed = true
			}
		}
		j += n
	}
	return changed
}

// inferLambdas fills in parameter and result types of short anonymous
// functions from their context (bidirectional typing).
func (a *Analyzer) inferLambdas() bool {
	changed := false
	a.pendingLambdaErr = map[*ast.FuncLit]string{}
	for fl, lam := range a.Pkg.Lambdas {
		if !isOpen(fl) {
			continue
		}
		if _, ok := a.parents[fl]; !ok {
			continue // no longer in the tree
		}
		f := lam.File
		var sig *types.Signature
		if et := a.expected(fl); et != nil {
			sig, _ = under(et).(*types.Signature)
		}
		closed := func(t types.Type) bool { return !a.calleeTypeParam(t, fl) }
		if sig != nil {
			if a.setLambdaType(fl, f, sig, closed) {
				changed = true
			}
		}
		res := fl.Type.Results
		if res == nil || len(res.List) == 0 || !iast.IsInfer(res.List[0].Type) {
			continue
		}
		if sig != nil && sig.Results().Len() == 0 {
			fl.Type.Results = nil
			voidBody(fl)
			changed = true
			continue
		}
		if sig != nil && sig.Results().Len() == 1 && closed(sig.Results().At(0).Type()) {
			res.List[0].Type = a.TypeExpr(f, sig.Results().At(0).Type())
			changed = true
			continue
		}
		// synthesize the result type from the body
		for _, prm := range fl.Type.Params.List {
			if iast.IsInfer(prm.Type) {
				goto next
			}
		}
		{
			rets := returns(fl.Body)
			if len(rets) == 0 || len(rets[0].Results) == 0 {
				fl.Type.Results = nil
				changed = true
				continue
			}
			var list []*ast.Field
			for _, r := range rets[0].Results {
				tv, ok := a.Info.Types[r]
				if !ok || tv.Type == nil || tv.Type == types.Typ[types.Invalid] {
					goto next
				}
				if tup, ok := tv.Type.(*types.Tuple); ok {
					if tup.Len() == 0 {
						fl.Type.Results = nil
						voidBody(fl)
						changed = true
						goto next
					}
					for i := 0; i < tup.Len(); i++ {
						list = append(list, &ast.Field{Type: a.TypeExpr(f, tup.At(i).Type())})
					}
					continue
				}
				if b, ok := tv.Type.(*types.Basic); ok && b.Info()&types.IsUntyped != 0 && tv.Value != nil {
					a.pendingLambdaErr[fl] = fmt.Sprintf("cannot infer the result type of a short function from the untyped constant %s; convert it or declare the function type", astx.String(r))
					goto next
				}
				list = append(list, &ast.Field{Type: a.TypeExpr(f, tv.Type)})
			}
			fl.Type.Results = &ast.FieldList{List: list}
			changed = true
		}
	next:
	}
	return changed
}

// calleeTypeParam reports whether t mentions a type parameter that is not
// in scope at the lambda (a type parameter of the callee that is not yet
// inferred).
func (a *Analyzer) calleeTypeParam(t types.Type, at ast.Node) bool {
	if hasInvalid(t) {
		return true
	}
	found := false
	walk(t, func(tp *types.TypeParam) {
		if !a.tparamVisible(tp, at) {
			found = true
		}
	})
	return found
}

func (a *Analyzer) tparamVisible(tp *types.TypeParam, at ast.Node) bool {
	for n := a.parents[at]; n != nil; n = a.parents[n] {
		d, ok := n.(*ast.FuncDecl)
		if !ok {
			continue
		}
		found := false
		visit := func(x ast.Node) {
			ast.Inspect(x, func(y ast.Node) bool {
				if id, ok := y.(*ast.Ident); ok && a.Info.Defs[id] == tp.Obj() {
					found = true
				}
				return !found
			})
		}
		if d.Type.TypeParams != nil {
			visit(d.Type.TypeParams)
		}
		if d.Recv != nil {
			visit(d.Recv)
		}
		return found
	}
	return false
}

func voidBody(fl *ast.FuncLit) {
	if len(fl.Body.List) == 1 {
		if r, ok := fl.Body.List[0].(*ast.ReturnStmt); ok && len(r.Results) == 1 {
			fl.Body.List[0] = &ast.ExprStmt{X: r.Results[0]}
		}
	}
}

// returns lists the return statements of a function body, excluding those
// of nested function literals.
func returns(b *ast.BlockStmt) []*ast.ReturnStmt {
	var out []*ast.ReturnStmt
	ast.Inspect(b, func(n ast.Node) bool {
		switch n := n.(type) {
		case *ast.FuncLit:
			return false
		case *ast.ReturnStmt:
			out = append(out, n)
		}
		return true
	})
	return out
}

// inferMatches determines the result types of match expressions.
func (a *Analyzer) inferMatches() bool {
	changed := false
	for _, m := range a.Pkg.Matches {
		if m.Expr == nil || m.Done || !iast.IsInfer(m.Result) {
			continue
		}
		if _, ok := a.parents[m.Expr]; !ok {
			continue
		}
		f := m.File
		set := func(t types.Type) {
			x := a.TypeExpr(f, t)
			m.Lit.Type.Results.List[0].Type = x
			m.Result = x
			changed = true
		}
		et := a.expected(m.Expr)
		if et != nil && a.calleeTypeParam(et, m.Expr) {
			et = nil
		}
		if et != nil && !types.IsInterface(et) {
			set(et)
			continue
		}
		var typed types.Type
		var untyped []types.Type
		ok := true
		same := true
		for _, arm := range m.Arms {
			if arm.Body == nil || lower.IsPanic(arm.Body) {
				continue
			}
			tv, has := a.Info.Types[arm.Body]
			if !has || tv.Type == nil || hasInvalid(tv.Type) {
				ok = false
				continue
			}
			if b, isB := tv.Type.(*types.Basic); isB && b.Info()&types.IsUntyped != 0 {
				untyped = append(untyped, b)
				continue
			}
			if typed == nil {
				typed = tv.Type
			} else if !types.Identical(typed, tv.Type) {
				same = false
			}
		}
		if et != nil {
			// an interface is expected: keep the arms' common concrete type
			var common types.Type
			switch {
			case typed != nil && same && len(untyped) == 0:
				common = typed
			case typed == nil && len(untyped) > 0:
				common = types.Default(untyped[0])
				for _, u := range untyped[1:] {
					if u.(*types.Basic).Kind() != untyped[0].(*types.Basic).Kind() {
						common = nil
					}
				}
				if untyped[0].(*types.Basic).Kind() == types.UntypedNil {
					common = nil
				}
			}
			if ok && common != nil && types.AssignableTo(common, et) {
				set(common)
			} else if ok {
				set(et)
			}
			continue
		}
		// the first arm with a known type decides; untyped constants only
		// decide when every arm is known
		switch {
		case typed != nil:
			set(typed)
		case len(untyped) > 0 && ok:
			best := untyped[0].(*types.Basic)
			for _, u := range untyped[1:] {
				if b := u.(*types.Basic); rank(b) > rank(best) {
					best = b
				}
			}
			if best.Kind() == types.UntypedNil {
				a.Pkg.Errorf(f, m.Pos, "cannot infer the type of a match whose arms are all nil")
				continue
			}
			set(types.Default(best))
		}
	}
	return changed
}

func rank(b *types.Basic) int {
	switch b.Kind() {
	case types.UntypedInt:
		return 1
	case types.UntypedRune:
		return 2
	case types.UntypedFloat:
		return 3
	case types.UntypedComplex:
		return 4
	}
	return 0
}

func (a *Analyzer) reportUnresolved() {
	for fl, lam := range a.Pkg.Lambdas {
		if _, ok := a.parents[fl]; !ok || !isOpen(fl) {
			continue
		}
		if msg, ok := a.pendingLambdaErr[fl]; ok {
			a.Pkg.Errorf(lam.File, fl.Pos(), "%s", msg)
			continue
		}
		for _, prm := range fl.Type.Params.List {
			if iast.IsInfer(prm.Type) {
				a.Pkg.Errorf(lam.File, fl.Pos(), "cannot infer the parameter types of a short function here; declare them, as in (x int) => ...")
				goto next
			}
		}
		a.Pkg.Errorf(lam.File, fl.Pos(), "cannot infer the result type of a short function")
	next:
	}
	for _, m := range a.Pkg.Matches {
		if m.Expr != nil && !m.Done && iast.IsInfer(m.Result) {
			if _, ok := a.parents[m.Expr]; ok {
				a.Pkg.Errorf(m.File, m.Pos, "cannot infer the result type of the match expression")
			}
		}
	}
}

// hasInvalid reports whether t contains the invalid type (for example a type
// argument that go/types could not infer yet).
func hasInvalid(t types.Type) bool {
	found := false
	var visit func(t types.Type)
	visit = func(t types.Type) {
		switch t := t.(type) {
		case *types.Basic:
			if t.Kind() == types.Invalid {
				found = true
			}
		case *types.Pointer:
			visit(t.Elem())
		case *types.Slice:
			visit(t.Elem())
		case *types.Array:
			visit(t.Elem())
		case *types.Map:
			visit(t.Key())
			visit(t.Elem())
		case *types.Chan:
			visit(t.Elem())
		case *types.Signature:
			visit(t.Params())
			visit(t.Results())
		case *types.Tuple:
			for i := 0; i < t.Len(); i++ {
				visit(t.At(i).Type())
			}
		case *types.Named:
			for i := 0; i < t.TypeArgs().Len(); i++ {
				visit(t.TypeArgs().At(i))
			}
		}
	}
	visit(t)
	return found
}
