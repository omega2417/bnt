// Package iast implements stage S2 of the GoNext transpiler: the internal
// abstract syntax tree. The IAST reuses the node structure of go/ast and adds
// node kinds for the extension constructs (enums, variants, match
// expressions and arms, patterns, short anonymous functions, functions with
// default parameters, extension methods and generic methods). Every node
// keeps the position of its GoNext source.
package iast

import (
	"go/ast"
	"go/token"
	"go/types"

	"github.com/ORGANIZATION/gonext/internal/syntax"
)

// Repr selects the Go representation of an enum.
type Repr string

const (
	ReprInterface Repr = "interface" // R1: sealed interface, one struct per variant
	ReprFlat      Repr = "flat"      // R2: tagged struct with the union of all fields
	ReprCompact   Repr = "compact"   // R3: tagged struct with shared words and pointer slots
)

// ValidRepr reports whether r names a representation.
func ValidRepr(r Repr) bool {
	return r == ReprInterface || r == ReprFlat || r == ReprCompact
}

// Package is a GoNext package: its GoNext files, the plain Go files that are
// compiled together with them, and the tables of extension constructs.
type Package struct {
	Name    string
	Dir     string
	Fset    *token.FileSet
	Files   []*File
	GoFiles []*ast.File

	Enums      []*Enum
	EnumByName map[string]*Enum
	Funcs      map[*ast.FuncDecl]*Func
	Exts       []*Ext
	Methods    []*GenMethod
	Matches    []*Match
	Lambdas    map[*ast.FuncLit]*Lambda

	// Origin maps synthetic nodes to the GoNext position of the construct
	// they were generated from; it is used for line directives.
	Origin map[ast.Node]token.Position

	Errs syntax.ErrorList
}

// File is one GoNext source file.
type File struct {
	Syn *syntax.File
	AST *ast.File
}

// Enum is an enum type with associated data.
type Enum struct {
	Name     string
	TParams  *ast.FieldList
	Variants []*Variant
	Repr     Repr
	File     *File
	Pos      token.Pos // anchor in the rewritten file
	Decl     *syntax.EnumDecl
	Gen      []ast.Decl // generated declarations
	Layout   *Layout    // compact layout, if Repr == ReprCompact
}

// Exported reports whether the enum type is exported.
func (e *Enum) Exported() bool { return token.IsExported(e.Name) }

// Generic reports whether the enum has type parameters.
func (e *Enum) Generic() bool { return e.TParams != nil && len(e.TParams.List) > 0 }

// Variant returns the variant with the given name.
func (e *Enum) Variant(name string) *Variant {
	for _, v := range e.Variants {
		if v.Name == name {
			return v
		}
	}
	return nil
}

// Variant is one alternative of an enum.
type Variant struct {
	Enum   *Enum
	Name   string
	Index  int
	Fields []*Field
	Pos    token.Position
}

// Field is a payload field of a variant.
type Field struct {
	Name string
	Type ast.Expr
	T    types.Type // set after the first type-checking round
	Slot Slot       // storage in the compact representation
}

// SlotKind classifies the storage of a payload field in R3.
type SlotKind int

const (
	SlotWord  SlotKind = iota // scalar word wN uint64
	SlotPtr                   // pointer slot pN unsafe.Pointer
	SlotTyped                 // dedicated typed field
)

// Slot describes where a payload field lives in the compact representation.
type Slot struct {
	Kind  SlotKind
	Index int    // word or pointer slot index
	Len   int    // index of the length word for strings and slices, else -1
	Cap   int    // index of the capacity word for slices, else -1
	Conv  string // conversion class: int, float64, float32, bool, string, slice, ptr, unsafe, ref
	Typed string // name of the dedicated field
}

// Layout is the slot assignment of a compact enum.
type Layout struct {
	Words, Ptrs, Lens int
	Typed             []*ast.Field
}

// Func describes a function declared in GoNext source that has default
// parameter values, or whose receiver was lifted into the first parameter.
type Func struct {
	Decl     *ast.FuncDecl
	File     *File
	Defaults map[int]ast.Expr // parameter index (excluding a lifted receiver) -> default
	Lifted   bool             // the first parameter is a lifted receiver
}

// Ext is an extension method.
type Ext struct {
	Name string // method name in GoNext source
	Decl *ast.FuncDecl
	File *File
}

// GenMethod is a generic method lifted to a top-level generic function.
type GenMethod struct {
	TypeName string
	Name     string
	Decl     *ast.FuncDecl
	File     *File
}

// Match is a match expression or statement.
type Match struct {
	Decl  *syntax.MatchDecl
	File  *File
	Call  *ast.CallExpr // placeholder call in the AST
	Scrut ast.Expr
	Arms  []*Arm
	Enum  *Enum // nil for matches over constants
	Stmt  bool  // used as a statement
	Pos   token.Pos
	End   token.Pos
	Done  bool // replaced by its final statement form

	// Set by lowering.
	Lit    *ast.FuncLit  // the function literal of the expression form
	Expr   *ast.CallExpr // the expression form (immediately invoked literal)
	Result ast.Expr      // result type, or the infer placeholder
}

// Arm is one arm of a match.
type Arm struct {
	Decl  *syntax.ArmDecl
	Pats  []*Pattern
	Guard ast.Expr
	Body  ast.Expr       // expression arm
	Block *ast.BlockStmt // block arm
}

// PatKind classifies patterns.
type PatKind int

const (
	PatWild PatKind = iota
	PatVariant
	PatConst
)

// Pattern is one alternative of an arm pattern.
type Pattern struct {
	Kind    PatKind
	Variant *Variant
	Binders []string
	Const   ast.Expr
	Decl    *syntax.PatternDecl
}

// Lambda is a short anonymous function x => expr.
type Lambda struct {
	Lit  *ast.FuncLit
	File *File
}

// IsInfer reports whether e is the type-inference placeholder.
func IsInfer(e ast.Expr) bool {
	id, ok := e.(*ast.Ident)
	return ok && id.Name == syntax.InferType
}

// Errorf records a diagnostic at a rewritten position of file f.
func (p *Package) Errorf(f *File, pos token.Pos, format string, args ...any) {
	p.Errs = append(p.Errs, newError(f, pos, format, args...))
}

// FileOf returns the GoNext file containing pos, or nil.
func (p *Package) FileOf(pos token.Pos) *File {
	if !pos.IsValid() {
		return nil
	}
	for _, f := range p.Files {
		tf := f.Syn.TokFile
		if int(pos) >= tf.Base() && int(pos) <= tf.Base()+tf.Size() {
			return f
		}
	}
	return nil
}

// Mark records that the synthetic node n originates from the rewritten
// position pos.
func (p *Package) Mark(n ast.Node, pos token.Pos) {
	if f := p.FileOf(pos); f != nil {
		p.Origin[n] = f.Syn.Position(pos)
	}
}

// Position returns the GoNext position of a node: its recorded origin, or
// the position of its first token.
func (p *Package) Position(n ast.Node) (token.Position, bool) {
	if pos, ok := p.Origin[n]; ok {
		return pos, true
	}
	if f := p.FileOf(n.Pos()); f != nil {
		return f.Syn.Position(n.Pos()), true
	}
	return token.Position{}, false
}
