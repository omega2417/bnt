Table 6. Generated-code measurements: median [interquartile range] of 10 runs.

| Benchmark | Time | Allocations | Memory |
|---|---|---|---|
| Enum construction, R1 interface | 38.0 [37.6–38.6] ns/value | 1 per value | 16 B + 16.0 B heap |
| Enum construction, R2 flat struct | 11.6 [11.3–12.1] ns/value | 0 | 72 B |
| Enum construction, R3 compact struct | 10.4 [10.3–10.6] ns/value | 0 | 48 B |
| Exhaustive match, R1 | 13.4 [13.2–13.5] ns/value | 0 | – |
| Exhaustive match, R2 | 12.8 [12.4–13.1] ns/value | 0 | – |
| Exhaustive match, R3 | 13.1 [12.8–13.5] ns/value | 0 | – |
| Named/default call, GoNext lowering | 8.7 [8.6–8.8] ns/call | 0 | 0 B |
| Named/default call, configuration struct | 10.8 [10.7–10.9] ns/call | 0 | 0 B |
| Named/default call, functional options | 48.5 [47.5–49.5] ns/call | 1 | 48 B |
| Generic method + lambda (4096 elements) | 8.36 [8.23–8.74] µs | 1 | 32 KiB |
| Hand-written loop (4096 elements) | 9.14 [8.61–9.42] µs | 1 | 32 KiB |
| Extension method sum (4096 elements) | 1.264 [1.183–1.286] µs | 0 | 0 B |
| Hand-written sum (4096 elements) | 1.302 [1.253–1.319] µs | 0 | 0 B |
