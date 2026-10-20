// Package mixed shows a package that contains both Go and GoNext files.
// The Go code in this file calls functions written in GoNext (route.gnx),
// and the GoNext code uses types declared here, without any binding layer.
package mixed

//go:generate go run github.com/ORGANIZATION/gonext/cmd/gonext translate -q .

import "fmt"

// Request is declared in Go.
type Request struct {
	Method string
	Path   string
}

// Handle dispatches a request with the GoNext router.
func Handle(r Request) string {
	switch rt := route(r); {
	case rt.IsNotFound():
		return "404 " + r.Path
	default:
		return fmt.Sprintf("200 %s", describe(rt))
	}
}
