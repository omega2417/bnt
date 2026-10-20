package lower

import (
	"go/ast"

	"github.com/ORGANIZATION/gonext/internal/astx"
	"github.com/ORGANIZATION/gonext/internal/iast"
)

// LiftMethods lifts extension methods and generic methods to top-level
// functions whose first parameter is the receiver.
func (l *Lowerer) LiftMethods() {
	p := l.Pkg
	for _, e := range p.Exts {
		fd := e.Decl
		recv := fd.Recv.List[0]
		fd.Name = &ast.Ident{NamePos: fd.Name.NamePos, Name: ExtName(recv.Type, e.Name)}
		l.liftRecv(fd)
	}
	for _, m := range p.Methods {
		fd := m.Decl
		recv := fd.Recv.List[0]
		var tps []*ast.Field
		rt := recv.Type
		if st, ok := rt.(*ast.StarExpr); ok {
			rt = st.X
		}
		var idx []ast.Expr
		switch x := rt.(type) {
		case *ast.IndexExpr:
			idx = []ast.Expr{x.Index}
		case *ast.IndexListExpr:
			idx = x.Indices
		}
		decl := l.typeParamsOf(m.TypeName)
		for i, ix := range idx {
			id, ok := ix.(*ast.Ident)
			if !ok {
				p.Errorf(m.File, ix.Pos(), "receiver type parameter must be an identifier")
				continue
			}
			var constraint ast.Expr = astx.Ident("any")
			if decl != nil && i < len(decl) {
				constraint = astx.Clone(decl[i])
				astx.ClearPos(constraint)
			}
			tps = append(tps, &ast.Field{Names: []*ast.Ident{astx.Ident(id.Name)}, Type: constraint})
		}
		if fd.Type.TypeParams != nil {
			tps = append(tps, fd.Type.TypeParams.List...)
		}
		fd.Type.TypeParams = &ast.FieldList{List: tps}
		fd.Name = &ast.Ident{NamePos: fd.Name.NamePos, Name: MethodName(m.TypeName, fd.Name.Name)}
		l.liftRecv(fd)
	}
}

func (l *Lowerer) liftRecv(fd *ast.FuncDecl) {
	recv := fd.Recv.List[0]
	if len(recv.Names) == 0 || recv.Names[0].Name == "_" {
		recv.Names = []*ast.Ident{astx.Ident(l.Fresh("gnRecv"))}
	}
	fd.Type.Params.List = append([]*ast.Field{recv}, fd.Type.Params.List...)
	fd.Recv = nil
	if fi := l.Pkg.Funcs[fd]; fi != nil {
		fi.Lifted = true
	}
}

// typeParamsOf returns the constraints of the type parameters of the named
// type declared in the package, one entry per type parameter.
func (l *Lowerer) typeParamsOf(name string) []ast.Expr {
	var files []*ast.File
	for _, f := range l.Pkg.Files {
		files = append(files, f.AST)
	}
	files = append(files, l.Pkg.GoFiles...)
	for _, f := range files {
		for _, d := range f.Decls {
			g, ok := d.(*ast.GenDecl)
			if !ok {
				continue
			}
			for _, s := range g.Specs {
				ts, ok := s.(*ast.TypeSpec)
				if !ok || ts.Name.Name != name || ts.TypeParams == nil {
					continue
				}
				var out []ast.Expr
				for _, f := range ts.TypeParams.List {
					for range f.Names {
						out = append(out, f.Type)
					}
				}
				return out
			}
		}
	}
	return nil
}

// RewriteConstructors replaces variant constructions Enum.Variant(args),
// Enum[T].Variant(args), Enum.Unit and Variant(args) by calls of the
// generated constructor functions. Calls are rewritten in place; other
// replaced nodes are reported through fix so that IAST references can be
// updated.
func (l *Lowerer) RewriteConstructors(fix map[ast.Node]ast.Node) {
	p := l.Pkg
	decl := map[string]bool{}
	for _, f := range p.Files {
		for _, d := range f.AST.Decls {
			switch d := d.(type) {
			case *ast.FuncDecl:
				if d.Recv == nil {
					decl[d.Name.Name] = true
				}
			case *ast.GenDecl:
				for _, s := range d.Specs {
					switch s := s.(type) {
					case *ast.TypeSpec:
						decl[s.Name.Name] = true
					case *ast.ValueSpec:
						for _, n := range s.Names {
							decl[n.Name] = true
						}
					}
				}
			}
		}
	}
	bare := map[string]*iast.Variant{}
	count := map[string]int{}
	for _, e := range p.Enums {
		for _, v := range e.Variants {
			bare[v.Name] = v
			count[v.Name]++
		}
	}
	// variantOf resolves Enum.V, Enum[T].V and V.
	variantOf := func(x ast.Expr, called bool) (*iast.Variant, []ast.Expr) {
		switch x := x.(type) {
		case *ast.SelectorExpr:
			var targs []ast.Expr
			base := x.X
			switch b := base.(type) {
			case *ast.IndexExpr:
				base, targs = b.X, []ast.Expr{b.Index}
			case *ast.IndexListExpr:
				base, targs = b.X, b.Indices
			}
			id, ok := base.(*ast.Ident)
			if !ok {
				return nil, nil
			}
			e := p.EnumByName[id.Name]
			if e == nil {
				return nil, nil
			}
			return e.Variant(x.Sel.Name), targs
		case *ast.Ident:
			if called && count[x.Name] == 1 && !decl[x.Name] {
				return bare[x.Name], nil
			}
		}
		return nil, nil
	}
	ctor := func(v *iast.Variant, targs []ast.Expr) ast.Expr {
		var fn ast.Expr = astx.Ident(CtorName(v))
		switch len(targs) {
		case 0:
		case 1:
			fn = &ast.IndexExpr{X: fn, Index: targs[0]}
		default:
			fn = &ast.IndexListExpr{X: fn, Indices: targs}
		}
		return fn
	}
	for _, f := range p.Files {
		called := map[ast.Expr]bool{}
		ast.Inspect(f.AST, func(n ast.Node) bool {
			if c, ok := n.(*ast.CallExpr); ok {
				called[c.Fun] = true
				if v, targs := variantOf(c.Fun, true); v != nil {
					if len(v.Fields) != len(c.Args) && !(len(c.Args) == 1 && c.Ellipsis.IsValid()) {
						p.Errorf(f, c.Pos(), "variant %s.%s takes %d values, got %d", v.Enum.Name, v.Name, len(v.Fields), len(c.Args))
					}
					c.Fun = ctor(v, targs)
				}
			}
			return true
		})
		astx.Rewrite(f.AST, func(n ast.Node) ast.Node {
			sel, ok := n.(*ast.SelectorExpr)
			if !ok || called[sel] {
				return n
			}
			v, targs := variantOf(sel, false)
			if v == nil {
				return n
			}
			if len(v.Fields) > 0 {
				p.Errorf(f, sel.Pos(), "variant %s.%s requires %d values", v.Enum.Name, v.Name, len(v.Fields))
				return n
			}
			c := &ast.CallExpr{Fun: ctor(v, targs), Lparen: sel.End(), Rparen: sel.End()}
			fix[sel] = c
			return c
		})
	}
}
