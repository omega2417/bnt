// Package driver runs the six stages of the GoNext transpiler on packages:
// S1 parsing, S2 IAST construction, S3 partial semantic analysis, S4
// normalization, S5 lowering and S6 emission.
package driver

import (
	"bufio"
	"errors"
	"fmt"
	"go/ast"
	"go/build"
	"go/importer"
	"go/parser"
	"go/token"
	"go/types"
	"os"
	"path/filepath"
	"sort"
	"strings"

	"github.com/ORGANIZATION/gonext/internal/emit"
	"github.com/ORGANIZATION/gonext/internal/iast"
	"github.com/ORGANIZATION/gonext/internal/sema"
	"github.com/ORGANIZATION/gonext/internal/syntax"
)

// Version is the version of the transpiler.
const Version = "v1.0.0"

// Ext is the file extension of GoNext sources.
const Ext = ".gnx"

// Options configures a translation.
type Options struct {
	Repr           iast.Repr // default enum representation
	LineDirectives bool
	Verify         bool // type-check the generated code and report errors
	DryRun         bool // do not write files
}

// DefaultOptions returns the default options.
func DefaultOptions() Options {
	return Options{Repr: iast.ReprCompact, LineDirectives: true, Verify: true}
}

// Output is a generated file.
type Output struct {
	Path string
	Src  string // GoNext source path
	Data []byte
}

// OutputName returns the name of the Go file generated for a GoNext file:
// shapes.gnx -> shapes_gnx.go, shapes_test.gnx -> shapes_gnx_test.go.
func OutputName(path string) string {
	base := strings.TrimSuffix(path, Ext)
	if strings.HasSuffix(base, "_test") {
		return strings.TrimSuffix(base, "_test") + "_gnx_test.go"
	}
	return base + "_gnx.go"
}

// IsGenerated reports whether a Go file name is a gonext output.
func IsGenerated(name string) bool {
	return strings.HasSuffix(name, "_gnx.go") || strings.HasSuffix(name, "_gnx_test.go")
}

// Translator translates packages. It shares one file set and one importer
// across packages so that packages translated earlier are visible to later
// ones.
type Translator struct {
	Opt  Options
	Fset *token.FileSet
	imp  types.Importer
}

// New returns a translator.
func New(opt Options) *Translator {
	fset := token.NewFileSet()
	return &Translator{Opt: opt, Fset: fset}
}

func (t *Translator) importer() types.Importer {
	if t.imp == nil {
		t.imp = importer.ForCompiler(t.Fset, "source", nil)
	}
	return t.imp
}

// TranslateSource translates a single GoNext file given as source text,
// without other files of its package. It is used by tests and tools.
func (t *Translator) TranslateSource(path string, src []byte) ([]byte, error) {
	outs, err := t.translateGroup(filepath.Dir(path), importPathFor(filepath.Dir(path)), []string{path}, map[string][]byte{path: src}, nil)
	if err != nil {
		return nil, err
	}
	return outs[0].Data, nil
}

// TranslateDir translates the GoNext files of the package in dir. Generated
// files are written next to their sources unless DryRun is set.
func (t *Translator) TranslateDir(dir string) ([]Output, error) {
	dir, err := filepath.Abs(dir)
	if err != nil {
		return nil, err
	}
	entries, err := os.ReadDir(dir)
	if err != nil {
		return nil, err
	}
	groups := map[string][]string{}  // package name -> gnx files
	goFiles := map[string][]string{} // package name -> go files
	var names []string
	ctxt := build.Default
	for _, e := range entries {
		n := e.Name()
		if e.IsDir() || strings.HasPrefix(n, ".") || strings.HasPrefix(n, "_") {
			continue
		}
		path := filepath.Join(dir, n)
		switch {
		case strings.HasSuffix(n, Ext):
		case strings.HasSuffix(n, ".go") && !IsGenerated(n):
			if ok, err := ctxt.MatchFile(dir, n); err != nil || !ok {
				continue
			}
		default:
			continue
		}
		pkg, err := packageName(path)
		if err != nil {
			return nil, err
		}
		if strings.HasSuffix(n, Ext) {
			if _, ok := groups[pkg]; !ok {
				names = append(names, pkg)
			}
			groups[pkg] = append(groups[pkg], path)
		} else {
			goFiles[pkg] = append(goFiles[pkg], path)
		}
	}
	if len(groups) == 0 {
		return nil, nil
	}
	// the package under test before its external test package
	sort.Slice(names, func(i, j int) bool {
		return !strings.HasSuffix(names[i], "_test") && strings.HasSuffix(names[j], "_test")
	})
	path := importPathFor(dir)
	var all []Output
	for _, name := range names {
		p := path
		if strings.HasSuffix(name, "_test") && len(names) > 1 {
			p += "_test"
		}
		outs, err := t.translateGroup(dir, p, groups[name], nil, goFiles[name])
		if err != nil {
			return all, err
		}
		if !t.Opt.DryRun {
			for _, o := range outs {
				if err := os.WriteFile(o.Path, o.Data, 0o644); err != nil {
					return all, err
				}
			}
		}
		all = append(all, outs...)
	}
	return all, nil
}

func packageName(path string) (string, error) {
	f, err := os.Open(path)
	if err != nil {
		return "", err
	}
	defer f.Close()
	sc := bufio.NewScanner(f)
	inComment := false
	for sc.Scan() {
		line := strings.TrimSpace(sc.Text())
		if inComment {
			if i := strings.Index(line, "*/"); i >= 0 {
				line = strings.TrimSpace(line[i+2:])
				inComment = false
			} else {
				continue
			}
		}
		if strings.HasPrefix(line, "/*") && !strings.Contains(line, "*/") {
			inComment = true
			continue
		}
		if strings.HasPrefix(line, "package ") {
			fs := strings.Fields(line)
			return fs[1], nil
		}
	}
	return "", fmt.Errorf("%s: missing package clause", path)
}

func (t *Translator) translateGroup(dir, importPath string, gnx []string, srcs map[string][]byte, goPaths []string) ([]Output, error) {
	// The source importer resolves imports with build.Default, which runs
	// the go command in build.Default.Dir; point it at the module of dir.
	if root, _ := ModuleRoot(dir); root != "" {
		build.Default.Dir = root
	}
	var files []*syntax.File
	var errs syntax.ErrorList
	sort.Strings(gnx)
	for _, path := range gnx {
		src, ok := srcs[path]
		if !ok {
			var err error
			if src, err = os.ReadFile(path); err != nil {
				return nil, err
			}
		}
		f, err := syntax.ParseFile(t.Fset, path, src)
		if err != nil {
			var el syntax.ErrorList
			if errors.As(err, &el) {
				errs = append(errs, el...)
				continue
			}
			return nil, err
		}
		files = append(files, f)
	}
	if len(errs) > 0 {
		return nil, errs
	}
	var goFiles []*ast.File
	for _, path := range goPaths {
		f, err := parser.ParseFile(t.Fset, path, nil, parser.ParseComments|parser.SkipObjectResolution)
		if err != nil {
			return nil, err
		}
		goFiles = append(goFiles, f)
	}
	pkg := iast.Build(t.Fset, dir, files, goFiles)
	an := sema.New(sema.Config{Path: importPath, Importer: t.importer(), Repr: t.Opt.Repr}, pkg)
	if err := an.Run(); err != nil {
		return nil, err
	}
	if t.Opt.Verify {
		if err := an.Verify(); err != nil {
			return nil, err
		}
	}
	var outs []Output
	for _, f := range pkg.Files {
		data, err := emit.File(pkg, f, emit.Options{LineDirectives: t.Opt.LineDirectives, Version: Version})
		if err != nil {
			return nil, err
		}
		outs = append(outs, Output{Path: OutputName(f.Syn.Path), Src: f.Syn.Path, Data: data})
	}
	return outs, nil
}

// ModuleRoot returns the directory containing go.mod above dir and the
// module path.
func ModuleRoot(dir string) (string, string) {
	for d := dir; ; {
		data, err := os.ReadFile(filepath.Join(d, "go.mod"))
		if err == nil {
			for _, line := range strings.Split(string(data), "\n") {
				line = strings.TrimSpace(line)
				if strings.HasPrefix(line, "module ") {
					return d, strings.Trim(strings.TrimSpace(line[len("module "):]), "\"")
				}
			}
			return d, ""
		}
		parent := filepath.Dir(d)
		if parent == d {
			return "", ""
		}
		d = parent
	}
}

func importPathFor(dir string) string {
	abs, err := filepath.Abs(dir)
	if err != nil {
		return filepath.Base(dir)
	}
	root, mod := ModuleRoot(abs)
	if root == "" || mod == "" {
		return filepath.Base(abs)
	}
	rel, err := filepath.Rel(root, abs)
	if err != nil || rel == "." {
		return mod
	}
	return mod + "/" + filepath.ToSlash(rel)
}

// Expand resolves package patterns (directories, optionally ending in /...)
// to the directories that contain GoNext files, ordered so that every
// package comes after the module-local packages it imports.
func Expand(patterns []string) ([]string, error) {
	if len(patterns) == 0 {
		patterns = []string{"."}
	}
	seen := map[string]bool{}
	var dirs []string
	add := func(d string) {
		if !seen[d] {
			seen[d] = true
			dirs = append(dirs, d)
		}
	}
	for _, p := range patterns {
		if strings.HasSuffix(p, ".gnx") {
			p = filepath.Dir(p)
		}
		if strings.HasSuffix(p, "/...") || p == "..." {
			root := strings.TrimSuffix(strings.TrimSuffix(p, "..."), "/")
			if root == "" {
				root = "."
			}
			err := filepath.WalkDir(root, func(path string, d os.DirEntry, err error) error {
				if err != nil {
					return err
				}
				if d.IsDir() {
					n := d.Name()
					if path != root && (strings.HasPrefix(n, ".") || strings.HasPrefix(n, "_") || n == "testdata" || n == "vendor") {
						return filepath.SkipDir
					}
					return nil
				}
				if strings.HasSuffix(path, Ext) {
					abs, _ := filepath.Abs(filepath.Dir(path))
					add(abs)
				}
				return nil
			})
			if err != nil {
				return nil, err
			}
			continue
		}
		abs, err := filepath.Abs(p)
		if err != nil {
			return nil, err
		}
		add(abs)
	}
	return order(dirs), nil
}

// order sorts directories topologically by their module-local imports.
func order(dirs []string) []string {
	byPath := map[string]string{}
	for _, d := range dirs {
		byPath[importPathFor(d)] = d
	}
	deps := map[string][]string{}
	for _, d := range dirs {
		entries, _ := os.ReadDir(d)
		for _, e := range entries {
			if !strings.HasSuffix(e.Name(), Ext) && !strings.HasSuffix(e.Name(), ".go") {
				continue
			}
			f, err := parser.ParseFile(token.NewFileSet(), filepath.Join(d, e.Name()), nil, parser.ImportsOnly)
			if err != nil {
				continue
			}
			for _, is := range f.Imports {
				p := strings.Trim(is.Path.Value, "\"")
				if dep, ok := byPath[p]; ok && dep != d {
					deps[d] = append(deps[d], dep)
				}
			}
		}
	}
	var out []string
	state := map[string]int{}
	var visit func(d string)
	visit = func(d string) {
		if state[d] != 0 {
			return
		}
		state[d] = 1
		for _, dep := range deps[d] {
			visit(dep)
		}
		state[d] = 2
		out = append(out, d)
	}
	for _, d := range dirs {
		visit(d)
	}
	return out
}

// Clean removes generated files from dir.
func Clean(dir string) error {
	entries, err := os.ReadDir(dir)
	if err != nil {
		return err
	}
	for _, e := range entries {
		if IsGenerated(e.Name()) {
			if err := os.Remove(filepath.Join(dir, e.Name())); err != nil {
				return err
			}
		}
	}
	return nil
}
