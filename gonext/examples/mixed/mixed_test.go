package mixed

import "testing"

func TestHandle(t *testing.T) {
	for path, want := range map[string]string{
		"/":              "200 index",
		"/users/42":      "200 user 42",
		"/static/app.js": "200 app.js cached *",
		"/nope":          "404 /nope",
		"/users":         "404 /users",
	} {
		if got := Handle(Request{Method: "GET", Path: path}); got != want {
			t.Errorf("Handle(%q) = %q, want %q", path, got, want)
		}
	}
}
