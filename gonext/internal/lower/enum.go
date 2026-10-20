package lower

import (
	"fmt"
	"go/ast"
	"go/parser"
	"go/token"
	"go/types"
	"strings"

	"github.com/ORGANIZATION/gonext/internal/astx"
	"github.com/ORGANIZATION/gonext/internal/iast"
)

func parseDecls(src string) ([]ast.Decl, error) {
	f, err := parser.ParseFile(token.NewFileSet(), "", "package p\n"+src, parser.SkipObjectResolution)
	if err != nil {
		return nil, fmt.Errorf("internal error: generated code does not parse: %v\n%s", err, src)
	}
	for _, d := range f.Decls {
		astx.ClearPos(d)
	}
	return f.Decls, nil
}

func tparamsText(e *iast.Enum) (decl, ref string) {
	if !e.Generic() {
		return "", ""
	}
	return astx.String(&ast.IndexListExpr{X: astx.Ident(""), Indices: fieldsAsExprs(e.TParams)}),
		astx.String(TypeRef(e))[len(e.Name):]
}

// fieldsAsExprs renders a type parameter list "T any, U comparable" as
// expressions so that it can be printed between brackets.
func fieldsAsExprs(fl *ast.FieldList) []ast.Expr {
	var out []ast.Expr
	for _, f := range fl.List {
		var names []string
		for _, n := range f.Names {
			names = append(names, n.Name)
		}
		out = append(out, astx.Ident(strings.Join(names, ", ")+" "+astx.String(f.Type)))
	}
	return out
}

// GenEnum generates the declarations of enum e in its representation and
// inserts them into the enum's file at the position of the declaration.
func (l *Lowerer) GenEnum(e *iast.Enum) error {
	var src string
	switch e.Repr {
	case iast.ReprInterface:
		src = l.genInterface(e)
	case iast.ReprCompact:
		src = l.genCompact(e)
	default:
		src = l.genFlat(e)
	}
	decls, err := parseDecls(src)
	if err != nil {
		return err
	}
	f := e.File.AST
	// remove previously generated declarations
	if len(e.Gen) > 0 {
		gen := map[ast.Decl]bool{}
		for _, d := range e.Gen {
			gen[d] = true
		}
		var keep []ast.Decl
		for _, d := range f.Decls {
			if !gen[d] {
				keep = append(keep, d)
			}
		}
		f.Decls = keep
	}
	// anchor: the first declaration gets the enum's position so that the
	// doc comment stays in front of it
	switch d := decls[0].(type) {
	case *ast.GenDecl:
		d.TokPos = e.Pos
	}
	// go/types needs a valid position for the names of receiver base types
	for _, d := range decls {
		if g, ok := d.(*ast.GenDecl); ok {
			for _, sp := range g.Specs {
				if ts, ok := sp.(*ast.TypeSpec); ok {
					ts.Name.NamePos = e.Pos
				}
			}
		}
	}
	for i, d := range decls {
		if i == 0 {
			l.Pkg.Origin[d] = e.Decl.Pos
			continue
		}
		if fd, ok := d.(*ast.FuncDecl); ok && strings.Contains(fd.Name.Name, "_") {
			name := fd.Name.Name[strings.LastIndex(fd.Name.Name, "_")+1:]
			if v := e.Variant(name); v != nil {
				l.Pkg.Origin[d] = v.Pos
				continue
			}
		}
		l.Pkg.Origin[d] = e.Decl.Pos
	}
	at := len(f.Decls)
	for i, d := range f.Decls {
		if d.Pos().IsValid() && d.Pos() > e.Pos {
			at = i
			break
		}
	}
	f.Decls = append(f.Decls[:at], append(decls, f.Decls[at:]...)...)
	e.Gen = decls
	return nil
}

func (l *Lowerer) docComment(e *iast.Enum) string {
	return fmt.Sprintf("// %s is the GoNext enum %s lowered to the %s representation.\n", e.Name, e.Name, e.Repr)
}

func (l *Lowerer) genInterface(e *iast.Enum) string {
	var b strings.Builder
	fmt.Fprintf(&b, "type %s interface{ %s() }\n", e.Name, markerMethod(e))
	for _, v := range e.Variants {
		fmt.Fprintf(&b, "type %s struct {", TagName(v))
		for _, f := range v.Fields {
			fmt.Fprintf(&b, "%s %s;", f.Name, astx.String(f.Type))
		}
		b.WriteString("}\n")
		fmt.Fprintf(&b, "func (%s) %s() {}\n", TagName(v), markerMethod(e))
	}
	for _, v := range e.Variants {
		fmt.Fprintf(&b, "func %s(%s) %s { return %s{", CtorName(v), params(v), e.Name, TagName(v))
		for _, f := range v.Fields {
			fmt.Fprintf(&b, "%s: %s,", f.Name, f.Name)
		}
		b.WriteString("} }\n")
	}
	return b.String()
}

func params(v *iast.Variant) string {
	var ps []string
	for _, f := range v.Fields {
		ps = append(ps, f.Name+" "+astx.String(f.Type))
	}
	return strings.Join(ps, ", ")
}

func tagType(e *iast.Enum) string {
	if len(e.Variants) < 255 {
		return "uint8"
	}
	return "uint16"
}

func (l *Lowerer) tagConsts(b *strings.Builder, e *iast.Enum) {
	b.WriteString("const (\n")
	for i, v := range e.Variants {
		if i == 0 {
			fmt.Fprintf(b, "%s %s = iota + 1\n", TagName(v), tagType(e))
		} else {
			fmt.Fprintf(b, "%s\n", TagName(v))
		}
	}
	b.WriteString(")\n")
}

func (l *Lowerer) genFlat(e *iast.Enum) string {
	var b strings.Builder
	tdecl, tref := tparamsText(e)
	fmt.Fprintf(&b, "type %s%s struct {\ntag %s\n", e.Name, tdecl, tagType(e))
	for _, v := range e.Variants {
		for _, f := range v.Fields {
			fmt.Fprintf(&b, "%s %s\n", FlatField(v, f), astx.String(f.Type))
		}
	}
	b.WriteString("}\n")
	l.tagConsts(&b, e)
	for _, v := range e.Variants {
		fmt.Fprintf(&b, "func %s%s(%s) %s%s { return %s%s{tag: %s", CtorName(v), tdecl, params(v), e.Name, tref, e.Name, tref, TagName(v))
		for _, f := range v.Fields {
			fmt.Fprintf(&b, ", %s: %s", FlatField(v, f), f.Name)
		}
		b.WriteString("} }\n")
	}
	return b.String()
}

// Classify determines how a payload of type t is stored in the compact
// representation.
func Classify(t types.Type) string {
	switch u := t.Underlying().(type) {
	case *types.Basic:
		switch {
		case u.Kind() == types.Bool:
			return "bool"
		case u.Kind() == types.Float64:
			return "float64"
		case u.Kind() == types.Float32:
			return "float32"
		case u.Kind() == types.String:
			return "string"
		case u.Kind() == types.UnsafePointer:
			return "unsafe"
		case u.Info()&types.IsInteger != 0:
			return "int"
		}
	case *types.Pointer:
		return "ptr"
	case *types.Slice:
		return "slice"
	case *types.Map, *types.Chan, *types.Signature:
		return "ref"
	}
	return "typed"
}

// HasPointers reports whether values of type t contain pointers that the
// garbage collector must see.
func HasPointers(t types.Type) bool {
	switch u := t.Underlying().(type) {
	case *types.Basic:
		return u.Kind() == types.String || u.Kind() == types.UnsafePointer
	case *types.Array:
		return u.Len() > 0 && HasPointers(u.Elem())
	case *types.Struct:
		for i := 0; i < u.NumFields(); i++ {
			if HasPointers(u.Field(i).Type()) {
				return true
			}
		}
		return false
	case *types.TypeParam:
		return true
	}
	return true
}

// ComputeLayout assigns every payload field of a compact enum to a slot and
// checks the invariant that every pointer-carrying field is stored in a slot
// that the garbage collector scans (Equation 4 of the GoNext article).
func (l *Lowerer) ComputeLayout(e *iast.Enum) error {
	lay := &iast.Layout{}
	for _, v := range e.Variants {
		w, p, n := 0, 0, 0
		for _, f := range v.Fields {
			if f.T == nil {
				return fmt.Errorf("type of payload %s.%s unknown", v.Name, f.Name)
			}
			s := iast.Slot{Conv: Classify(f.T), Len: -1, Cap: -1}
			switch s.Conv {
			case "int", "float64", "float32", "bool":
				s.Kind, s.Index = iast.SlotWord, w
				w++
			case "ptr", "unsafe", "ref":
				s.Kind, s.Index = iast.SlotPtr, p
				p++
			case "string":
				s.Kind, s.Index, s.Len = iast.SlotPtr, p, n
				p++
				n++
			case "slice":
				s.Kind, s.Index, s.Len, s.Cap = iast.SlotPtr, p, n, n+1
				p++
				n += 2
			default:
				s.Kind = iast.SlotTyped
				s.Typed = FlatField(v, f)
				lay.Typed = append(lay.Typed, &ast.Field{Names: []*ast.Ident{astx.Ident(s.Typed)}, Type: f.Type})
			}
			if HasPointers(f.T) && s.Kind == iast.SlotWord {
				return fmt.Errorf("internal error: pointer payload %s.%s assigned to an integer word", v.Name, f.Name)
			}
			f.Slot = s
		}
		lay.Words = max(lay.Words, w)
		lay.Ptrs = max(lay.Ptrs, p)
		lay.Lens = max(lay.Lens, n)
	}
	e.Layout = lay
	return nil
}

func ptrName(lay *iast.Layout, i int) string {
	if lay.Ptrs == 1 {
		return "p"
	}
	return fmt.Sprintf("p%d", i)
}

func lenName(lay *iast.Layout, i int) string {
	if lay.Lens == 1 {
		return "n"
	}
	return fmt.Sprintf("n%d", i)
}

func (l *Lowerer) genCompact(e *iast.Enum) string {
	f := e.File
	lay := e.Layout
	var b strings.Builder
	fmt.Fprintf(&b, "type %s struct {\ntag %s\n", e.Name, tagType(e))
	if lay.Words > 0 {
		var ws []string
		for i := 0; i < lay.Words; i++ {
			ws = append(ws, fmt.Sprintf("w%d", i))
		}
		fmt.Fprintf(&b, "%s uint64\n", strings.Join(ws, ", "))
	}
	for i := 0; i < lay.Ptrs; i++ {
		fmt.Fprintf(&b, "%s %s.Pointer\n", ptrName(lay, i), l.imp(f, "unsafe"))
	}
	for i := 0; i < lay.Lens; i++ {
		fmt.Fprintf(&b, "%s int\n", lenName(lay, i))
	}
	for _, t := range lay.Typed {
		fmt.Fprintf(&b, "%s %s\n", t.Names[0].Name, astx.String(t.Type))
	}
	b.WriteString("}\n")
	l.tagConsts(&b, e)
	for _, v := range e.Variants {
		fmt.Fprintf(&b, "func %s(%s) %s { return %s{tag: %s", CtorName(v), params(v), e.Name, e.Name, TagName(v))
		for _, fl := range v.Fields {
			for _, kv := range l.store(f, lay, fl) {
				fmt.Fprintf(&b, ", %s", kv)
			}
		}
		b.WriteString("} }\n")
	}
	return b.String()
}

func isBasic(t types.Type, k types.BasicKind) bool {
	b, ok := t.(*types.Basic)
	return ok && b.Kind() == k
}

// store returns the key: value elements that store payload field fl.
func (l *Lowerer) store(f *iast.File, lay *iast.Layout, fl *iast.Field) []string {
	x := fl.Name
	s := fl.Slot
	w := fmt.Sprintf("w%d", s.Index)
	switch s.Conv {
	case "int":
		return []string{fmt.Sprintf("%s: uint64(%s)", w, x)}
	case "float64":
		if !isBasic(fl.T, types.Float64) {
			x = "float64(" + x + ")"
		}
		return []string{fmt.Sprintf("%s: %s.Float64bits(%s)", w, l.imp(f, "math"), x)}
	case "float32":
		if !isBasic(fl.T, types.Float32) {
			x = "float32(" + x + ")"
		}
		return []string{fmt.Sprintf("%s: uint64(%s.Float32bits(%s))", w, l.imp(f, "math"), x)}
	case "bool":
		return []string{fmt.Sprintf("%s: %s.BoolWord(%s)", w, l.imp(f, GnrtPath), x)}
	case "string":
		u := l.imp(f, "unsafe")
		y := x
		if !isBasic(fl.T, types.String) {
			y = "string(" + x + ")"
		}
		return []string{
			fmt.Sprintf("%s: %s.Pointer(%s.StringData(%s))", ptrName(lay, s.Index), u, u, y),
			fmt.Sprintf("%s: len(%s)", lenName(lay, s.Len), x),
		}
	case "slice":
		u := l.imp(f, "unsafe")
		return []string{
			fmt.Sprintf("%s: %s.Pointer(%s.SliceData(%s))", ptrName(lay, s.Index), u, u, x),
			fmt.Sprintf("%s: len(%s)", lenName(lay, s.Len), x),
			fmt.Sprintf("%s: cap(%s)", lenName(lay, s.Cap), x),
		}
	case "ptr", "unsafe":
		return []string{fmt.Sprintf("%s: %s.Pointer(%s)", ptrName(lay, s.Index), l.imp(f, "unsafe"), x)}
	case "ref":
		return []string{fmt.Sprintf("%s: %s.Ptr(%s)", ptrName(lay, s.Index), l.imp(f, GnrtPath), x)}
	}
	return []string{fmt.Sprintf("%s: %s", s.Typed, x)}
}

// Load returns an expression that reads payload field fl of variant v from
// the value named sv.
func (l *Lowerer) Load(f *iast.File, v *iast.Variant, fl *iast.Field, sv string) ast.Expr {
	var src string
	e := v.Enum
	switch e.Repr {
	case iast.ReprInterface:
		src = sv + "." + fl.Name
	case iast.ReprFlat:
		src = sv + "." + FlatField(v, fl)
	default:
		src = l.loadCompact(f, e.Layout, fl, sv)
	}
	x, err := iast.ParseExpr(src)
	if err != nil {
		panic(fmt.Sprintf("internal error: %v: %s", err, src))
	}
	return x
}

func (l *Lowerer) loadCompact(f *iast.File, lay *iast.Layout, fl *iast.Field, sv string) string {
	s := fl.Slot
	T := astx.String(fl.Type)
	conv := func(exact bool, x string) string {
		if exact {
			return x
		}
		return T + "(" + x + ")"
	}
	w := fmt.Sprintf("%s.w%d", sv, s.Index)
	switch s.Conv {
	case "int":
		return fmt.Sprintf("%s(%s)", T, w)
	case "float64":
		return conv(isBasic(fl.T, types.Float64), fmt.Sprintf("%s.Float64frombits(%s)", l.imp(f, "math"), w))
	case "float32":
		return conv(isBasic(fl.T, types.Float32), fmt.Sprintf("%s.Float32frombits(uint32(%s))", l.imp(f, "math"), w))
	case "bool":
		return conv(isBasic(fl.T, types.Bool), w+" != 0")
	case "string":
		u := l.imp(f, "unsafe")
		return conv(isBasic(fl.T, types.String), fmt.Sprintf("%s.String((*byte)(%s.%s), %s.%s)", u, sv, ptrName(lay, s.Index), sv, lenName(lay, s.Len)))
	case "slice":
		u := l.imp(f, "unsafe")
		elem := astx.String(l.TypeExpr(f, fl.T.Underlying().(*types.Slice).Elem()))
		_, named := fl.T.(*types.Named)
		return conv(!named, fmt.Sprintf("%s.Slice((*%s)(%s.%s), %s.%s)[:%s.%s]", u, elem, sv, ptrName(lay, s.Index), sv, lenName(lay, s.Cap), sv, lenName(lay, s.Len)))
	case "ptr":
		return fmt.Sprintf("(%s)(%s.%s)", T, sv, ptrName(lay, s.Index))
	case "unsafe":
		return conv(isBasic(fl.T, types.UnsafePointer), fmt.Sprintf("%s.%s", sv, ptrName(lay, s.Index)))
	case "ref":
		return fmt.Sprintf("%s.FromPtr[%s](%s.%s)", l.imp(f, GnrtPath), T, sv, ptrName(lay, s.Index))
	}
	return sv + "." + s.Typed
}
