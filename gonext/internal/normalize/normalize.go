// Package normalize implements stage S4 of the GoNext transpiler: the
// rewriting of extension constructs into a small core. Calls with named and
// default arguments become positional calls, with temporaries that preserve
// the source order of evaluation; match expressions become a result
// variable and a switch statement placed before the statement that uses
// them.
package normalize

import (
	"go/ast"
	"go/token"
	"go/types"

	"github.com/ORGANIZATION/gonext/internal/astx"
	"github.com/ORGANIZATION/gonext/internal/iast"
	"github.com/ORGANIZATION/gonext/internal/lower"
	"github.com/ORGANIZATION/gonext/internal/syntax"
)

// Normalizer rewrites the calls and matches of one package.
type Normalizer struct {
	Pkg *iast.Package
	L   *lower.Lowerer
	// Temps holds, for every normalized call, the temporaries that must be
	// evaluated before it.
	Temps map[*ast.CallExpr][]*ast.AssignStmt
	// Recv is the number of leading arguments of a call that came from a
	// receiver (uniform function call syntax, extension and generic
	// methods); they cannot be passed by name.
	Recv map[*ast.CallExpr]int
}

// New returns a normalizer.
func New(l *lower.Lowerer) *Normalizer {
	return &Normalizer{Pkg: l.Pkg, L: l, Temps: map[*ast.CallExpr][]*ast.AssignStmt{}, Recv: map[*ast.CallExpr]int{}}
}

// NamedArg returns the name and value of a named-argument placeholder.
func NamedArg(x ast.Expr) (string, ast.Expr, bool) {
	c, ok := x.(*ast.CallExpr)
	if !ok || len(c.Args) != 2 {
		return "", nil, false
	}
	id, ok := c.Fun.(*ast.Ident)
	if !ok || id.Name != syntax.NamedFunc {
		return "", nil, false
	}
	lit := c.Args[0].(*ast.BasicLit)
	return lit.Value[1 : len(lit.Value)-1], c.Args[1], true
}

// HasNamed reports whether call c has named arguments.
func HasNamed(c *ast.CallExpr) bool {
	for _, a := range c.Args {
		if _, _, ok := NamedArg(a); ok {
			return true
		}
	}
	return false
}

func (n *Normalizer) errorf(f *iast.File, pos token.Pos, format string, args ...any) {
	n.Pkg.Errorf(f, pos, format, args...)
}

// Call rewrites the arguments of c into a positional argument list. params
// are the parameter names of the callee, variadic reports whether the last
// one is variadic, and defaults maps parameter indexes to default values.
func (n *Normalizer) Call(f *iast.File, c *ast.CallExpr, params []string, variadic bool, defaults map[int]ast.Expr) {
	skip := n.Recv[c]
	type arg struct {
		x     ast.Expr
		param int
	}
	var src []arg // explicit arguments in source order
	final := make([]ast.Expr, len(params))
	var tail []ast.Expr
	named := false
	for i, a := range c.Args {
		if name, val, ok := NamedArg(a); ok {
			named = true
			idx := -1
			for j := skip; j < len(params); j++ {
				if params[j] == name {
					idx = j
				}
			}
			switch {
			case idx < 0:
				n.errorf(f, a.Pos(), "unknown parameter name %s", name)
				return
			case variadic && idx == len(params)-1:
				n.errorf(f, a.Pos(), "variadic parameter %s cannot be passed by name", name)
				return
			case final[idx] != nil:
				n.errorf(f, a.Pos(), "parameter %s given more than once", name)
				return
			}
			final[idx] = val
			src = append(src, arg{val, idx})
			continue
		}
		if named {
			n.errorf(f, a.Pos(), "positional argument after named argument")
			return
		}
		if variadic && i >= len(params)-1 {
			tail = append(tail, a)
			src = append(src, arg{a, len(params) - 1})
			continue
		}
		if i >= len(params) {
			n.errorf(f, a.Pos(), "too many arguments")
			return
		}
		final[i] = a
		src = append(src, arg{a, i})
	}
	if named && c.Ellipsis.IsValid() {
		n.errorf(f, c.Ellipsis, "cannot use ... with named arguments")
		return
	}
	// defaults are evaluated after the explicit arguments
	evalOrder := append([]arg(nil), src...)
	last := len(params)
	if variadic {
		last--
	}
	for i := 0; i < last; i++ {
		if final[i] != nil {
			continue
		}
		d, ok := defaults[i]
		if !ok {
			n.errorf(f, c.Rparen, "missing argument for parameter %s", params[i])
			return
		}
		x := astx.Clone(d)
		astx.ClearPos(x)
		final[i] = x
		evalOrder = append(evalOrder, arg{x, i})
	}
	// does positional evaluation change the order of impure arguments?
	reordered := false
	prev := -1
	for _, a := range evalOrder {
		if astx.IsPure(a.x) {
			continue
		}
		if a.param < prev {
			reordered = true
		}
		prev = a.param
	}
	if reordered {
		for _, a := range src {
			if astx.IsPure(a.x) {
				continue
			}
			name := n.L.Fresh("gnArg")
			t := astx.Define([]string{name}, a.x)
			n.Pkg.Mark(t, a.x.Pos())
			n.Temps[c] = append(n.Temps[c], t)
			for i := range final {
				if final[i] == a.x {
					final[i] = astx.Ident(name)
				}
			}
			for i := range tail {
				if tail[i] == a.x {
					tail[i] = astx.Ident(name)
				}
			}
		}
	}
	if variadic {
		final = append(final[:len(final)-1], tail...)
	}
	c.Args = final
}

// Finalizer places the temporaries of normalized calls and the statement
// form of match expressions in front of the statements that use them. Where
// moving an evaluation would change the order of effects (after an earlier
// call in the same statement, in the right operand of && or ||, in a loop
// condition or a case expression), the construct stays an immediately
// invoked function literal.
type Finalizer struct {
	N       *Normalizer
	Info    *types.Info
	Matches map[*ast.CallExpr]*iast.Match
	// ResultType returns the result type expression of a call in file f.
	ResultType func(f *iast.File, c *ast.CallExpr) *ast.FieldList
	file       *iast.File
	cur        token.Pos // position of the statement being finalized
}

// Run finalizes every file of the package.
func (z *Finalizer) Run() {
	z.Matches = map[*ast.CallExpr]*iast.Match{}
	for _, m := range z.N.Pkg.Matches {
		if m.Expr != nil && !m.Done {
			z.Matches[m.Expr] = m
		}
	}
	for _, f := range z.N.Pkg.Files {
		z.file = f
		for _, d := range f.AST.Decls {
			switch d := d.(type) {
			case *ast.FuncDecl:
				if d.Body != nil {
					d.Body.List = z.block(d.Body.List)
				}
			case *ast.GenDecl:
				for _, s := range d.Specs {
					if vs, ok := s.(*ast.ValueSpec); ok {
						for i := range vs.Values {
							vs.Values[i] = z.expr(vs.Values[i], &state{unsafe: true}, nil)
						}
					}
				}
			}
		}
	}
}

func (z *Finalizer) pending(x ast.Expr) bool {
	c, ok := x.(*ast.CallExpr)
	if !ok {
		return false
	}
	if z.Matches[c] != nil {
		return true
	}
	_, ok = z.N.Temps[c]
	return ok
}

type state struct {
	unsafe bool // hoisting is not allowed here
	seen   bool // an impure evaluation precedes the current expression
}

// block finalizes a statement list.
func (z *Finalizer) block(list []ast.Stmt) []ast.Stmt {
	var out []ast.Stmt
	for _, s := range list {
		pre, s2 := z.stmt(s)
		if len(pre) > 0 {
			pre = z.block(pre)
		}
		out = append(out, pre...)
		if s2 != nil {
			out = append(out, s2)
		}
	}
	return out
}

// stmt finalizes statement s and returns the statements to insert before it
// and its replacement (nil to drop it).
func (z *Finalizer) stmt(s ast.Stmt) ([]ast.Stmt, ast.Stmt) {
	var pre []ast.Stmt
	if s.Pos().IsValid() {
		z.cur = s.Pos()
	}
	head := func(x ast.Expr, st *state) ast.Expr { return z.expr(x, st, &pre) }
	nested := func(x ast.Expr) ast.Expr { return z.expr(x, &state{unsafe: true}, nil) }
	switch s := s.(type) {
	case *ast.AssignStmt:
		// x := match ...  and  x = match ...
		if len(s.Lhs) == 1 && len(s.Rhs) == 1 && (s.Tok == token.DEFINE || s.Tok == token.ASSIGN) {
			if id, ok := s.Lhs[0].(*ast.Ident); ok && id.Name != "_" {
				if m := z.Matches[callOf(s.Rhs[0])]; m != nil {
					var stmts []ast.Stmt
					if s.Tok == token.DEFINE {
						d := astx.VarDecl(id.Name, astx.Clone(m.Result))
						d.Decl.(*ast.GenDecl).TokPos = s.Pos()
						z.N.Pkg.Mark(d, s.Pos())
						stmts = append(stmts, d)
					}
					sw := z.N.L.Switch(m, lower.AssignSink(id.Name))
					m.Done = true
					stmts = append(stmts, sw)
					return z.block(stmts), nil
				}
			}
		}
		st := &state{}
		for i := range s.Lhs {
			s.Lhs[i] = head(s.Lhs[i], st)
		}
		for i := range s.Rhs {
			s.Rhs[i] = head(s.Rhs[i], st)
		}
	case *ast.ExprStmt:
		s.X = head(s.X, &state{})
	case *ast.ReturnStmt:
		st := &state{}
		for i := range s.Results {
			s.Results[i] = head(s.Results[i], st)
		}
	case *ast.DeclStmt:
		if g, ok := s.Decl.(*ast.GenDecl); ok {
			st := &state{}
			for _, sp := range g.Specs {
				if vs, ok := sp.(*ast.ValueSpec); ok {
					for i := range vs.Values {
						vs.Values[i] = head(vs.Values[i], st)
					}
				}
			}
		}
	case *ast.IncDecStmt:
		s.X = head(s.X, &state{})
	case *ast.SendStmt:
		st := &state{}
		s.Chan = head(s.Chan, st)
		s.Value = head(s.Value, st)
	case *ast.GoStmt:
		s.Call = head(s.Call, &state{}).(*ast.CallExpr)
	case *ast.DeferStmt:
		s.Call = head(s.Call, &state{}).(*ast.CallExpr)
	case *ast.LabeledStmt:
		p, s2 := z.stmt(s.Stmt)
		if s2 == nil {
			s2 = &ast.EmptyStmt{Implicit: true}
		}
		s.Stmt = s2
		return p, s
	case *ast.BlockStmt:
		s.List = z.block(s.List)
	case *ast.IfStmt:
		var scoped []ast.Stmt
		if s.Init != nil {
			p, s2 := z.stmt(s.Init)
			scoped = p
			s.Init = s2
		}
		if s.Init == nil {
			s.Cond = head(s.Cond, &state{})
		} else {
			s.Cond = nested(s.Cond)
		}
		s.Body.List = z.block(s.Body.List)
		switch e := s.Else.(type) {
		case *ast.BlockStmt:
			e.List = z.block(e.List)
		case *ast.IfStmt:
			p, e2 := z.stmt(e)
			if len(p) > 0 {
				s.Else = &ast.BlockStmt{List: append(z.block(p), e2)}
			} else {
				s.Else = e2
			}
		}
		if len(scoped) > 0 {
			// keep the variables of the init statement local to the if
			return pre, &ast.BlockStmt{List: append(z.block(scoped), s)}
		}
	case *ast.SwitchStmt:
		var scoped []ast.Stmt
		if s.Init != nil {
			p, s2 := z.stmt(s.Init)
			scoped = p
			s.Init = s2
		}
		if s.Tag != nil {
			if s.Init == nil {
				s.Tag = head(s.Tag, &state{})
			} else {
				s.Tag = nested(s.Tag)
			}
		}
		z.clauses(s.Body)
		if len(scoped) > 0 {
			return pre, &ast.BlockStmt{List: append(z.block(scoped), s)}
		}
	case *ast.TypeSwitchStmt:
		var scoped []ast.Stmt
		if s.Init != nil {
			p, s2 := z.stmt(s.Init)
			scoped = p
			s.Init = s2
		}
		if s.Init == nil {
			p, s2 := z.stmt(s.Assign)
			pre = append(pre, p...)
			s.Assign = s2
		}
		z.clauses(s.Body)
		if len(scoped) > 0 {
			return pre, &ast.BlockStmt{List: append(z.block(scoped), s)}
		}
	case *ast.SelectStmt:
		z.clauses(s.Body)
	case *ast.ForStmt:
		if s.Init != nil {
			// loop variables are per iteration; nothing is moved out
			_, s.Init = z.stmtNested(s.Init)
		}
		if s.Cond != nil {
			s.Cond = nested(s.Cond)
		}
		if s.Post != nil {
			_, s.Post = z.stmtNested(s.Post)
		}
		s.Body.List = z.block(s.Body.List)
	case *ast.RangeStmt:
		s.X = head(s.X, &state{})
		s.Body.List = z.block(s.Body.List)
	}
	return pre, s
}

// stmtNested finalizes a statement in which nothing can be hoisted.
func (z *Finalizer) stmtNested(s ast.Stmt) ([]ast.Stmt, ast.Stmt) {
	n := func(x ast.Expr) ast.Expr { return z.expr(x, &state{unsafe: true}, nil) }
	switch s := s.(type) {
	case *ast.AssignStmt:
		for i := range s.Lhs {
			s.Lhs[i] = n(s.Lhs[i])
		}
		for i := range s.Rhs {
			s.Rhs[i] = n(s.Rhs[i])
		}
	case *ast.ExprStmt:
		s.X = n(s.X)
	case *ast.IncDecStmt:
		s.X = n(s.X)
	case *ast.SendStmt:
		s.Chan, s.Value = n(s.Chan), n(s.Value)
	}
	return nil, s
}

func (z *Finalizer) clauses(b *ast.BlockStmt) {
	for _, c := range b.List {
		switch c := c.(type) {
		case *ast.CaseClause:
			for i := range c.List {
				c.List[i] = z.expr(c.List[i], &state{unsafe: true}, nil)
			}
			c.Body = z.block(c.Body)
		case *ast.CommClause:
			if c.Comm != nil {
				_, c.Comm = z.stmtNested(c.Comm)
			}
			c.Body = z.block(c.Body)
		}
	}
}

func callOf(x ast.Expr) *ast.CallExpr {
	c, _ := ast.Unparen(x).(*ast.CallExpr)
	return c
}

// expr finalizes expression x evaluated in state st. Hoisted statements are
// appended to *pre; pre == nil forbids hoisting.
func (z *Finalizer) expr(x ast.Expr, st *state, pre *[]ast.Stmt) ast.Expr {
	if x == nil {
		return nil
	}
	if z.pending(x) {
		c := x.(*ast.CallExpr)
		if m := z.Matches[c]; m != nil {
			if pre != nil && !st.unsafe && !st.seen {
				name := z.N.L.Fresh("gnMatch")
				d := astx.VarDecl(name, astx.Clone(m.Result))
				d.Decl.(*ast.GenDecl).TokPos = z.cur
				z.N.Pkg.Mark(d, m.Pos)
				sw := z.N.L.Switch(m, lower.AssignSink(name))
				m.Done = true
				*pre = append(*pre, d, sw)
				return astx.Ident(name)
			}
			// keep the function literal; finalize its body
			m.Done = true
			m.Lit.Body.List = z.block(m.Lit.Body.List)
			st.seen = true
			return x
		}
		temps := z.N.Temps[c]
		delete(z.N.Temps, c)
		for _, t := range temps {
			t.Rhs[0] = z.expr(t.Rhs[0], &state{unsafe: true}, nil)
		}
		z.children(c, st, nil)
		if pre != nil && !st.unsafe && !st.seen {
			for _, t := range temps {
				t.Lhs[0].(*ast.Ident).NamePos = z.cur
				*pre = append(*pre, t)
			}
			st.seen = true
			return c
		}
		st.seen = true
		lit := &ast.FuncLit{Type: &ast.FuncType{Params: &ast.FieldList{}, Results: z.ResultType(z.file, c)}, Body: &ast.BlockStmt{}}
		for _, t := range temps {
			lit.Body.List = append(lit.Body.List, t)
		}
		if lit.Type.Results == nil || len(lit.Type.Results.List) == 0 {
			lit.Body.List = append(lit.Body.List, &ast.ExprStmt{X: c})
		} else {
			lit.Body.List = append(lit.Body.List, &ast.ReturnStmt{Results: []ast.Expr{c}})
		}
		return &ast.CallExpr{Fun: lit}
	}
	if fl, ok := x.(*ast.FuncLit); ok {
		saved := z.file
		fl.Body.List = z.block(fl.Body.List)
		z.file = saved
		return x
	}
	z.children(x, st, pre)
	switch x := x.(type) {
	case *ast.CallExpr:
		if !z.pureCall(x) {
			st.seen = true
		}
	case *ast.UnaryExpr:
		if x.Op == token.ARROW {
			st.seen = true
		}
	}
	return x
}

func (z *Finalizer) pureCall(c *ast.CallExpr) bool {
	if tv, ok := z.Info.Types[c.Fun]; ok && tv.IsType() {
		return true
	}
	if id, ok := c.Fun.(*ast.Ident); ok {
		if b, ok := z.Info.Uses[id].(*types.Builtin); ok {
			switch b.Name() {
			case "len", "cap", "min", "max", "real", "imag", "complex":
				return true
			}
		}
	}
	return false
}

// children finalizes the operands of x in evaluation order.
func (z *Finalizer) children(x ast.Expr, st *state, pre *[]ast.Stmt) {
	e := func(y ast.Expr) ast.Expr { return z.expr(y, st, pre) }
	switch x := x.(type) {
	case *ast.CallExpr:
		x.Fun = e(x.Fun)
		for i := range x.Args {
			x.Args[i] = e(x.Args[i])
		}
	case *ast.ParenExpr:
		x.X = e(x.X)
	case *ast.SelectorExpr:
		x.X = e(x.X)
	case *ast.IndexExpr:
		x.X = e(x.X)
		x.Index = e(x.Index)
	case *ast.IndexListExpr:
		x.X = e(x.X)
	case *ast.SliceExpr:
		x.X = e(x.X)
		x.Low, x.High, x.Max = e(x.Low), e(x.High), e(x.Max)
	case *ast.TypeAssertExpr:
		x.X = e(x.X)
	case *ast.StarExpr:
		x.X = e(x.X)
	case *ast.UnaryExpr:
		x.X = e(x.X)
	case *ast.BinaryExpr:
		x.X = e(x.X)
		if x.Op == token.LAND || x.Op == token.LOR {
			sub := &state{unsafe: true, seen: true}
			x.Y = z.expr(x.Y, sub, nil)
			if sub.seen {
				st.seen = true
			}
		} else {
			x.Y = e(x.Y)
		}
	case *ast.KeyValueExpr:
		x.Key = e(x.Key)
		x.Value = e(x.Value)
	case *ast.CompositeLit:
		for i := range x.Elts {
			x.Elts[i] = e(x.Elts[i])
		}
	}
}
