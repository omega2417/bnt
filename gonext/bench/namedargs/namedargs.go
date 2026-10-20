// Package namedargs reproduces Experiment 2 of the GoNext manuscript
// (Section 2.6, Section 3.3.1, Listings 1 and 2, Table 6, Figure 4d): a
// call with one named argument and two omitted defaulted parameters,
//
//	func dial(host string, port int = 443,
//	          timeout time.Duration = 5*time.Second, retries int = 3) Conn
//	c1 := dial("example.org", retries: 5)
//
// lowered by GoNext to a positional call with the defaults inlined at the
// call site, compared with the two idioms Go programmers use for the same
// purpose: a configuration struct with zero-value defaults and the
// functional-options pattern. Every callee is marked //go:noinline so
// that the comparison concerns the call itself.
package namedargs

import "time"

// Default parameter values of dial (Listing 1).
const (
	DefaultPort    = 443
	DefaultTimeout = 5 * time.Second
	DefaultRetries = 3
)

// Conn is the small result struct returned by value by every variant.
type Conn struct {
	Host    string
	Port    int
	Timeout time.Duration
	Retries int
}

// ---------------------------------------------------------------------
// Variant 1: GoNext lowering (Listing 2).

// Dial is the callee as emitted by GoNext (Listing 2): defaulted
// parameters become ordinary positional parameters.
//
//go:noinline
func Dial(host string, port int, timeout time.Duration, retries int) Conn {
	return Conn{Host: host, Port: port, Timeout: timeout, Retries: retries}
}

// CallGoNext is the lowered call site of Listing 2:
// dial("example.org", retries: 5) becomes
// dial("example.org", 443, 5*time.Second, 5).
func CallGoNext(host string, retries int) Conn {
	return Dial(host, 443, 5*time.Second, retries)
}

// ---------------------------------------------------------------------
// Variant 2: configuration struct with zero-value defaults (idiomatic Go).

// DialConfig carries the parameters of DialWithConfig; zero fields take
// the default values.
type DialConfig struct {
	Host    string
	Port    int
	Timeout time.Duration
	Retries int
}

// DialWithConfig is the configuration-struct idiom.
//
//go:noinline
func DialWithConfig(cfg DialConfig) Conn {
	if cfg.Port == 0 {
		cfg.Port = DefaultPort
	}
	if cfg.Timeout == 0 {
		cfg.Timeout = DefaultTimeout
	}
	if cfg.Retries == 0 {
		cfg.Retries = DefaultRetries
	}
	return Conn{Host: cfg.Host, Port: cfg.Port, Timeout: cfg.Timeout, Retries: cfg.Retries}
}

// CallConfig is the call site of the configuration-struct idiom.
func CallConfig(host string, retries int) Conn {
	return DialWithConfig(DialConfig{Host: host, Retries: retries})
}

// ---------------------------------------------------------------------
// Variant 3: functional options (idiomatic Go).

type dialOptions struct {
	host    string
	port    int
	timeout time.Duration
	retries int
}

// Option configures DialWithOptions.
type Option func(*dialOptions)

// WithPort sets the port.
func WithPort(p int) Option { return func(o *dialOptions) { o.port = p } }

// WithTimeout sets the timeout.
func WithTimeout(d time.Duration) Option { return func(o *dialOptions) { o.timeout = d } }

// WithRetries sets the number of retries.
func WithRetries(n int) Option { return func(o *dialOptions) { o.retries = n } }

// DialWithOptions is the functional-options idiom.
//
//go:noinline
func DialWithOptions(host string, opts ...Option) Conn {
	o := dialOptions{host: host, port: DefaultPort, timeout: DefaultTimeout, retries: DefaultRetries}
	for _, opt := range opts {
		opt(&o)
	}
	return Conn{Host: o.host, Port: o.port, Timeout: o.timeout, Retries: o.retries}
}

// CallOptions is the call site of the functional-options idiom.
func CallOptions(host string, retries int) Conn {
	return DialWithOptions(host, WithRetries(retries))
}
