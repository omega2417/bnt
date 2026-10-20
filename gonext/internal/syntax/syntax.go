// Package syntax implements stage S1 (parsing) of the GoNext transpiler.
//
// The GoNext grammar is a superset of the Go grammar. Instead of
// re-implementing a Go parser, S1 runs a token-level pre-parser over the
// GoNext source that recognizes the extension productions (enum
// declarations, match expressions, named and default arguments, extension
// methods, method type parameters and short anonymous functions), records
// them in side tables and replaces them by placeholder Go syntax. The
// resulting text is parsed by the standard go/parser. Every byte of the
// rewritten text is mapped back to the original source, and the rewriting
// preserves line structure, so that positions reported by later stages refer
// to GoNext lines.
package syntax

import (
	"fmt"
	"go/ast"
	"go/parser"
	"go/scanner"
	"go/token"
	"strings"
)

// Placeholder identifiers used in the rewritten Go text.
const (
	MatchFunc  = "__gonext_match"
	NamedFunc  = "__gonext_named"
	InferType  = "__gonext_infer"
	KeywordPfx = "gnkw_"
)

// EnumDecl is an enum declaration with associated data.
type EnumDecl struct {
	Name     string
	TParams  string // "[T any]" or ""
	Variants []*VariantDecl
	Repr     string // representation requested by a //gonext:repr comment
	Doc      string
	Offset   int // offset in the rewritten text where the declaration stood
	Pos      token.Position
}

// VariantDecl is one variant of an enum.
type VariantDecl struct {
	Name   string
	Params string // "(w, h float64)" or ""
	Pos    token.Position
}

// PatternDecl is one alternative of a match pattern.
type PatternDecl struct {
	Wildcard bool
	Qual     string   // qualifier in Enum.Variant
	Name     string   // variant or constant name
	Parens   bool     // Name(...) form
	Binders  []string // binder names, "_" for ignored payloads
	Expr     string   // source of a constant pattern
	Pos      token.Position
}

// ArmDecl is one arm of a match.
type ArmDecl struct {
	Patterns []*PatternDecl
	HasGuard bool
	Block    bool
	Pos      token.Position
}

// MatchDecl records the arms of a match; the scrutinee, guards and bodies are
// part of the placeholder call in the Go AST.
type MatchDecl struct {
	ID   int
	Arms []*ArmDecl
	Pos  token.Position
}

// File is a parsed GoNext file.
type File struct {
	Path    string
	Src     []byte
	Go      []byte // rewritten text
	Fset    *token.FileSet
	TokFile *token.File
	AST     *ast.File
	Map     *PosMap

	Enums         []*EnumDecl
	Matches       map[int]*MatchDecl
	Defaults      map[int]string // rewritten offset of '=' -> default expression
	ExtFuncs      map[int]bool   // rewritten offset of 'func' of ext declarations
	MethodTParams map[int]string // rewritten offset of method name -> "[U any]"

	lines []int // line start offsets of Src
}

// Position returns the original GoNext position of a position in the
// rewritten file.
func (f *File) Position(p token.Pos) token.Position {
	if !p.IsValid() || f.TokFile == nil || int(p) < f.TokFile.Base() || int(p) > f.TokFile.Base()+f.TokFile.Size() {
		return token.Position{Filename: f.Path}
	}
	return f.origPosition(f.Map.Orig(f.TokFile.Offset(p)))
}

func (f *File) origPosition(off int) token.Position {
	if f.lines == nil {
		f.lines = []int{0}
		for i, c := range f.Src {
			if c == '\n' {
				f.lines = append(f.lines, i+1)
			}
		}
	}
	lo, hi := 0, len(f.lines)
	for hi-lo > 1 {
		mid := (lo + hi) / 2
		if f.lines[mid] <= off {
			lo = mid
		} else {
			hi = mid
		}
	}
	return token.Position{Filename: f.Path, Offset: off, Line: lo + 1, Column: off - f.lines[lo] + 1}
}

// Error is a diagnostic at a GoNext source position.
type Error struct {
	Pos token.Position
	Msg string
}

func (e *Error) Error() string { return fmt.Sprintf("%s: %s", e.Pos, e.Msg) }

// ErrorList is a list of diagnostics.
type ErrorList []*Error

func (l ErrorList) Error() string {
	var b strings.Builder
	for i, e := range l {
		if i > 0 {
			b.WriteByte('\n')
		}
		b.WriteString(e.Error())
	}
	return b.String()
}

// Err returns l as an error, or nil if l is empty.
func (l ErrorList) Err() error {
	if len(l) == 0 {
		return nil
	}
	return l
}

// ParseFile parses a GoNext source file. Plain Go files can be parsed with
// it as well; they are returned unchanged.
func ParseFile(fset *token.FileSet, path string, src []byte) (*File, error) {
	f := &File{
		Path:          path,
		Src:           src,
		Fset:          fset,
		Map:           &PosMap{},
		Matches:       map[int]*MatchDecl{},
		Defaults:      map[int]string{},
		ExtFuncs:      map[int]bool{},
		MethodTParams: map[int]string{},
	}
	rw, err := newRewriter(f)
	if err != nil {
		return nil, err
	}
	rw.run()
	if len(rw.errs) > 0 {
		return nil, rw.errs
	}
	f.Go = rw.out.Bytes()
	astf, perr := parser.ParseFile(fset, path, f.Go, parser.ParseComments|parser.SkipObjectResolution)
	f.TokFile = fset.File(astf.Package)
	if f.TokFile == nil && astf != nil {
		fset.Iterate(func(tf *token.File) bool {
			if tf.Name() == path {
				f.TokFile = tf
			}
			return true
		})
	}
	if perr != nil {
		var errs ErrorList
		if list, ok := perr.(scanner.ErrorList); ok {
			for _, e := range list {
				p := e.Pos
				if f.TokFile != nil && p.Offset >= 0 && p.Offset <= f.TokFile.Size() {
					p = f.origPosition(f.Map.Orig(p.Offset))
				}
				errs = append(errs, &Error{Pos: p, Msg: e.Msg})
			}
		} else {
			errs = append(errs, &Error{Pos: token.Position{Filename: path}, Msg: perr.Error()})
		}
		return nil, errs
	}
	f.AST = astf
	return f, nil
}
