// Package astx provides small utilities for manipulating go/ast trees that
// the transpiler stages share: generic in-place rewriting, deep copies,
// position clearing and construction helpers.
package astx

import (
	"go/ast"
	"go/printer"
	"go/token"
	"reflect"
	"strconv"
	"strings"
)

var (
	exprType  = reflect.TypeOf((*ast.Expr)(nil)).Elem()
	stmtType  = reflect.TypeOf((*ast.Stmt)(nil)).Elem()
	declType  = reflect.TypeOf((*ast.Decl)(nil)).Elem()
	specType  = reflect.TypeOf((*ast.Spec)(nil)).Elem()
	nodeType  = reflect.TypeOf((*ast.Node)(nil)).Elem()
	posType   = reflect.TypeOf(token.NoPos)
	objPtrTyp = reflect.TypeOf((*ast.Object)(nil))
	scopePtr  = reflect.TypeOf((*ast.Scope)(nil))
)

// Rewrite walks the tree rooted at root in post-order and replaces every
// expression or statement e stored in a field or slice by f(e). The function
// f returns its argument unchanged when no replacement is wanted. Rewrite
// does not descend into the node returned by f.
func Rewrite(root ast.Node, f func(ast.Node) ast.Node) {
	rewriteValue(reflect.ValueOf(root), f)
}

func rewriteValue(v reflect.Value, f func(ast.Node) ast.Node) {
	switch v.Kind() {
	case reflect.Ptr:
		if v.IsNil() || v.Type() == objPtrTyp || v.Type() == scopePtr {
			return
		}
		rewriteValue(v.Elem(), f)
	case reflect.Interface:
		if v.IsNil() {
			return
		}
		rewriteValue(v.Elem(), f)
	case reflect.Struct:
		for i := 0; i < v.NumField(); i++ {
			fv := v.Field(i)
			if !fv.CanSet() {
				continue
			}
			rewriteSlot(fv, f)
		}
	case reflect.Slice:
		for i := 0; i < v.Len(); i++ {
			rewriteSlot(v.Index(i), f)
		}
	}
}

func rewriteSlot(fv reflect.Value, f func(ast.Node) ast.Node) {
	t := fv.Type()
	switch {
	case t == exprType || t == stmtType || t == declType || t == specType || t == nodeType:
		if fv.IsNil() {
			return
		}
		rewriteValue(fv, f)
		n := fv.Interface().(ast.Node)
		if r := f(n); r != n {
			if r == nil {
				fv.Set(reflect.Zero(t))
			} else {
				fv.Set(reflect.ValueOf(r))
			}
		}
	case t.Kind() == reflect.Ptr && t.Implements(nodeType):
		if fv.IsNil() {
			return
		}
		rewriteValue(fv, f)
		n := fv.Interface().(ast.Node)
		if r := f(n); r != n && r != nil && reflect.TypeOf(r) == t {
			fv.Set(reflect.ValueOf(r))
		}
	case t.Kind() == reflect.Slice || t.Kind() == reflect.Struct:
		rewriteValue(fv, f)
	}
}

// Clone returns a deep copy of n. Comments, objects and scopes are not
// copied; positions are preserved.
func Clone[N ast.Node](n N) N {
	v := cloneValue(reflect.ValueOf(n))
	return v.Interface().(N)
}

func cloneValue(v reflect.Value) reflect.Value {
	switch v.Kind() {
	case reflect.Ptr:
		if v.IsNil() || v.Type() == objPtrTyp || v.Type() == scopePtr {
			return reflect.Zero(v.Type())
		}
		if v.Type() == reflect.TypeOf((*ast.CommentGroup)(nil)) {
			return reflect.Zero(v.Type())
		}
		c := reflect.New(v.Type().Elem())
		c.Elem().Set(cloneValue(v.Elem()))
		return c
	case reflect.Interface:
		if v.IsNil() {
			return reflect.Zero(v.Type())
		}
		c := cloneValue(v.Elem())
		r := reflect.New(v.Type()).Elem()
		r.Set(c)
		return r
	case reflect.Struct:
		c := reflect.New(v.Type()).Elem()
		for i := 0; i < v.NumField(); i++ {
			if c.Field(i).CanSet() {
				c.Field(i).Set(cloneValue(v.Field(i)))
			}
		}
		return c
	case reflect.Slice:
		if v.IsNil() {
			return reflect.Zero(v.Type())
		}
		c := reflect.MakeSlice(v.Type(), v.Len(), v.Len())
		for i := 0; i < v.Len(); i++ {
			c.Index(i).Set(cloneValue(v.Index(i)))
		}
		return c
	}
	return v
}

// ClearPos sets every position in the tree rooted at n to token.NoPos.
func ClearPos(n ast.Node) {
	clearValue(reflect.ValueOf(n))
}

func clearValue(v reflect.Value) {
	switch v.Kind() {
	case reflect.Ptr:
		if v.IsNil() || v.Type() == objPtrTyp || v.Type() == scopePtr {
			return
		}
		clearValue(v.Elem())
	case reflect.Interface:
		if !v.IsNil() {
			clearValue(v.Elem())
		}
	case reflect.Struct:
		for i := 0; i < v.NumField(); i++ {
			fv := v.Field(i)
			if !fv.CanSet() {
				continue
			}
			if fv.Type() == posType {
				fv.SetInt(0)
				continue
			}
			clearValue(fv)
		}
	case reflect.Slice:
		for i := 0; i < v.Len(); i++ {
			clearValue(v.Index(i))
		}
	}
}

// Ident returns a new identifier without position.
func Ident(name string) *ast.Ident { return &ast.Ident{Name: name} }

// Sel returns the selector expression x.name.
func Sel(x ast.Expr, name string) *ast.SelectorExpr {
	return &ast.SelectorExpr{X: x, Sel: Ident(name)}
}

// Call returns the call fun(args...).
func Call(fun ast.Expr, args ...ast.Expr) *ast.CallExpr {
	return &ast.CallExpr{Fun: fun, Args: args}
}

// Str returns a string literal.
func Str(s string) *ast.BasicLit {
	return &ast.BasicLit{Kind: token.STRING, Value: strconv.Quote(s)}
}

// Int returns an integer literal.
func Int(i int) *ast.BasicLit {
	return &ast.BasicLit{Kind: token.INT, Value: strconv.Itoa(i)}
}

// Define returns the statement lhs := rhs.
func Define(lhs []string, rhs ...ast.Expr) *ast.AssignStmt {
	var l []ast.Expr
	for _, n := range lhs {
		l = append(l, Ident(n))
	}
	return &ast.AssignStmt{Lhs: l, Tok: token.DEFINE, Rhs: rhs}
}

// Assign returns the statement lhs = rhs.
func Assign(lhs ast.Expr, rhs ast.Expr) *ast.AssignStmt {
	return &ast.AssignStmt{Lhs: []ast.Expr{lhs}, Tok: token.ASSIGN, Rhs: []ast.Expr{rhs}}
}

// VarDecl returns the statement var name T.
func VarDecl(name string, typ ast.Expr) *ast.DeclStmt {
	return &ast.DeclStmt{Decl: &ast.GenDecl{Tok: token.VAR, Specs: []ast.Spec{
		&ast.ValueSpec{Names: []*ast.Ident{Ident(name)}, Type: typ},
	}}}
}

// Paren wraps x in parentheses unless it is an operand that never needs them.
func Paren(x ast.Expr) ast.Expr {
	switch x.(type) {
	case *ast.Ident, *ast.BasicLit, *ast.CallExpr, *ast.SelectorExpr, *ast.IndexExpr,
		*ast.IndexListExpr, *ast.ParenExpr, *ast.CompositeLit, *ast.SliceExpr:
		return x
	}
	return &ast.ParenExpr{X: x}
}

// IsPure reports whether evaluating x can have no side effects and cannot
// panic in a way that depends on evaluation order: identifiers, literals,
// selectors of pure expressions and operators over pure operands.
func IsPure(x ast.Expr) bool {
	switch x := x.(type) {
	case *ast.Ident, *ast.BasicLit:
		return true
	case *ast.FuncLit:
		return true
	case *ast.ParenExpr:
		return IsPure(x.X)
	case *ast.SelectorExpr:
		return IsPure(x.X)
	case *ast.UnaryExpr:
		return x.Op != token.ARROW && IsPure(x.X)
	case *ast.BinaryExpr:
		return x.Op != token.QUO && x.Op != token.REM && IsPure(x.X) && IsPure(x.Y)
	case *ast.CompositeLit:
		for _, e := range x.Elts {
			if kv, ok := e.(*ast.KeyValueExpr); ok {
				e = kv.Value
			}
			if !IsPure(e) {
				return false
			}
		}
		return true
	case *ast.KeyValueExpr:
		return IsPure(x.Value)
	}
	return false
}

// Uses reports whether the identifier name occurs anywhere in the trees.
func Uses(name string, nodes ...ast.Node) bool {
	found := false
	for _, n := range nodes {
		if n == nil || reflect.ValueOf(n).IsNil() {
			continue
		}
		ast.Inspect(n, func(m ast.Node) bool {
			if id, ok := m.(*ast.Ident); ok && id.Name == name {
				found = true
			}
			return !found
		})
	}
	return found
}

// AddImport makes sure file imports path and returns the local name under
// which the package is accessible. name is the package's declared name.
func AddImport(file *ast.File, path, name string) string {
	taken := map[string]bool{}
	for _, is := range file.Imports {
		p, _ := strconv.Unquote(is.Path.Value)
		local := name
		if is.Name != nil {
			local = is.Name.Name
		} else if p != path {
			local = lastElem(p)
		}
		if p == path && (is.Name == nil || (is.Name.Name != "_" && is.Name.Name != ".")) {
			return local
		}
		taken[local] = true
	}
	local := name
	for i := 2; taken[local]; i++ {
		local = name + strconv.Itoa(i)
	}
	spec := &ast.ImportSpec{Path: Str(path)}
	if local != lastElem(path) {
		spec.Name = Ident(local)
	}
	file.Imports = append(file.Imports, spec)
	for _, d := range file.Decls {
		if g, ok := d.(*ast.GenDecl); ok && g.Tok == token.IMPORT {
			if !g.Lparen.IsValid() {
				g.Lparen = g.TokPos
				g.Rparen = g.TokPos
			}
			g.Specs = append(g.Specs, spec)
			return local
		}
	}
	g := &ast.GenDecl{Tok: token.IMPORT, Specs: []ast.Spec{spec}}
	file.Decls = append([]ast.Decl{g}, file.Decls...)
	return local
}

func lastElem(p string) string {
	for i := len(p) - 1; i >= 0; i-- {
		if p[i] == '/' {
			return p[i+1:]
		}
	}
	return p
}

// CloneMap returns a deep copy of n and a table from every original node in
// the tree to its copy.
func CloneMap[N ast.Node](n N) (N, map[ast.Node]ast.Node) {
	m := map[ast.Node]ast.Node{}
	v := cloneValueMap(reflect.ValueOf(n), m)
	return v.Interface().(N), m
}

func cloneValueMap(v reflect.Value, m map[ast.Node]ast.Node) reflect.Value {
	switch v.Kind() {
	case reflect.Ptr:
		if v.IsNil() || v.Type() == objPtrTyp || v.Type() == scopePtr {
			return reflect.Zero(v.Type())
		}
		if v.Type() == reflect.TypeOf((*ast.CommentGroup)(nil)) {
			return reflect.Zero(v.Type())
		}
		c := reflect.New(v.Type().Elem())
		c.Elem().Set(cloneValueMap(v.Elem(), m))
		if on, ok := v.Interface().(ast.Node); ok {
			m[on] = c.Interface().(ast.Node)
		}
		return c
	case reflect.Interface:
		if v.IsNil() {
			return reflect.Zero(v.Type())
		}
		c := cloneValueMap(v.Elem(), m)
		r := reflect.New(v.Type()).Elem()
		r.Set(c)
		return r
	case reflect.Struct:
		c := reflect.New(v.Type()).Elem()
		for i := 0; i < v.NumField(); i++ {
			if c.Field(i).CanSet() {
				c.Field(i).Set(cloneValueMap(v.Field(i), m))
			}
		}
		return c
	case reflect.Slice:
		if v.IsNil() {
			return reflect.Zero(v.Type())
		}
		c := reflect.MakeSlice(v.Type(), v.Len(), v.Len())
		for i := 0; i < v.Len(); i++ {
			c.Index(i).Set(cloneValueMap(v.Index(i), m))
		}
		return c
	}
	return v
}

// String formats an expression or type as Go source.
func String(n ast.Node) string {
	var b strings.Builder
	if err := printer.Fprint(&b, token.NewFileSet(), n); err != nil {
		return "<invalid>"
	}
	return b.String()
}
