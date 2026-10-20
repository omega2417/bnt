// Package lower implements stage S5 of the GoNext transpiler: the lowering
// of extension constructs to go/ast nodes. It generates the declarations of
// enums in the selected representation (R1 sealed interface, R2 flat tagged
// struct, R3 compact tagged struct), compiles match expressions into
// decision trees of switch statements, and lifts extension methods and
// generic methods to top-level functions.
package lower

import (
	"go/ast"
	"go/token"
	"go/types"
	"strings"
	"unicode"
	"unicode/utf8"

	"github.com/ORGANIZATION/gonext/internal/astx"
	"github.com/ORGANIZATION/gonext/internal/iast"
	"github.com/ORGANIZATION/gonext/internal/syntax"
)

// GnrtPath is the import path of the run-time helper package.
const GnrtPath = "github.com/ORGANIZATION/gonext/gnrt"

// Lowerer lowers the extension constructs of one package.
type Lowerer struct {
	Pkg *iast.Package
	// TypeExpr converts a type into a type expression valid in file f.
	TypeExpr func(f *iast.File, t types.Type) ast.Expr
	names    map[string]bool
	counter  int
}

// New returns a lowerer for pkg.
func New(pkg *iast.Package) *Lowerer {
	l := &Lowerer{Pkg: pkg, names: map[string]bool{}}
	all := append([]*ast.File{}, pkg.GoFiles...)
	for _, f := range pkg.Files {
		all = append(all, f.AST)
	}
	for _, f := range all {
		ast.Inspect(f, func(n ast.Node) bool {
			if id, ok := n.(*ast.Ident); ok {
				l.names[id.Name] = true
			}
			return true
		})
	}
	return l
}

// Fresh returns a new identifier name with the given prefix that does not
// occur in the package.
func (l *Lowerer) Fresh(prefix string) string {
	for {
		l.counter++
		n := prefix + itoa(l.counter)
		if !l.names[n] {
			l.names[n] = true
			return n
		}
	}
}

func itoa(i int) string {
	if i < 10 {
		return string(rune('0' + i))
	}
	return itoa(i/10) + string(rune('0'+i%10))
}

func upperFirst(s string) string {
	r, n := utf8.DecodeRuneInString(s)
	return string(unicode.ToUpper(r)) + s[n:]
}

func lowerFirst(s string) string {
	r, n := utf8.DecodeRuneInString(s)
	return string(unicode.ToLower(r)) + s[n:]
}

// CtorName returns the name of the constructor function of variant v.
func CtorName(v *iast.Variant) string {
	if v.Enum.Exported() {
		return "New" + v.Enum.Name + "_" + v.Name
	}
	return "new" + upperFirst(v.Enum.Name) + "_" + v.Name
}

// TagName returns the name of the tag constant of variant v.
func TagName(v *iast.Variant) string { return v.Enum.Name + "_" + v.Name }

func FlatField(v *iast.Variant, f *iast.Field) string {
	return lowerFirst(v.Name) + "_" + f.Name
}

func markerMethod(e *iast.Enum) string { return "is" + upperFirst(e.Name) }

// TypeRef returns the type expression E or E[T1, ..., Tn] for use inside
// declarations that carry the enum's type parameters.
func TypeRef(e *iast.Enum) ast.Expr {
	if !e.Generic() {
		return astx.Ident(e.Name)
	}
	var idx []ast.Expr
	for _, f := range e.TParams.List {
		for _, n := range f.Names {
			idx = append(idx, astx.Ident(n.Name))
		}
	}
	if len(idx) == 1 {
		return &ast.IndexExpr{X: astx.Ident(e.Name), Index: idx[0]}
	}
	return &ast.IndexListExpr{X: astx.Ident(e.Name), Indices: idx}
}

func (l *Lowerer) imp(f *iast.File, path string) string {
	name := path[strings.LastIndex(path, "/")+1:]
	return astx.AddImport(f.AST, path, name)
}

// Mangle returns an identifier fragment for a receiver type expression, as
// used in the names of lifted extension methods: []int -> IntSlice.
func Mangle(t ast.Expr) string {
	switch t := t.(type) {
	case *ast.Ident:
		return upperFirst(t.Name)
	case *ast.SelectorExpr:
		return upperFirst(Mangle(t.X)) + upperFirst(t.Sel.Name)
	case *ast.StarExpr:
		return "Ptr" + Mangle(t.X)
	case *ast.ArrayType:
		if t.Len == nil {
			return Mangle(t.Elt) + "Slice"
		}
		return Mangle(t.Elt) + "Array"
	case *ast.MapType:
		return "Map" + Mangle(t.Key) + Mangle(t.Value)
	case *ast.ChanType:
		return "Chan" + Mangle(t.Value)
	case *ast.IndexExpr:
		return Mangle(t.X)
	case *ast.IndexListExpr:
		return Mangle(t.X)
	case *ast.FuncType:
		return "Func"
	case *ast.InterfaceType:
		return "Any"
	case *ast.StructType:
		return "Struct"
	case *ast.Ellipsis:
		return Mangle(t.Elt) + "Slice"
	}
	return "T"
}

// ExtName returns the name of the top-level function an extension method is
// lifted to: ext_IntSlice_sum, or Ext_IntSlice_Sum when exported.
func ExtName(recv ast.Expr, method string) string {
	method = strings.TrimPrefix(method, syntax.KeywordPfx)
	if token.IsExported(method) {
		return "Ext_" + Mangle(recv) + "_" + method
	}
	return "ext_" + Mangle(recv) + "_" + method
}

// MethodName returns the name of the top-level generic function a generic
// method is lifted to: List_map.
func MethodName(typeName, method string) string {
	return typeName + "_" + strings.TrimPrefix(method, syntax.KeywordPfx)
}
