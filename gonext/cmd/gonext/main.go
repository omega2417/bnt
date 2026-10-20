// Command gonext translates GoNext sources (.gnx) into ordinary Go files and
// wraps the Go toolchain.
//
// Usage:
//
//	gonext translate [flags] [packages]   translate .gnx files to _gnx.go files
//	gonext build     [go build flags] [packages]
//	gonext test      [go test flags] [packages]
//	gonext vet       [go vet flags] [packages]
//	gonext run       [go run flags] file.gnx|dir [args]
//	gonext clean     [packages]           remove generated files
//	gonext version
//
// Packages are directories; a trailing /... selects all directories below.
// The default is the current directory for translate and ./... for the
// toolchain wrappers. For use with go generate, add to a Go file:
//
//	//go:generate gonext translate .
package main

import (
	"errors"
	"flag"
	"fmt"
	"os"
	"os/exec"
	"path/filepath"
	"strings"

	"github.com/ORGANIZATION/gonext/internal/driver"
	"github.com/ORGANIZATION/gonext/internal/iast"
	"github.com/ORGANIZATION/gonext/internal/syntax"
)

func usage() {
	fmt.Fprint(os.Stderr, `gonext translates the GoNext dialect of Go into standard Go.

Usage:
  gonext translate [-repr compact|flat|interface] [-lines=true] [-verify=true] [-n] [packages]
  gonext build|test|vet [go flags] [packages]
  gonext run [go run flags] file.gnx|dir [args]
  gonext clean [packages]
  gonext version
`)
}

func main() {
	if len(os.Args) < 2 {
		usage()
		os.Exit(2)
	}
	cmd, args := os.Args[1], os.Args[2:]
	var err error
	switch cmd {
	case "translate":
		err = translate(args)
	case "build", "test", "vet":
		err = wrap(cmd, args)
	case "run":
		err = run(args)
	case "clean":
		err = clean(args)
	case "version":
		fmt.Println("gonext", driver.Version)
	case "help", "-h", "-help", "--help":
		usage()
	default:
		fmt.Fprintf(os.Stderr, "gonext: unknown command %q\n", cmd)
		usage()
		os.Exit(2)
	}
	if err != nil {
		var el syntax.ErrorList
		if errors.As(err, &el) {
			for _, e := range el {
				e.Pos.Filename = rel(e.Pos.Filename)
				fmt.Fprintln(os.Stderr, e)
			}
		} else {
			fmt.Fprintln(os.Stderr, "gonext:", err)
		}
		var ee *exec.ExitError
		if errors.As(err, &ee) {
			os.Exit(ee.ExitCode())
		}
		os.Exit(1)
	}
}

func rel(path string) string {
	wd, err := os.Getwd()
	if err != nil {
		return path
	}
	if r, err := filepath.Rel(wd, path); err == nil && !strings.HasPrefix(r, "..") {
		return r
	}
	return path
}

func translate(args []string) error {
	fs := flag.NewFlagSet("translate", flag.ExitOnError)
	repr := fs.String("repr", string(iast.ReprCompact), "default enum representation: compact, flat or interface")
	lines := fs.Bool("lines", true, "emit //line directives that map to GoNext sources")
	verify := fs.Bool("verify", true, "type-check the generated code and report errors at GoNext positions")
	dry := fs.Bool("n", false, "print the generated code instead of writing files")
	quiet := fs.Bool("q", false, "do not list generated files")
	fs.Parse(args)
	opt := driver.DefaultOptions()
	opt.Repr = iast.Repr(*repr)
	if !iast.ValidRepr(opt.Repr) {
		return fmt.Errorf("unknown representation %q", *repr)
	}
	opt.LineDirectives = *lines
	opt.Verify = *verify
	opt.DryRun = *dry
	return translateAll(fs.Args(), opt, *quiet)
}

func translateAll(patterns []string, opt driver.Options, quiet bool) error {
	dirs, err := driver.Expand(patterns)
	if err != nil {
		return err
	}
	t := driver.New(opt)
	for _, d := range dirs {
		outs, err := t.TranslateDir(d)
		if err != nil {
			return err
		}
		for _, o := range outs {
			switch {
			case opt.DryRun:
				fmt.Printf("// ---- %s\n%s", rel(o.Path), o.Data)
			case !quiet:
				fmt.Fprintf(os.Stderr, "%s -> %s\n", rel(o.Src), rel(o.Path))
			}
		}
	}
	return nil
}

// split separates go flags from package arguments.
func split(args []string) (flags, pkgs []string) {
	for i := 0; i < len(args); i++ {
		a := args[i]
		if strings.HasPrefix(a, "-") {
			flags = append(flags, a)
			if !strings.Contains(a, "=") && i+1 < len(args) && takesValue(a) {
				flags = append(flags, args[i+1])
				i++
			}
			continue
		}
		pkgs = append(pkgs, a)
	}
	return
}

func takesValue(flag string) bool {
	switch strings.TrimLeft(flag, "-") {
	case "o", "run", "bench", "count", "tags", "ldflags", "gcflags", "timeout", "cpu", "benchtime", "coverprofile", "p", "exec", "skip", "covermode", "coverpkg", "mod", "modfile", "C", "parallel":
		return true
	}
	return false
}

func wrap(cmd string, args []string) error {
	flags, pkgs := split(args)
	if len(pkgs) == 0 {
		pkgs = []string{"./..."}
	}
	if err := translateAll(pkgs, driver.DefaultOptions(), true); err != nil {
		return err
	}
	return gotool(append(append([]string{cmd}, flags...), pkgs...)...)
}

func run(args []string) error {
	var flags []string
	i := 0
	for ; i < len(args) && strings.HasPrefix(args[i], "-"); i++ {
		flags = append(flags, args[i])
	}
	if i >= len(args) {
		return errors.New("run: missing file or directory")
	}
	target := args[i]
	dir := target
	if strings.HasSuffix(target, driver.Ext) || strings.HasSuffix(target, ".go") {
		dir = filepath.Dir(target)
	}
	if err := translateAll([]string{dir}, driver.DefaultOptions(), true); err != nil {
		return err
	}
	if !strings.HasPrefix(dir, ".") && !filepath.IsAbs(dir) {
		dir = "./" + dir
	}
	return gotool(append(append(append([]string{"run"}, flags...), dir), args[i+1:]...)...)
}

func clean(args []string) error {
	if len(args) == 0 {
		args = []string{"./..."}
	}
	dirs, err := driver.Expand(args)
	if err != nil {
		return err
	}
	for _, d := range dirs {
		if err := driver.Clean(d); err != nil {
			return err
		}
	}
	return nil
}

func gotool(args ...string) error {
	c := exec.Command("go", args...)
	c.Stdin, c.Stdout, c.Stderr = os.Stdin, os.Stdout, os.Stderr
	return c.Run()
}
