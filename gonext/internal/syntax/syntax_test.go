package syntax

import (
	"bytes"
	"go/token"
	"strings"
	"testing"
)

func parse(t *testing.T, src string) *File {
	t.Helper()
	f, err := ParseFile(token.NewFileSet(), "t.gnx", []byte(src))
	if err != nil {
		t.Fatalf("ParseFile: %v", err)
	}
	return f
}

func TestPlainGoUnchanged(t *testing.T) {
	src := "package p\n\nimport \"fmt\"\n\nfunc f(match int) {\n\tm := map[string]int{\"a\": 1}\n\tif match > 0 {\n\t\tfmt.Println(m[\"a\"], match)\n\t}\n}\n"
	f := parse(t, src)
	if string(f.Go) != src {
		t.Errorf("plain Go was rewritten:\n%s", f.Go)
	}
}

func TestLinesPreserved(t *testing.T) {
	src := `package p

enum E {
	A(x int)
	B
}

func f(e E, xs []int) int {
	g := (a, b) => a + b
	return match e {
		A(x) => x
		B    => 0
	}
}
`
	f := parse(t, src)
	if got, want := bytes.Count(f.Go, []byte("\n")), strings.Count(src, "\n"); got < want {
		t.Errorf("rewritten text has %d lines, source %d:\n%s", got, want, f.Go)
	}
	if len(f.Enums) != 1 || len(f.Enums[0].Variants) != 2 || f.Enums[0].Variants[0].Params != "(x int)" {
		t.Errorf("enum not recorded: %+v", f.Enums)
	}
	if len(f.Matches) != 1 || len(f.Matches[1].Arms) != 2 {
		t.Fatalf("match not recorded: %+v", f.Matches)
	}
	a := f.Matches[1].Arms[0].Patterns[0]
	if a.Name != "A" || !a.Parens || len(a.Binders) != 1 || a.Binders[0] != "x" {
		t.Errorf("pattern = %+v", a)
	}
	if !strings.Contains(string(f.Go), "func(a __gonext_infer, b __gonext_infer) __gonext_infer { return a + b }") {
		t.Errorf("lambda not rewritten:\n%s", f.Go)
	}
}

func TestPositionsMapBack(t *testing.T) {
	src := "package p\n\nfunc f() {\n\tx := dial(port: 1)\n}\n"
	f := parse(t, src)
	off := bytes.Index(f.Go, []byte("1)"))
	pos := f.Position(f.TokFile.Pos(off))
	if pos.Line != 4 || pos.Column != 18 {
		t.Errorf("position of the argument = %v, want t.gnx:4:18", pos)
	}
}

func TestDefaultsAndExt(t *testing.T) {
	src := "package p\n\next func (s []int) sum(from int = 0) int { return from }\n"
	f := parse(t, src)
	if len(f.ExtFuncs) != 1 {
		t.Errorf("ext not recorded")
	}
	if len(f.Defaults) != 1 {
		t.Errorf("defaults = %v", f.Defaults)
	}
	for _, v := range f.Defaults {
		if v != "0" {
			t.Errorf("default = %q", v)
		}
	}
}

func TestMethodTypeParamsAndKeywords(t *testing.T) {
	src := "package p\n\ntype L[T any] struct{}\n\nfunc (l L[T]) map[U any](f func(T) U) L[U] { return L[U]{} }\n\nfunc g(l L[int]) { l.map(x => x) }\n"
	f := parse(t, src)
	if len(f.MethodTParams) != 1 {
		t.Errorf("method type parameters not recorded")
	}
	if !strings.Contains(string(f.Go), "l.gnkw_map(") {
		t.Errorf("keyword selector not renamed:\n%s", f.Go)
	}
}

func TestSyntaxErrorsAtGoNextPositions(t *testing.T) {
	_, err := ParseFile(token.NewFileSet(), "t.gnx", []byte("package p\n\nfunc f() {\n\tx := match y {\n\t\tA => \n\t}\n}\n"))
	if err == nil {
		t.Fatal("expected an error")
	}
	if !strings.Contains(err.Error(), "t.gnx:5") {
		t.Errorf("error not at line 5: %v", err)
	}
}

func TestPosMap(t *testing.T) {
	var m PosMap
	m.add(0, 0, false)
	m.add(10, 20, true)
	m.add(15, 25, false)
	for out, want := range map[int]int{0: 0, 9: 9, 10: 20, 14: 20, 15: 25, 17: 27} {
		if got := m.Orig(out); got != want {
			t.Errorf("Orig(%d) = %d, want %d", out, got, want)
		}
	}
}
