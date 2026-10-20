package iast

import (
	"fmt"
	"go/ast"
	"go/parser"
	"go/token"
	"strconv"
	"strings"

	"github.com/ORGANIZATION/gonext/internal/astx"
	"github.com/ORGANIZATION/gonext/internal/syntax"
)

func newError(f *File, pos token.Pos, format string, args ...any) *syntax.Error {
	var p token.Position
	if f != nil {
		p = f.Syn.Position(pos)
	}
	return &syntax.Error{Pos: p, Msg: fmt.Sprintf(format, args...)}
}

// ParseFieldList parses "(a, b T)" into a field list without positions.
func ParseFieldList(text string) (*ast.FieldList, error) {
	f, err := parser.ParseFile(token.NewFileSet(), "", "package p; func _"+text+" {}", parser.SkipObjectResolution)
	if err != nil {
		return nil, err
	}
	fl := f.Decls[0].(*ast.FuncDecl).Type.Params
	astx.ClearPos(fl)
	return fl, nil
}

// ParseTypeParams parses "[T any, U comparable]".
func ParseTypeParams(text string) (*ast.FieldList, error) {
	f, err := parser.ParseFile(token.NewFileSet(), "", "package p; func _"+text+"() {}", parser.SkipObjectResolution)
	if err != nil {
		return nil, err
	}
	fl := f.Decls[0].(*ast.FuncDecl).Type.TypeParams
	astx.ClearPos(fl)
	return fl, nil
}

// ParseExpr parses an expression and clears its positions.
func ParseExpr(text string) (ast.Expr, error) {
	e, err := parser.ParseExpr(text)
	if err != nil {
		return nil, err
	}
	astx.ClearPos(e)
	return e, nil
}

// Build constructs the IAST of a package from parsed GoNext files and the
// plain Go files compiled with them.
func Build(fset *token.FileSet, dir string, files []*syntax.File, goFiles []*ast.File) *Package {
	p := &Package{
		Dir:        dir,
		Fset:       fset,
		GoFiles:    goFiles,
		EnumByName: map[string]*Enum{},
		Funcs:      map[*ast.FuncDecl]*Func{},
		Lambdas:    map[*ast.FuncLit]*Lambda{},
		Origin:     map[ast.Node]token.Position{},
	}
	for _, sf := range files {
		f := &File{Syn: sf, AST: sf.AST}
		p.Files = append(p.Files, f)
		if p.Name == "" {
			p.Name = sf.AST.Name.Name
		}
	}
	for _, f := range p.Files {
		p.collectEnums(f)
	}
	for _, f := range p.Files {
		p.collectFuncs(f)
	}
	for _, f := range p.Files {
		p.collectExprs(f)
	}
	return p
}

func (p *Package) collectEnums(f *File) {
	for _, d := range f.Syn.Enums {
		e := &Enum{
			Name: d.Name,
			File: f,
			Pos:  f.Syn.TokFile.Pos(d.Offset),
			Decl: d,
			Repr: Repr(d.Repr),
		}
		if d.Repr != "" && !ValidRepr(e.Repr) {
			p.Errs = append(p.Errs, &syntax.Error{Pos: d.Pos, Msg: fmt.Sprintf("unknown enum representation %q (want interface, flat or compact)", d.Repr)})
		}
		if d.TParams != "" {
			tp, err := ParseTypeParams(d.TParams)
			if err != nil {
				p.Errs = append(p.Errs, &syntax.Error{Pos: d.Pos, Msg: "invalid type parameters of enum " + d.Name})
				continue
			}
			e.TParams = tp
		}
		if p.EnumByName[d.Name] != nil {
			p.Errs = append(p.Errs, &syntax.Error{Pos: d.Pos, Msg: "enum " + d.Name + " redeclared"})
			continue
		}
		for i, vd := range d.Variants {
			v := &Variant{Enum: e, Name: vd.Name, Index: i, Pos: vd.Pos}
			if e.Variant(vd.Name) != nil {
				p.Errs = append(p.Errs, &syntax.Error{Pos: vd.Pos, Msg: "duplicate variant " + vd.Name})
			}
			if vd.Params != "" {
				fl, err := ParseFieldList(vd.Params)
				if err != nil {
					p.Errs = append(p.Errs, &syntax.Error{Pos: vd.Pos, Msg: "invalid payload of variant " + vd.Name})
					continue
				}
				n := 0
				for _, fld := range fl.List {
					if len(fld.Names) == 0 {
						v.Fields = append(v.Fields, &Field{Name: "f" + strconv.Itoa(n), Type: fld.Type})
						n++
						continue
					}
					for _, name := range fld.Names {
						v.Fields = append(v.Fields, &Field{Name: name.Name, Type: fld.Type})
						n++
					}
				}
			}
			e.Variants = append(e.Variants, v)
		}
		p.Enums = append(p.Enums, e)
		p.EnumByName[e.Name] = e
	}
}

func (p *Package) collectFuncs(f *File) {
	tf := f.Syn.TokFile
	for _, d := range f.AST.Decls {
		fd, ok := d.(*ast.FuncDecl)
		if !ok {
			continue
		}
		if f.Syn.ExtFuncs[tf.Offset(fd.Type.Func)] {
			if fd.Recv == nil || len(fd.Recv.List) != 1 {
				p.Errorf(f, fd.Pos(), "extension method %s must have exactly one receiver", fd.Name.Name)
				continue
			}
			p.Exts = append(p.Exts, &Ext{Name: strings.TrimPrefix(fd.Name.Name, syntax.KeywordPfx), Decl: fd, File: f})
		}
		if tp, ok := f.Syn.MethodTParams[tf.Offset(fd.Name.Pos())]; ok {
			fl, err := ParseTypeParams(tp)
			if err != nil {
				p.Errorf(f, fd.Name.Pos(), "invalid method type parameters")
				continue
			}
			fd.Type.TypeParams = fl
			if !f.Syn.ExtFuncs[tf.Offset(fd.Type.Func)] {
				p.Methods = append(p.Methods, &GenMethod{TypeName: recvTypeName(fd), Name: fd.Name.Name, Decl: fd, File: f})
			}
		}
		// default parameter values
		var fi *Func
		idx := 0
		for _, fld := range fd.Type.Params.List {
			n := len(fld.Names)
			if n == 0 {
				n = 1
			}
			for off, text := range f.Syn.Defaults {
				pos := tf.Pos(off)
				if pos < fld.Type.End() || (fld != fd.Type.Params.List[len(fd.Type.Params.List)-1] && pos > nextField(fd, fld).Pos()) || pos > fd.Type.Params.Closing {
					continue
				}
				if len(fld.Names) != 1 {
					p.Errorf(f, fld.Pos(), "a parameter with a default value must be declared with its own type")
					continue
				}
				e, err := ParseExpr(text)
				if err != nil {
					p.Errorf(f, pos, "invalid default value: %v", err)
					continue
				}
				if fi == nil {
					fi = &Func{Decl: fd, File: f, Defaults: map[int]ast.Expr{}}
				}
				fi.Defaults[idx] = e
			}
			idx += n
		}
		if fi != nil {
			if fd.Type.Params.List[len(fd.Type.Params.List)-1].Type != nil {
				if _, ok := fd.Type.Params.List[len(fd.Type.Params.List)-1].Type.(*ast.Ellipsis); ok {
					if _, has := fi.Defaults[idx-1]; has {
						p.Errorf(f, fd.Pos(), "variadic parameter cannot have a default value")
					}
				}
			}
			p.Funcs[fd] = fi
		}
	}
}

func nextField(fd *ast.FuncDecl, fld *ast.Field) *ast.Field {
	l := fd.Type.Params.List
	for i := range l {
		if l[i] == fld && i+1 < len(l) {
			return l[i+1]
		}
	}
	return fld
}

func recvTypeName(fd *ast.FuncDecl) string {
	if fd.Recv == nil || len(fd.Recv.List) == 0 {
		return ""
	}
	t := fd.Recv.List[0].Type
	if st, ok := t.(*ast.StarExpr); ok {
		t = st.X
	}
	switch x := t.(type) {
	case *ast.IndexExpr:
		t = x.X
	case *ast.IndexListExpr:
		t = x.X
	}
	if id, ok := t.(*ast.Ident); ok {
		return id.Name
	}
	return ""
}

// collectExprs finds match placeholders and short anonymous functions.
func (p *Package) collectExprs(f *File) {
	stmtMatch := map[*ast.CallExpr]bool{}
	ast.Inspect(f.AST, func(n ast.Node) bool {
		switch n := n.(type) {
		case *ast.ExprStmt:
			if c, ok := n.X.(*ast.CallExpr); ok && isPlaceholder(c, syntax.MatchFunc) {
				stmtMatch[c] = true
			}
		case *ast.CallExpr:
			if isPlaceholder(n, syntax.MatchFunc) {
				p.buildMatch(f, n, stmtMatch[n])
			}
		case *ast.FuncLit:
			if isInferLit(n) {
				p.Lambdas[n] = &Lambda{Lit: n, File: f}
			}
		}
		return true
	})
}

func isInferLit(fl *ast.FuncLit) bool {
	if fl.Type.Results != nil {
		for _, r := range fl.Type.Results.List {
			if IsInfer(r.Type) {
				return true
			}
		}
	}
	for _, prm := range fl.Type.Params.List {
		if IsInfer(prm.Type) {
			return true
		}
	}
	return false
}

func isPlaceholder(c *ast.CallExpr, name string) bool {
	id, ok := c.Fun.(*ast.Ident)
	return ok && id.Name == name
}

func (p *Package) buildMatch(f *File, c *ast.CallExpr, stmt bool) {
	id, _ := strconv.Atoi(c.Args[0].(*ast.BasicLit).Value)
	d := f.Syn.Matches[id]
	scrut := c.Args[1]
	if pe, ok := scrut.(*ast.ParenExpr); ok {
		scrut = pe.X
	}
	m := &Match{Decl: d, File: f, Call: c, Scrut: scrut, Stmt: stmt, Pos: c.Pos(), End: c.End()}
	args := c.Args[2:]
	for i, ad := range d.Arms {
		a := &Arm{Decl: ad}
		if g, ok := args[2*i].(*ast.FuncLit); ok {
			a.Guard = g.Body.List[0].(*ast.ReturnStmt).Results[0]
		}
		body := args[2*i+1].(*ast.FuncLit)
		if ad.Block {
			a.Block = body.Body
		} else {
			a.Body = body.Body.List[0].(*ast.ReturnStmt).Results[0]
		}
		m.Arms = append(m.Arms, a)
	}
	p.resolvePatterns(m)
	p.Matches = append(p.Matches, m)
}

// resolvePatterns classifies the patterns of a match and determines the enum
// it ranges over from the variant names used in its patterns.
func (p *Package) resolvePatterns(m *Match) {
	// candidate enums
	var enum *Enum
	ambiguous := false
	for _, a := range m.Arms {
		for _, pd := range a.Decl.Patterns {
			if pd.Wildcard || pd.Name == "" {
				continue
			}
			var cands []*Enum
			if pd.Qual != "" {
				if e := p.EnumByName[pd.Qual]; e != nil && e.Variant(pd.Name) != nil {
					cands = append(cands, e)
				}
			} else {
				for _, e := range p.Enums {
					if v := e.Variant(pd.Name); v != nil && (pd.Parens || len(v.Fields) == 0) {
						cands = append(cands, e)
					}
				}
			}
			switch {
			case len(cands) == 1 && enum == nil:
				enum = cands[0]
			case len(cands) == 1 && enum != cands[0]:
				p.Errs = append(p.Errs, &syntax.Error{Pos: pd.Pos, Msg: fmt.Sprintf("variant %s does not belong to enum %s", pd.Name, enum.Name)})
			case len(cands) > 1:
				ambiguous = true
			}
		}
	}
	if enum == nil && ambiguous {
		p.Errs = append(p.Errs, &syntax.Error{Pos: m.Decl.Pos, Msg: "ambiguous variant names in match; qualify a pattern as Enum.Variant"})
		return
	}
	m.Enum = enum
	for i, a := range m.Arms {
		for _, pd := range a.Decl.Patterns {
			pat := &Pattern{Decl: pd}
			switch {
			case pd.Wildcard:
				pat.Kind = PatWild
			case enum != nil && pd.Name != "" && (pd.Qual == "" || pd.Qual == enum.Name) && enum.Variant(pd.Name) != nil:
				v := enum.Variant(pd.Name)
				pat.Kind = PatVariant
				pat.Variant = v
				pat.Binders = pd.Binders
				if !pd.Parens && len(v.Fields) > 0 {
					p.Errs = append(p.Errs, &syntax.Error{Pos: pd.Pos, Msg: fmt.Sprintf("variant %s has payload; use %s(...) or %s(_...)", v.Name, v.Name, v.Name)})
				} else if pd.Parens && len(pd.Binders) != len(v.Fields) {
					p.Errs = append(p.Errs, &syntax.Error{Pos: pd.Pos, Msg: fmt.Sprintf("pattern %s binds %d values, variant has %d", v.Name, len(pd.Binders), len(v.Fields))})
				}
				if len(a.Decl.Patterns) > 1 && len(pd.Binders) > 0 {
					for _, b := range pd.Binders {
						if b != "_" {
							p.Errs = append(p.Errs, &syntax.Error{Pos: pd.Pos, Msg: "alternative patterns cannot bind variables"})
							break
						}
					}
				}
			case pd.Parens:
				p.Errs = append(p.Errs, &syntax.Error{Pos: pd.Pos, Msg: fmt.Sprintf("unknown variant %s", pd.Name)})
				continue
			default:
				if enum != nil {
					p.Errs = append(p.Errs, &syntax.Error{Pos: pd.Pos, Msg: fmt.Sprintf("%s is not a variant of %s", pd.Expr, enum.Name)})
					continue
				}
				e, err := ParseExpr(pd.Expr)
				if err != nil {
					p.Errs = append(p.Errs, &syntax.Error{Pos: pd.Pos, Msg: "invalid pattern " + pd.Expr})
					continue
				}
				pat.Kind = PatConst
				pat.Const = e
			}
			m.Arms[i].Pats = append(m.Arms[i].Pats, pat)
		}
	}
}
