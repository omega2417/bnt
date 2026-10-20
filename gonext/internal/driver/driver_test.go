package driver

import (
	"bytes"
	"errors"
	"flag"
	"fmt"
	"go/format"
	"os"
	"os/exec"
	"path/filepath"
	"regexp"
	"strings"
	"testing"

	"github.com/ORGANIZATION/gonext/internal/iast"
	"github.com/ORGANIZATION/gonext/internal/syntax"
)

var update = flag.Bool("update", false, "rewrite golden files")

var allReprs = []iast.Repr{iast.ReprCompact, iast.ReprFlat, iast.ReprInterface}

// goldenReprs lists the representations a golden input is translated with.
var goldenReprs = map[string][]iast.Repr{
	"listing5_shape.gnx": allReprs,
	"match_forms.gnx":    allReprs,
}

func repoRoot(t *testing.T) string {
	t.Helper()
	root, err := filepath.Abs("../..")
	if err != nil {
		t.Fatal(err)
	}
	return root
}

func goldenName(src string, r iast.Repr, n int) string {
	base := strings.TrimSuffix(src, Ext)
	if n == 1 {
		return base + ".golden"
	}
	return base + "." + string(r) + ".golden"
}

func translate(t *testing.T, path string, r iast.Repr) ([]byte, error) {
	t.Helper()
	src, err := os.ReadFile(path)
	if err != nil {
		t.Fatal(err)
	}
	opt := DefaultOptions()
	opt.Repr = r
	return New(opt).TranslateSource(path, src)
}

// TestGolden compares generated code with reviewed expectations (quality
// gate 1). Run with -update to rewrite the expectations.
func TestGolden(t *testing.T) {
	files, _ := filepath.Glob("../../testdata/golden/*.gnx")
	if len(files) == 0 {
		t.Fatal("no golden inputs")
	}
	for _, path := range files {
		reprs := goldenReprs[filepath.Base(path)]
		if reprs == nil {
			reprs = []iast.Repr{iast.ReprCompact}
		}
		for _, r := range reprs {
			name := goldenName(path, r, len(reprs))
			t.Run(filepath.Base(name), func(t *testing.T) {
				got, err := translate(t, path, r)
				if err != nil {
					t.Fatalf("translate: %v", err)
				}
				if *update {
					if err := os.WriteFile(name, got, 0o644); err != nil {
						t.Fatal(err)
					}
					return
				}
				want, err := os.ReadFile(name)
				if err != nil {
					t.Fatalf("%v (run go test -update)", err)
				}
				if !bytes.Equal(got, want) {
					t.Errorf("generated code differs from %s (run go test -update and review the diff)\n%s", name, diff(want, got))
				}
			})
		}
	}
}

func diff(a, b []byte) string {
	al, bl := strings.Split(string(a), "\n"), strings.Split(string(b), "\n")
	for i := 0; i < len(al) || i < len(bl); i++ {
		var x, y string
		if i < len(al) {
			x = al[i]
		}
		if i < len(bl) {
			y = bl[i]
		}
		if x != y {
			return fmt.Sprintf("first difference at line %d:\n- %s\n+ %s", i+1, x, y)
		}
	}
	return ""
}

// tempModule creates a module that can import the gonext run-time package.
func tempModule(t *testing.T, name string) string {
	t.Helper()
	dir := t.TempDir()
	gomod := fmt.Sprintf("module %s\n\ngo 1.24\n\nrequire github.com/ORGANIZATION/gonext v0.0.0\n\nreplace github.com/ORGANIZATION/gonext => %s\n", name, repoRoot(t))
	if err := os.WriteFile(filepath.Join(dir, "go.mod"), []byte(gomod), 0o644); err != nil {
		t.Fatal(err)
	}
	return dir
}

func goCmd(t *testing.T, dir string, args ...string) (string, error) {
	t.Helper()
	c := exec.Command("go", args...)
	c.Dir = dir
	c.Env = append(os.Environ(), "GOFLAGS=-mod=mod", "GOWORK=off")
	out, err := c.CombinedOutput()
	return string(out), err
}

// TestGeneratedCodeQuality checks that every generated file is accepted by
// gofmt, go vet and the Go type checker without warnings (quality gate 2).
func TestGeneratedCodeQuality(t *testing.T) {
	if testing.Short() {
		t.Skip("runs the go command")
	}
	files, _ := filepath.Glob("../../testdata/golden/*.gnx")
	for _, path := range files {
		reprs := goldenReprs[filepath.Base(path)]
		if reprs == nil {
			reprs = []iast.Repr{iast.ReprCompact}
		}
		for _, r := range reprs {
			t.Run(filepath.Base(path)+"/"+string(r), func(t *testing.T) {
				got, err := translate(t, path, r)
				if err != nil {
					t.Fatal(err)
				}
				formatted, err := format.Source(got)
				if err != nil {
					t.Fatal(err)
				}
				if !bytes.Equal(formatted, got) {
					t.Errorf("generated code is not gofmt-formatted\n%s", diff(got, formatted))
				}
				dir := tempModule(t, "golden")
				if err := os.WriteFile(filepath.Join(dir, OutputName(filepath.Base(path))), got, 0o644); err != nil {
					t.Fatal(err)
				}
				if out, err := goCmd(t, dir, "vet", "."); err != nil {
					t.Errorf("go vet: %v\n%s", err, out)
				}
			})
		}
	}
}

var errRe = regexp.MustCompile(`// ERROR "((?:[^"\\]|\\.)*)"`)

// TestDiagnostics checks that errors are reported at the GoNext lines that
// carry an ERROR annotation, and nowhere else.
func TestDiagnostics(t *testing.T) {
	files, _ := filepath.Glob("../../testdata/diagnostics/*.gnx")
	if len(files) == 0 {
		t.Fatal("no diagnostics inputs")
	}
	for _, path := range files {
		t.Run(filepath.Base(path), func(t *testing.T) {
			src, err := os.ReadFile(path)
			if err != nil {
				t.Fatal(err)
			}
			want := map[int]*regexp.Regexp{}
			for i, line := range strings.Split(string(src), "\n") {
				if m := errRe.FindStringSubmatch(line); m != nil {
					want[i+1] = regexp.MustCompile(strings.ReplaceAll(m[1], `\"`, `"`))
				}
			}
			_, err = New(DefaultOptions()).TranslateSource(path, src)
			var list syntax.ErrorList
			if !errors.As(err, &list) {
				t.Fatalf("expected diagnostics, got %v", err)
			}
			seen := map[int]bool{}
			for _, e := range list {
				re, ok := want[e.Pos.Line]
				switch {
				case !ok:
					t.Errorf("unexpected error %s", e)
				case !re.MatchString(e.Msg):
					t.Errorf("line %d: error %q does not match %q", e.Pos.Line, e.Msg, re)
				default:
					seen[e.Pos.Line] = true
				}
			}
			for line, re := range want {
				if !seen[line] {
					t.Errorf("line %d: missing error matching %q", line, re)
				}
			}
		})
	}
}

// TestDifferential runs every program in testdata/run under all enum
// representations and compares the output with expected.out (quality gate
// 3: the same GoNext program under alternative lowering schemes).
func TestDifferential(t *testing.T) {
	if testing.Short() {
		t.Skip("runs the go command")
	}
	dirs, _ := filepath.Glob("../../testdata/run/*")
	for _, src := range dirs {
		want, err := os.ReadFile(filepath.Join(src, "expected.out"))
		if err != nil {
			t.Fatal(err)
		}
		for _, r := range allReprs {
			t.Run(filepath.Base(src)+"/"+string(r), func(t *testing.T) {
				dir := tempModule(t, "example.com/"+filepath.Base(src))
				copyTree(t, src, dir)
				dirs, err := Expand([]string{filepath.Join(dir, "...")})
				if err != nil {
					t.Fatal(err)
				}
				opt := DefaultOptions()
				opt.Repr = r
				tr := New(opt)
				for _, d := range dirs {
					if _, err := tr.TranslateDir(d); err != nil {
						t.Fatal(err)
					}
				}
				out, err := goCmd(t, dir, "run", ".")
				if err != nil {
					t.Fatalf("go run: %v\n%s", err, out)
				}
				if out != string(want) {
					t.Errorf("output differs from expected.out\n%s", diff(want, []byte(out)))
				}
				if out, err := goCmd(t, dir, "vet", "./..."); err != nil {
					t.Errorf("go vet: %v\n%s", err, out)
				}
			})
		}
	}
}

func copyTree(t *testing.T, from, to string) {
	t.Helper()
	err := filepath.WalkDir(from, func(path string, d os.DirEntry, err error) error {
		if err != nil {
			return err
		}
		rel, _ := filepath.Rel(from, path)
		dst := filepath.Join(to, rel)
		if d.IsDir() {
			return os.MkdirAll(dst, 0o755)
		}
		if IsGenerated(d.Name()) || d.Name() == "expected.out" {
			return nil
		}
		data, err := os.ReadFile(path)
		if err != nil {
			return err
		}
		return os.WriteFile(dst, data, 0o644)
	})
	if err != nil {
		t.Fatal(err)
	}
}

func TestOutputName(t *testing.T) {
	for in, want := range map[string]string{
		"a/shapes.gnx":      "a/shapes_gnx.go",
		"a/shapes_test.gnx": "a/shapes_gnx_test.go",
	} {
		if got := OutputName(in); got != want {
			t.Errorf("OutputName(%q) = %q, want %q", in, got, want)
		}
	}
}
