package lower

import (
	"fmt"
	"go/ast"
	"go/token"

	"github.com/ORGANIZATION/gonext/internal/astx"
	"github.com/ORGANIZATION/gonext/internal/iast"
	"github.com/ORGANIZATION/gonext/internal/syntax"
)

// Sink produces the statements that deliver the value of an expression arm:
// a return in the expression form, an assignment to the result variable in
// the statement form, or an expression statement.
type Sink func(body ast.Expr) []ast.Stmt

// IsPanic reports whether x is a call of the builtin panic.
func IsPanic(x ast.Expr) bool {
	c, ok := x.(*ast.CallExpr)
	if !ok {
		return false
	}
	id, ok := c.Fun.(*ast.Ident)
	return ok && id.Name == "panic"
}

// ReturnSink returns from the enclosing function literal.
func ReturnSink(body ast.Expr) []ast.Stmt {
	if IsPanic(body) {
		return []ast.Stmt{&ast.ExprStmt{X: body}}
	}
	return []ast.Stmt{&ast.ReturnStmt{Return: body.Pos(), Results: []ast.Expr{body}}}
}

// AssignSink assigns to the variable name.
func AssignSink(name string) Sink {
	return func(body ast.Expr) []ast.Stmt {
		if IsPanic(body) {
			return []ast.Stmt{&ast.ExprStmt{X: body}}
		}
		return []ast.Stmt{astx.Assign(&ast.Ident{NamePos: body.Pos(), Name: name}, body)}
	}
}

// StmtSink evaluates the arm for its effects.
func StmtSink(body ast.Expr) []ast.Stmt {
	if _, ok := ast.Unparen(body).(*ast.CallExpr); ok {
		return []ast.Stmt{&ast.ExprStmt{X: body}}
	}
	if u, ok := ast.Unparen(body).(*ast.UnaryExpr); ok && u.Op == token.ARROW {
		return []ast.Stmt{&ast.ExprStmt{X: body}}
	}
	return []ast.Stmt{astx.Assign(astx.Ident("_"), body)}
}

// Matches lowers every match of the package: statement matches become
// switch statements, expression matches become an immediately invoked
// function literal whose result type is inferred in the type-checking
// rounds and which is turned into statements during normalization.
func (l *Lowerer) Matches() {
	p := l.Pkg
	stmts := map[*ast.CallExpr]ast.Stmt{}
	for _, m := range p.Matches {
		if m.Stmt {
			for _, a := range m.Arms {
				if a.Block != nil {
					l.checkBranches(m, a.Block)
				}
			}
			sw := l.Switch(m, StmtSink)
			if sw != nil {
				stmts[m.Call] = sw
				m.Done = true
			}
			continue
		}
		for _, a := range m.Arms {
			if a.Block != nil {
				p.Errorf(m.File, a.Block.Pos(), "a block arm is only allowed in a match statement; use an expression or a function call")
			}
		}
		sw := l.Switch(m, ReturnSink)
		if sw == nil {
			continue
		}
		m.Result = astx.Ident(syntax.InferType)
		m.Lit = &ast.FuncLit{
			Type: &ast.FuncType{Func: m.Pos, Params: &ast.FieldList{}, Results: &ast.FieldList{List: []*ast.Field{{Type: m.Result}}}},
			Body: &ast.BlockStmt{Lbrace: m.Pos, List: []ast.Stmt{sw}, Rbrace: m.End - 1},
		}
		m.Call.Fun = m.Lit
		m.Call.Args = nil
		m.Expr = m.Call
	}
	for _, f := range p.Files {
		astx.Rewrite(f.AST, func(n ast.Node) ast.Node {
			if es, ok := n.(*ast.ExprStmt); ok {
				if c, ok := es.X.(*ast.CallExpr); ok {
					if sw := stmts[c]; sw != nil {
						return sw
					}
				}
			}
			return n
		})
	}
}

func (l *Lowerer) errorf(m *iast.Match, pos token.Position, format string, args ...any) {
	if !pos.IsValid() {
		pos = m.Decl.Pos
	}
	l.Pkg.Errs = append(l.Pkg.Errs, &syntax.Error{Pos: pos, Msg: sprintf(format, args...)})
}

// Switch compiles the arms of m into a switch statement (a decision tree)
// whose expression arms deliver their value through sink. It reports
// non-exhaustive matches and unreachable arms.
func (l *Lowerer) Switch(m *iast.Match, sink Sink) ast.Stmt {
	if m.Enum == nil {
		return l.constSwitch(m, sink)
	}
	return l.enumSwitch(m, sink)
}

// bodyOf returns the statements of arm a. Arms that end up in more than one
// case clause are copied; nested IAST nodes of the copy are registered.
func (l *Lowerer) bodyOf(a *iast.Arm, sink Sink, used map[*iast.Arm]int) []ast.Stmt {
	used[a]++
	if used[a] == 1 {
		if a.Block != nil {
			return a.Block.List
		}
		return sink(a.Body)
	}
	if a.Block != nil {
		return cloneTracked(l, a.Block).List
	}
	return sink(cloneTracked(l, a.Body))
}

// cloneTracked copies n and registers the copies of nested matches and
// short functions in the IAST.
func cloneTracked[N ast.Node](l *Lowerer, n N) N {
	c, m := astx.CloneMap(n)
	p := l.Pkg
	get := func(x ast.Node) ast.Node {
		if y, ok := m[x]; ok {
			return y
		}
		return x
	}
	for old, nw := range m {
		if fl, ok := old.(*ast.FuncLit); ok {
			if lam := p.Lambdas[fl]; lam != nil {
				p.Lambdas[nw.(*ast.FuncLit)] = &iast.Lambda{Lit: nw.(*ast.FuncLit), File: lam.File}
			}
		}
		if pos, ok := p.Origin[old]; ok {
			p.Origin[nw] = pos
		}
	}
	for _, mt := range append([]*iast.Match(nil), p.Matches...) {
		if mt.Expr == nil || m[mt.Expr] == nil || mt.Done {
			continue
		}
		cm := *mt
		cm.Call = get(mt.Call).(*ast.CallExpr)
		cm.Expr = cm.Call
		cm.Lit = get(mt.Lit).(*ast.FuncLit)
		cm.Result = cm.Lit.Type.Results.List[0].Type
		cm.Scrut = get(mt.Scrut).(ast.Expr)
		cm.Arms = nil
		for _, a := range mt.Arms {
			ca := *a
			if a.Guard != nil {
				ca.Guard = get(a.Guard).(ast.Expr)
			}
			if a.Body != nil {
				ca.Body = get(a.Body).(ast.Expr)
			}
			cm.Arms = append(cm.Arms, &ca)
		}
		p.Matches = append(p.Matches, &cm)
	}
	return c
}

func sprintf(format string, args ...any) string { return fmtSprintf(format, args...) }

func (l *Lowerer) constSwitch(m *iast.Match, sink Sink) ast.Stmt {
	sw := &ast.SwitchStmt{Body: &ast.BlockStmt{}}
	sv := m.Scrut
	if _, ok := m.Scrut.(*ast.Ident); !ok {
		name := l.Fresh("gnS")
		sw.Init = astx.Define([]string{name}, m.Scrut)
		sv = astx.Ident(name)
	}
	used := map[*iast.Arm]int{}
	exhaustive := false
	for _, a := range m.Arms {
		if exhaustive {
			l.errorf(m, a.Decl.Pos, "unreachable match arm")
			continue
		}
		var cond ast.Expr
		wild := false
		for _, pat := range a.Pats {
			if pat.Kind == iast.PatWild {
				wild = true
				continue
			}
			if pat.Kind != iast.PatConst {
				continue
			}
			c := &ast.BinaryExpr{X: astx.Clone(sv), Op: token.EQL, Y: pat.Const}
			if cond == nil {
				cond = c
			} else {
				cond = &ast.BinaryExpr{X: cond, Op: token.LOR, Y: c}
			}
		}
		if wild {
			cond = nil
		}
		if a.Guard != nil {
			if cond == nil {
				cond = a.Guard
			} else {
				cond = &ast.BinaryExpr{X: astx.Paren(cond), Op: token.LAND, Y: astx.Paren(a.Guard)}
			}
		}
		cc := &ast.CaseClause{Case: armPos(a), Colon: armPos(a), Body: l.bodyOf(a, sink, used)}
		l.Pkg.Origin[cc] = a.Decl.Pos
		if cond == nil {
			exhaustive = true
		} else {
			cc.List = []ast.Expr{cond}
		}
		sw.Body.List = append(sw.Body.List, cc)
	}
	if !exhaustive {
		l.errorf(m, m.Decl.Pos, "non-exhaustive match: a match over values that are not enum variants needs an unguarded wildcard arm _")
		return nil
	}
	l.Pkg.Origin[sw] = m.Decl.Pos
	return sw
}

// armPos returns a position on the line of arm a.
func armPos(a *iast.Arm) token.Pos {
	switch {
	case a.Guard != nil:
		return a.Guard.Pos()
	case a.Body != nil:
		return a.Body.Pos()
	case a.Block != nil:
		return a.Block.Lbrace
	}
	return token.NoPos
}

// place gives a synthetic switch the positions of the match it replaces so
// that go/printer keeps comments and line breaks around it.
func place(m *iast.Match, sw ast.Stmt, clauses []ast.Stmt) {
	end := m.End - 1
	last := armPos(m.Arms[len(m.Arms)-1])
	switch sw := sw.(type) {
	case *ast.SwitchStmt:
		sw.Switch, sw.Body.Lbrace, sw.Body.Rbrace = m.Pos, m.Pos, end
	case *ast.TypeSwitchStmt:
		sw.Switch, sw.Body.Lbrace, sw.Body.Rbrace = m.Pos, m.Pos, end
	}
	for _, c := range clauses {
		if cc, ok := c.(*ast.CaseClause); ok && !cc.Case.IsValid() {
			cc.Case, cc.Colon = last, last
		}
	}
}

// patternFor returns the pattern of arm a that matches variant v, or nil.
func patternFor(a *iast.Arm, v *iast.Variant) *iast.Pattern {
	for _, p := range a.Pats {
		if p.Kind == iast.PatWild || (p.Kind == iast.PatVariant && p.Variant == v) {
			return p
		}
	}
	return nil
}

func (l *Lowerer) usedBinders(a *iast.Arm, p *iast.Pattern) []int {
	var out []int
	if p == nil || p.Kind != iast.PatVariant {
		return nil
	}
	for i, b := range p.Binders {
		if b == "_" {
			continue
		}
		var nodes []ast.Node
		if a.Guard != nil {
			nodes = append(nodes, a.Guard)
		}
		if a.Body != nil {
			nodes = append(nodes, a.Body)
		}
		if a.Block != nil {
			nodes = append(nodes, a.Block)
		}
		if astx.Uses(b, nodes...) {
			out = append(out, i)
		}
	}
	return out
}

func (l *Lowerer) enumSwitch(m *iast.Match, sink Sink) ast.Stmt {
	e := m.Enum
	f := m.File
	if e.Repr == iast.ReprInterface && e.Generic() {
		l.errorf(m, m.Decl.Pos, "internal error: generic enum in interface representation")
		return nil
	}
	// chains of candidate arms per variant
	chains := make([][]*iast.Arm, len(e.Variants))
	reach := map[*iast.Arm]bool{}
	ok := true
	for i, v := range e.Variants {
		for _, a := range m.Arms {
			if patternFor(a, v) == nil {
				continue
			}
			chains[i] = append(chains[i], a)
			reach[a] = true
			if a.Guard == nil {
				break
			}
		}
		c := chains[i]
		if len(c) == 0 || c[len(c)-1].Guard != nil {
			why := ""
			if len(c) > 0 {
				why = " (every arm for it has a guard)"
			}
			l.errorf(m, m.Decl.Pos, "non-exhaustive match on %s: variant %s not covered%s", e.Name, v.Name, why)
			ok = false
		}
	}
	for _, a := range m.Arms {
		if !reach[a] {
			l.errorf(m, a.Decl.Pos, "unreachable match arm")
			ok = false
		}
	}
	if !ok {
		return nil
	}
	needBind := false
	for i, v := range e.Variants {
		for _, a := range chains[i] {
			if len(l.usedBinders(a, patternFor(a, v))) > 0 {
				needBind = true
			}
		}
	}
	// scrutinee variable
	var sv string
	var init ast.Stmt
	var tag ast.Expr
	var typeSwitch *ast.TypeSwitchStmt
	if e.Repr == iast.ReprInterface {
		var assign ast.Stmt
		x := &ast.TypeAssertExpr{X: m.Scrut}
		if needBind {
			sv = l.Fresh("gnV")
			assign = astx.Define([]string{sv}, x)
		} else {
			assign = &ast.ExprStmt{X: x}
		}
		typeSwitch = &ast.TypeSwitchStmt{Assign: assign, Body: &ast.BlockStmt{}}
	} else {
		if id, ok := m.Scrut.(*ast.Ident); ok {
			sv = id.Name
		} else {
			sv = l.Fresh("gnS")
			init = astx.Define([]string{sv}, m.Scrut)
		}
		tag = astx.Sel(astx.Ident(sv), "tag")
	}
	used := map[*iast.Arm]int{}
	isWildChain := func(c []*iast.Arm) bool {
		for _, a := range c {
			for _, p := range a.Pats {
				if p.Kind == iast.PatVariant {
					return false
				}
			}
		}
		return true
	}
	var clauses []ast.Stmt
	var deflt []*iast.Arm
	done := make([]bool, len(e.Variants))
	for i, v := range e.Variants {
		if done[i] {
			continue
		}
		c := chains[i]
		if isWildChain(c) {
			deflt = c
			done[i] = true
			continue
		}
		group := []*iast.Variant{v}
		done[i] = true
		bind := false
		for _, a := range c {
			if len(l.usedBinders(a, patternFor(a, v))) > 0 {
				bind = true
			}
		}
		if !bind {
			for j := i + 1; j < len(e.Variants); j++ {
				if !done[j] && sameChain(c, chains[j]) && !isWildChain(chains[j]) {
					group = append(group, e.Variants[j])
					done[j] = true
				}
			}
		}
		cc := &ast.CaseClause{Case: armPos(c[0]), Colon: armPos(c[0]), Body: l.chain(f, m, c, v, sv, sink, used)}
		for _, gv := range group {
			if typeSwitch != nil {
				cc.List = append(cc.List, astx.Ident(TagName(gv)))
			} else {
				cc.List = append(cc.List, astx.Ident(TagName(gv)))
			}
		}
		l.Pkg.Origin[cc] = c[0].Decl.Pos
		clauses = append(clauses, cc)
	}
	dc := &ast.CaseClause{}
	if deflt != nil {
		dc.Body = l.chain(f, m, deflt, nil, sv, sink, used)
		l.Pkg.Origin[dc] = deflt[0].Decl.Pos
	} else {
		dc.Body = []ast.Stmt{&ast.ExprStmt{X: astx.Call(astx.Ident("panic"), astx.Str("gonext: non-exhaustive match on "+e.Name))}}
		l.Pkg.Origin[dc] = m.Decl.Pos
	}
	clauses = append(clauses, dc)
	if typeSwitch != nil {
		typeSwitch.Body.List = clauses
		l.Pkg.Origin[typeSwitch] = m.Decl.Pos
		place(m, typeSwitch, clauses)
		return typeSwitch
	}
	sw := &ast.SwitchStmt{Init: init, Tag: tag, Body: &ast.BlockStmt{List: clauses}}
	l.Pkg.Origin[sw] = m.Decl.Pos
	place(m, sw, clauses)
	return sw
}

func sameChain(a, b []*iast.Arm) bool {
	if len(a) != len(b) {
		return false
	}
	for i := range a {
		if a[i] != b[i] {
			return false
		}
	}
	return true
}

// chain builds the if-else chain that tries the arms of one variant in
// source order; the last arm has no guard.
func (l *Lowerer) chain(f *iast.File, m *iast.Match, arms []*iast.Arm, v *iast.Variant, sv string, sink Sink, used map[*iast.Arm]int) []ast.Stmt {
	var tail []ast.Stmt
	for i := len(arms) - 1; i >= 0; i-- {
		a := arms[i]
		var bind *ast.AssignStmt
		if v != nil {
			p := patternFor(a, v)
			for _, idx := range l.usedBinders(a, p) {
				if bind == nil {
					bind = &ast.AssignStmt{Tok: token.DEFINE, TokPos: armPos(a)}
				}
				bind.Lhs = append(bind.Lhs, &ast.Ident{NamePos: armPos(a), Name: p.Binders[idx]})
				bind.Rhs = append(bind.Rhs, l.Load(f, v, v.Fields[idx], sv))
			}
		}
		body := l.bodyOf(a, sink, used)
		if a.Guard == nil {
			tail = body
			if bind != nil {
				l.Pkg.Origin[bind] = a.Decl.Pos
				tail = append([]ast.Stmt{bind}, body...)
			}
			continue
		}
		guard := a.Guard
		if used[a] > 1 {
			guard = cloneTracked(l, guard)
		}
		is := &ast.IfStmt{If: armPos(a), Cond: guard, Body: &ast.BlockStmt{Lbrace: armPos(a), List: body}}
		if bind != nil {
			is.Init = bind
		}
		next := armPos(arms[i+1])
		if len(tail) == 1 {
			if t, ok := tail[0].(*ast.IfStmt); ok {
				is.Else = t
			} else {
				is.Else = &ast.BlockStmt{Lbrace: next, List: tail}
			}
		} else {
			is.Else = &ast.BlockStmt{Lbrace: next, List: tail}
		}
		l.Pkg.Origin[is] = a.Decl.Pos
		tail = []ast.Stmt{is}
	}
	return tail
}

var fmtSprintf = fmt.Sprintf

// checkBranches rejects unlabeled break and fallthrough statements that
// would refer to the generated switch instead of the enclosing statement.
func (l *Lowerer) checkBranches(m *iast.Match, b *ast.BlockStmt) {
	var visit func(n ast.Node) bool
	visit = func(n ast.Node) bool {
		switch n := n.(type) {
		case *ast.FuncLit, *ast.ForStmt, *ast.RangeStmt, *ast.SwitchStmt, *ast.TypeSwitchStmt, *ast.SelectStmt:
			return false
		case *ast.BranchStmt:
			switch {
			case n.Tok == token.BREAK && n.Label == nil:
				l.Pkg.Errorf(m.File, n.Pos(), "unlabeled break in a match arm; use a labeled break to leave the enclosing loop")
			case n.Tok == token.FALLTHROUGH:
				l.Pkg.Errorf(m.File, n.Pos(), "fallthrough is not allowed in a match arm")
			}
		}
		return true
	}
	for _, st := range b.List {
		ast.Inspect(st, visit)
	}
}
