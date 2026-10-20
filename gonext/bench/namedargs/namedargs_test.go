package namedargs

import (
	"testing"
	"time"
)

// TestEquivalence verifies that the three variants produce identical
// results for the call with one named and two omitted arguments, and
// that the defaults are applied when the named argument is the default.
func TestEquivalence(t *testing.T) {
	for _, retries := range []int{1, 3, 5, 42} {
		a := CallGoNext("example.org", retries)
		b := CallConfig("example.org", retries)
		c := CallOptions("example.org", retries)
		if a != b || a != c {
			t.Fatalf("retries=%d: %+v %+v %+v", retries, a, b, c)
		}
		want := Conn{Host: "example.org", Port: 443, Timeout: 5 * time.Second, Retries: retries}
		if a != want {
			t.Fatalf("got %+v, want %+v", a, want)
		}
	}
	// All parameters omitted except host.
	a := Dial("h", DefaultPort, DefaultTimeout, DefaultRetries)
	b := DialWithConfig(DialConfig{Host: "h"})
	c := DialWithOptions("h")
	if a != b || a != c {
		t.Fatalf("defaults: %+v %+v %+v", a, b, c)
	}
	// All parameters given.
	a = Dial("h", 80, time.Second, 7)
	b = DialWithConfig(DialConfig{Host: "h", Port: 80, Timeout: time.Second, Retries: 7})
	c = DialWithOptions("h", WithPort(80), WithTimeout(time.Second), WithRetries(7))
	if a != b || a != c {
		t.Fatalf("explicit: %+v %+v %+v", a, b, c)
	}
}
