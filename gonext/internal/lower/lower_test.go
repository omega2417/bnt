package lower

import (
	"go/types"
	"testing"

	"github.com/ORGANIZATION/gonext/internal/iast"
)

func TestExtName(t *testing.T) {
	for src, want := range map[string]string{
		"[]int":           "ext_IntSlice_sum",
		"*Counter":        "ext_PtrCounter_sum",
		"map[string]int":  "ext_MapStringInt_sum",
		"time.Duration":   "ext_TimeDuration_sum",
		"List[T]":         "ext_List_sum",
		"[]T":             "ext_TSlice_sum",
		"chan<- []string": "ext_ChanStringSlice_sum",
	} {
		x, err := iast.ParseExpr(src)
		if err != nil {
			t.Fatal(err)
		}
		if got := ExtName(x, "sum"); got != want {
			t.Errorf("ExtName(%s) = %s, want %s", src, got, want)
		}
	}
	x, _ := iast.ParseExpr("[]int")
	if got := ExtName(x, "Sum"); got != "Ext_IntSlice_Sum" {
		t.Errorf("exported extension name = %s", got)
	}
}

func TestClassifyAndPointers(t *testing.T) {
	str := types.Typ[types.String]
	cases := []struct {
		t        types.Type
		class    string
		pointers bool
	}{
		{types.Typ[types.Int], "int", false},
		{types.Typ[types.Uint8], "int", false},
		{types.Typ[types.Float64], "float64", false},
		{types.Typ[types.Float32], "float32", false},
		{types.Typ[types.Bool], "bool", false},
		{str, "string", true},
		{types.Typ[types.UnsafePointer], "unsafe", true},
		{types.NewPointer(str), "ptr", true},
		{types.NewSlice(str), "slice", true},
		{types.NewMap(str, str), "ref", true},
		{types.NewArray(types.Typ[types.Int], 4), "typed", false},
		{types.NewArray(str, 2), "typed", true},
		{types.Typ[types.Complex128], "typed", false},
	}
	for _, c := range cases {
		if got := Classify(c.t); got != c.class {
			t.Errorf("Classify(%s) = %s, want %s", c.t, got, c.class)
		}
		if got := HasPointers(c.t); got != c.pointers {
			t.Errorf("HasPointers(%s) = %v, want %v", c.t, got, c.pointers)
		}
	}
}

// TestCompactInvariant checks Equation (4) of the article on a layout: a
// payload that carries pointers is never stored in an integer word.
func TestCompactInvariant(t *testing.T) {
	e := &iast.Enum{Name: "E"}
	payload := []types.Type{
		types.Typ[types.Int], types.Typ[types.String], types.NewPointer(types.Typ[types.Int]),
		types.NewSlice(types.Typ[types.Byte]), types.Typ[types.Float64], types.NewArray(types.Typ[types.String], 2),
	}
	v := &iast.Variant{Enum: e, Name: "V"}
	for i, pt := range payload {
		x, _ := iast.ParseExpr("int")
		v.Fields = append(v.Fields, &iast.Field{Name: string(rune('a' + i)), Type: x, T: pt})
	}
	e.Variants = []*iast.Variant{v}
	l := &Lowerer{}
	if err := l.ComputeLayout(e); err != nil {
		t.Fatal(err)
	}
	for _, f := range v.Fields {
		if HasPointers(f.T) && f.Slot.Kind == iast.SlotWord {
			t.Errorf("field %s of type %s stored in a word", f.Name, f.T)
		}
	}
	if e.Layout.Words != 2 || e.Layout.Ptrs != 3 || e.Layout.Lens != 3 || len(e.Layout.Typed) != 1 {
		t.Errorf("layout = %+v", e.Layout)
	}
}
