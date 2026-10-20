# GoNext — common tasks
GO ?= go
PYTHON ?= python3

.PHONY: all build check test fmt vet golden generate examples bench reproduce archive clean

all: build check

build:
	$(GO) build -o bin/gonext ./cmd/gonext

fmt:
	@out=$$(gofmt -l cmd internal gnrt bench examples); if [ -n "$$out" ]; then echo "gofmt needed:"; echo "$$out"; exit 1; fi

vet:
	$(GO) vet ./...

test:
	$(GO) test ./...

# quality gates 1-3 and diagnostics
check: fmt vet test generate-check

golden:
	$(GO) test ./internal/driver -run Golden -update

generate:
	$(GO) generate ./examples/...

# generated example files must be up to date
generate-check: generate
	@if git rev-parse --git-dir >/dev/null 2>&1; then \
		git diff --exit-code -- examples >/dev/null || (echo "generated files in examples/ are stale; run make generate"; exit 1); \
	fi

examples: generate
	$(GO) run ./examples/shapes
	$(GO) run ./examples/calc

# quality gate 4: regression benchmarks
bench:
	bash scripts/run_benchmarks.sh

reproduce:
	bash scripts/reproduce.sh

archive:
	bash scripts/make-zenodo-archive.sh

clean:
	rm -rf bin dist
